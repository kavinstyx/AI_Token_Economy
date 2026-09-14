"""
decider.py — routing brain.
Primary: read model_specs + routing_rules from MySQL.
Fallback: if DB is unreachable, log the error and use hardcoded rules.
"""
import os
import logging
from dataclasses import dataclass
import mysql.connector

# --- error logging to FILE (works even when DB is down) ---
logging.basicConfig(
    filename=os.environ.get("ERROR_LOG", "errors.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("decider")

# model names must match litellm_config.yaml
LOCAL_MODEL = "local-qwen"
EXTERNAL_MODEL = "gemini-flash"

DB = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "3308")),
    database=os.environ.get("DB_NAME", "token_economy"),
    user=os.environ.get("DB_USER", "appuser"),
    password=os.environ.get("DB_PASSWORD", "apppass"),
)

# hardcoded fallback rules (same logic as before)
_HARD_KEYWORDS = ["code","python","javascript","sql","regex","algorithm",
                  "legal","contract","medical","translate","prove","analyze","essay"]
_LENGTH_THRESHOLD = 240


@dataclass
class Decision:
    model: str
    reason: str
    rule: str
    source: str   # 'db' | 'fallback'


def _decide_from_db(prompt: str) -> Decision:
    """Load rules from MySQL and apply them (first match by priority)."""
    conn = mysql.connector.connect(**DB, connection_timeout=3)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM routing_rules WHERE active=TRUE ORDER BY priority ASC")
        rules = cur.fetchall()
        text = (prompt or "").strip()
        lowered = text.lower()
        for r in rules:
            ct = r["condition_type"]
            if ct == "keyword":
                kws = [k.strip() for k in (r["condition_value"] or "").split(",") if k.strip()]
                hit = next((k for k in kws if k in lowered), None)
                if hit:
                    return Decision(r["target_model"], f"{r['reason_label']} (keyword: '{hit}').", f"db_kw_{hit}", "db")
            elif ct == "max_chars":
                if len(text) > int(r["condition_value"]):
                    return Decision(r["target_model"], f"{r['reason_label']} ({len(text)} chars).", "db_long", "db")
            elif ct == "default":
                return Decision(r["target_model"], f"{r['reason_label']} ({len(text)} chars).", "db_default", "db")
        # if no rule matched at all, use local as last resort
        return Decision(LOCAL_MODEL, "No rule matched — defaulting to local.", "db_nomatch", "db")
    finally:
        conn.close()


def _decide_fallback(prompt: str) -> Decision:
    """Hardcoded rules used when the DB is unreachable."""
    text = (prompt or "").strip()
    lowered = text.lower()
    hit = next((k for k in _HARD_KEYWORDS if k in lowered), None)
    if hit:
        return Decision(EXTERNAL_MODEL, f"[FALLBACK] Harder task (keyword: '{hit}').", "fb_kw", "fallback")
    if len(text) > _LENGTH_THRESHOLD:
        return Decision(EXTERNAL_MODEL, f"[FALLBACK] Long prompt ({len(text)} chars).", "fb_long", "fallback")
    return Decision(LOCAL_MODEL, f"[FALLBACK] Short prompt ({len(text)} chars) — local.", "fb_default", "fallback")


def decide(prompt: str) -> Decision:
    """Try DB rules; on any DB error, log it and fall back to hardcoded rules."""
    try:
        return _decide_from_db(prompt)
    except Exception as e:
        log.warning(f"DB routing unavailable, using fallback rules. Error: {type(e).__name__}: {e}")
        return _decide_fallback(prompt)