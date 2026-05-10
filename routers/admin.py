import os
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from middleware.auth import _ai_counters, _counters
from routers.stocks import _ticker_counters
from services.api_keys import count_active_keys
from services.contacts import list_contact_messages

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(key: str = "") -> None:
    expected = os.environ.get("ADMIN_KEY", "nurilabs2026")
    if key != expected:
        raise HTTPException(status_code=401, detail="관리자 키가 필요합니다.")


@router.get("/stats")
def admin_stats(key: str = Query("")):
    _require_admin(key)
    today = date.today()

    ai_today = {k: v[0] for k, v in _ai_counters.items() if v[1] == today}
    api_today = {k: v[0] for k, v in _counters.items() if v[1] == today}

    total_ai = sum(ai_today.values())
    total_api = sum(api_today.values()) + total_ai

    top_ips = sorted(ai_today.items(), key=lambda x: x[1], reverse=True)[:10]
    top_tickers = sorted(_ticker_counters.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "date": today.isoformat(),
        "total_api_requests_today": total_api,
        "total_ai_requests_today": total_ai,
        "top_ips_by_ai_requests": [{"identifier": k, "count": v} for k, v in top_ips],
        "top_tickers": [{"ticker": k, "count": v} for k, v in top_tickers],
        "registered_users": count_active_keys(),
    }


@router.get("/contacts")
def admin_contacts(key: str = Query(""), limit: int = Query(20, ge=1, le=100), status: str = Query("")):
    _require_admin(key)
    contacts = list_contact_messages(limit=limit, status=status or None)
    return {"contacts": contacts, "count": len(contacts)}
