"""
metering.py — records RAW usage only.

Golden rule: store the provider's native token counts, untouched.
No conversion to "our tokens" here — that's a separate layer we add later,
which will READ this table and apply a rate map. Keeping raw immutable means
we can always re-rate history when our prices change.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "usage.db"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS usage_raw (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              TEXT    NOT NULL,   -- ISO timestamp (UTC)
            user_key        TEXT,               -- who sent it (for attribution later)
            mode            TEXT,               -- local | gemini | decider
            requested_model TEXT,               -- what the caller/decider asked for
            served_model    TEXT,               -- what actually answered
            decider_rule    TEXT,               -- which rule fired (if decider mode)
            prompt_tokens   INTEGER,
            completion_tokens INTEGER,
            total_tokens    INTEGER,            -- includes hidden reasoning tokens!
            prompt_chars    INTEGER
        )
    """)
    con.commit()
    con.close()


def record(*, user_key, mode, requested_model, served_model, decider_rule,
           usage: dict, prompt_chars: int):
    """usage is the raw `usage` block from the LiteLLM response."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """INSERT INTO usage_raw
           (ts, user_key, mode, requested_model, served_model, decider_rule,
            prompt_tokens, completion_tokens, total_tokens, prompt_chars)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            user_key, mode, requested_model, served_model, decider_rule,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
            prompt_chars,
        ),
    )
    con.commit()
    con.close()


def recent(limit=50):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM usage_raw ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def summary():
    """Simple per-model totals — the raw material the conversion layer will use."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT served_model,
               COUNT(*)              AS requests,
               SUM(prompt_tokens)    AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens,
               SUM(total_tokens)     AS total_tokens
        FROM usage_raw
        GROUP BY served_model
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print("DB initialised at", DB_PATH)
