from datetime import date

from fastapi import APIRouter

from middleware.auth import _ai_counters, _counters
from routers.stocks import _ticker_counters
from services.api_keys import count_active_keys

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats():
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
