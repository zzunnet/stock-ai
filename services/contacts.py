import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from psycopg2.extras import RealDictCursor

from services.api_keys import _get_conn, _use_db

_CONTACTS_FILE = Path(__file__).parent.parent / "data" / "contacts.json"


def _json_load() -> list[dict]:
    if not _CONTACTS_FILE.exists():
        return []
    with open(_CONTACTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _json_save(data: list[dict]) -> None:
    _CONTACTS_FILE.parent.mkdir(exist_ok=True)
    with open(_CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_contact_message(name: str, email: str, subject: str, message: str, ip: str = "", user_agent: str = "") -> dict:
    now = datetime.utcnow()
    if _use_db():
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO contact_messages (name, email, subject, message, ip, user_agent, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, name, email, subject, message, status, ip, user_agent, created_at
                    """,
                    (name, email, subject, message, ip, user_agent, now),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    data = _json_load()
    item = {
        "id": (max([m.get("id", 0) for m in data]) + 1) if data else 1,
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "status": "new",
        "ip": ip,
        "user_agent": user_agent,
        "created_at": now.isoformat(),
    }
    data.append(item)
    _json_save(data)
    return item


def list_contact_messages(limit: int = 50, status: Optional[str] = None) -> list[dict]:
    limit = max(1, min(limit, 100))
    if _use_db():
        where = "WHERE status = %s" if status else ""
        params = (status, limit) if status else (limit,)
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT id, name, email, subject, message, status, ip, user_agent, created_at
                    FROM contact_messages
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    data = _json_load()
    if status:
        data = [m for m in data if m.get("status") == status]
    return sorted(data, key=lambda m: m.get("created_at", ""), reverse=True)[:limit]
