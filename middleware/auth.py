from collections import defaultdict
from datetime import date

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from services.api_keys import check_and_increment_usage, get_key_info

FREE_DAILY_LIMIT = 30
FREE_AI_DAILY_LIMIT = 1
TIER_LIMITS = {
    "free": {"api": FREE_DAILY_LIMIT, "ai": FREE_AI_DAILY_LIMIT},
    "starter": {"api": 100, "ai": 30},
    "pro": {"api": 500, "ai": 100},
}

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
            return info["tier"], f"key:{api_key}", True
    return "free", f"anon:{_client_identifier(request)}", False


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

        tier, identifier, has_api_key = _resolve_tier(request)
        request.state.tier = tier
        request.state.identifier = identifier
        request.state.has_api_key = has_api_key

        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        is_ai = path.startswith("/api/ai/")
        kind = "ai" if is_ai else "api"
        limit = limits[kind]
        counters = _ai_counters if is_ai else _counters
        if not check_and_increment_usage(identifier, kind, limit):
            message = (
                f"AI 브리핑 한도({limit}회/일)를 초과했습니다."
                if is_ai else f"일일 API 요청 한도({limit}회)를 초과했습니다."
            )
            return JSONResponse(status_code=429, content={"detail": message, "upgrade_url": "/#pricing"})
        _check(counters, identifier, 10**9)

        return await call_next(request)
