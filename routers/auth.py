import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from services.api_keys import get_key_info, get_user_by_email, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_PLAN_LIMITS = {
    "free":    {"api_calls_per_day": 30,  "ai_analyses_per_day": 1},
    "starter": {"api_calls_per_day": 100, "ai_analyses_per_day": 30},
    "pro":     {"api_calls_per_day": 500, "ai_analyses_per_day": 100},
}


class RegisterRequest(BaseModel):
    email: str


class AccountLookupRequest(BaseModel):
    email: str


@router.post("/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="유효한 이메일 주소를 입력해주세요.")

    try:
        result = register_user(email)
    except ValueError as exc:
        if str(exc) == "already_registered":
            raise HTTPException(status_code=409, detail="이미 등록된 이메일입니다.")
        raise HTTPException(status_code=400, detail=str(exc))

    # 이메일 발송 시뮬레이션 (콘솔 출력)
    print(f"\n[API 키 발급] 수신: {email} | 키: {result['api_key']}\n")
    logger.info("[이메일 시뮬레이션] 수신: %s | 키: %s", email, result["api_key"])

    return {
        "api_key": result["api_key"],
        "tier": result["tier"],
        "message": "API 키가 발급되었습니다. 같은 이메일로 결제하면 이 키의 플랜이 자동으로 업그레이드됩니다.",
    }


@router.get("/me")
def me(x_api_key: str = Header(..., alias="X-API-Key")):
    info = get_key_info(x_api_key)
    if not info:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키입니다.")

    tier = info.get("tier", "free")
    return {
        "email": info.get("email", ""),
        "tier": tier,
        "created_at": info.get("created_at"),
        "plan": _PLAN_LIMITS.get(tier, _PLAN_LIMITS["free"]),
    }


@router.post("/account")
def account_lookup(req: AccountLookupRequest):
    email = req.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="이메일을 입력해주세요.")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="등록된 이메일이 없습니다.")
    return {
        "email": user["email"],
        "tier": user.get("tier", "free"),
        "api_key": user.get("api_key", ""),
        "created_at": user.get("created_at"),
        "subscription_status": user.get("subscription_status", ""),
        "customer_portal_url": user.get("customer_portal_url", ""),
        "plan": _PLAN_LIMITS.get(user.get("tier", "free"), _PLAN_LIMITS["free"]),
    }
