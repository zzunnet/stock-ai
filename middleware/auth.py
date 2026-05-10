from collections import defaultdict
from datetime import date

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from services.api_keys import get_key_info

FREE_DAILY_LIMIT = 30
FREE_AI_DAILY_LIMIT = 1

_counters: dict = defaultdict(lambda: (0, date.min))
_ai_counters: dict = defaultdict(lambda: (0, date.min))

_SKIP_PREFIXES = ("/api/payments/webhook", "/api/payments/", "/api/auth/", "/api/ai/engine-status", "/health", "/static/", "/docs", "/openapi", "/redoc")


def _client_identifier(request: Request) -> str:
    forwarded = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _resolve_tier(request: Request) -> tuple:
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        info = get_key_info(api_key)
        if info:
            return info["tier"], api_key
    return "free", _client_identifier(request)


def _check(counters: dict, identifier: str, limit: int) -> bool:
    today = date.today()
    count, day = counters[identifier]
    if day < today:
        count, day = 0, today
    if count >= limit:
        return False
    counters[identifier] = (count + 1, day)
    return True


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not path.startswith("/api/") or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        tier, identifier = _resolve_tier(request)

        if tier == "free":
            is_ai = path.startswith("/api/ai/")
            if is_ai:
                if not _check(_ai_counters, identifier, FREE_AI_DAILY_LIMIT):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": f"AI 브리핑 무료 한도({FREE_AI_DAILY_LIMIT}회/일)를 초과했습니다.", "upgrade_url": "/api/payments/plans"},
                    )
            else:
                if not _check(_counters, identifier, FREE_DAILY_LIMIT):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": f"일일 무료 요청 한도({FREE_DAILY_LIMIT}회)를 초과했습니다.", "upgrade_url": "/api/payments/plans"},
                    )

        return await call_next(request)
