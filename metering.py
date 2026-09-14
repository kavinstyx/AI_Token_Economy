"""
metering.py — records RAW usage to MySQL. No conversion.
If the DB write fails, log the error (don't crash the request).
"""
import os
import logging
from datetime import datetime, timezone
import mysql.connector

logging.basicConfig(
    filename=os.environ.get("ERROR_LOG", "errors.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("metering")

DB = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "3308")),
    database=os.environ.get("DB_NAME", "token_economy"),
    user=os.environ.get("DB_USER", "appuser"),
    password=os.environ.get("DB_PASSWORD", "apppass"),
)


def record(*, user_key, mode, requested_model, served_model, decider_rule,
           usage: dict, prompt_chars: int, routing_source: str):
    try:
        conn = mysql.connector.connect(**DB, connection_timeout=3)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO usage_raw
               (ts, user_key, mode, requested_model, served_model, decider_rule,
                prompt_tokens, completion_tokens, total_tokens, prompt_chars, routing_source)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
             user_key, mode, requested_model, served_model, decider_rule,
             usage.get("prompt_tokens"), usage.get("completion_tokens"),
             usage.get("total_tokens"), prompt_chars, routing_source),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Metering write failed (usage not saved). Error: {type(e).__name__}: {e}")