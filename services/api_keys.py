import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _get_conn():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)


def init_db():
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        key        TEXT PRIMARY KEY,
                        tier       TEXT        NOT NULL,
                        email      TEXT        NOT NULL DEFAULT '',
                        created_at TIMESTAMP   NOT NULL DEFAULT NOW(),
                        active     BOOLEAN     NOT NULL DEFAULT TRUE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        email      TEXT PRIMARY KEY,
                        tier       TEXT      NOT NULL DEFAULT 'free',
                        api_key    TEXT      NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        verified   BOOLEAN   NOT NULL DEFAULT FALSE
                    )
                """)
            conn.commit()
        logger.info("DB 초기화 완료 (api_keys, users 테이블)")
    except Exception as e:
        logger.warning("DB 초기화 실패 (DATABASE_URL 미설정?): %s", e)


_DATA_FILE = Path(__file__).parent.parent / "data" / "api_keys.json"


def _json_load() -> dict:
    if not _DATA_FILE.exists():
        return {}
    with open(_DATA_FILE) as f:
        return json.load(f)


def _json_save(data: dict) -> None:
    _DATA_FILE.parent.mkdir(exist_ok=True)
    with open(_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _use_db() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def create_key(tier: str, email: str = "") -> str:
    key = "sak_" + secrets.token_urlsafe(32)
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO api_keys (key, tier, email, created_at, active) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (key, tier, email, datetime.utcnow(), True),
                )
            conn.commit()
    else:
        data = _json_load()
        data[key] = {
            "tier": tier,
            "email": email,
            "created_at": datetime.utcnow().isoformat(),
            "active": True,
        }
        _json_save(data)
    return key


def get_key_info(key: str) -> Optional[dict]:
    if not key or not key.startswith("sak_"):
        return None
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT tier, email, created_at, active FROM api_keys "
                    "WHERE key = %s AND active = TRUE",
                    (key,),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    else:
        data = _json_load()
        info = data.get(key)
        return info if info and info.get("active") else None


def count_active_keys() -> int:
    if _use_db():
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM api_keys WHERE active = TRUE")
                    return cur.fetchone()[0]
        except Exception:
            return 0
    else:
        data = _json_load()
        return sum(1 for v in data.values() if v.get("active"))


def revoke_key(key: str) -> bool:
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE api_keys SET active = FALSE WHERE key = %s",
                    (key,),
                )
                updated = cur.rowcount
            conn.commit()
        return updated > 0
    else:
        data = _json_load()
        if key in data:
            data[key]["active"] = False
            _json_save(data)
            return True
        return False


def update_user_tier(email: str, tier: str) -> bool:
    """Update user tier after payment event. Returns True if user was found and updated."""
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET tier = %s WHERE email = %s RETURNING api_key",
                    (tier, email),
                )
                row = cur.fetchone()
                if not row:
                    return False
                api_key = row[0]
                cur.execute("UPDATE api_keys SET tier = %s WHERE key = %s", (tier, api_key))
            conn.commit()
        return True
    else:
        data = _json_load()
        updated = False
        for v in data.values():
            if v.get("email") == email:
                v["tier"] = tier
                updated = True
        if updated:
            _json_save(data)
        return updated


def register_user(email: str) -> dict:
    """Register a new user. Returns {api_key, tier}. Raises ValueError('already_registered') if duplicate."""
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT api_key FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    raise ValueError("already_registered")
                api_key = "sak_" + secrets.token_urlsafe(32)
                cur.execute(
                    "INSERT INTO api_keys (key, tier, email, created_at, active) VALUES (%s, %s, %s, %s, %s)",
                    (api_key, "free", email, datetime.utcnow(), True),
                )
                cur.execute(
                    "INSERT INTO users (email, tier, api_key, created_at, verified) VALUES (%s, %s, %s, %s, %s)",
                    (email, "free", api_key, datetime.utcnow(), False),
                )
            conn.commit()
        return {"api_key": api_key, "tier": "free"}
    else:
        data = _json_load()
        for v in data.values():
            if v.get("email") == email:
                raise ValueError("already_registered")
        api_key = create_key("free", email)
        return {"api_key": api_key, "tier": "free"}
