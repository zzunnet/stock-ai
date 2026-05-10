"""
토스페이먼츠 연동 (한국 결제) + Lemon Squeezy 웹훅
"""
import hashlib
import hmac
import json
import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.api_keys import create_key, update_user_tier

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "test_sk_zXLkKEypNArWmo50nX3lmeaxYG5R")
TOSS_API_BASE = "https://api.tosspayments.com/v1"

PLANS = {
    "starter": {
        "name": "스타터",
        "price_krw": 9900,
        "requests_per_day": 100,
        "ai_requests_per_day": 30,
        "features": ["종목 분석 30회/일", "시장 동향 분석", "섹터 분석"],
    },
    "pro": {
        "name": "프로",
        "price_krw": 29900,
        "requests_per_day": 500,
        "ai_requests_per_day": 100,
        "features": ["종목 분석 100회/일", "포트폴리오 리뷰", "감성 분석 무제한", "우선 지원"],
    },
}


@router.get("/plans")
def get_plans():
    return {
        "free": {"name": "무료", "price_krw": 0, "requests_per_day": 30, "ai_requests_per_day": 1, "features": ["종목 분석 1회/일", "시장 지수 조회"]},
        **PLANS,
    }


class CreatePaymentRequest(BaseModel):
    plan: str
    email: str
    order_name: str = ""


@router.post("/create-payment")
def create_payment(req: CreatePaymentRequest):
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 플랜: {req.plan}")
    plan = PLANS[req.plan]
    import secrets, time
    order_id = f"order_{int(time.time())}_{secrets.token_hex(4)}"
    return {
        "client_key": os.environ.get("TOSS_CLIENT_KEY", "test_ck_D5GePWvyJnrK0W0k6q8gLzN97Eoq"),
        "order_id": order_id,
        "order_name": req.order_name or f"주식 AI 분석 {plan['name']} 구독",
        "amount": plan["price_krw"],
        "customer_email": req.email,
        "plan": req.plan,
    }


class ConfirmPaymentRequest(BaseModel):
    payment_key: str
    order_id: str
    amount: int
    plan: str
    email: str


def _variant_to_tier(variant_id: str, starter_vid: str, pro_vid: str) -> str:
    if pro_vid and variant_id == pro_vid:
        return "pro"
    if starter_vid and variant_id == starter_vid:
        return "starter"
    return ""


@router.post("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    secret = os.environ.get("LEMON_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("LEMON_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    body = await request.body()
    sig = request.headers.get("X-Signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        logger.warning("Lemon Squeezy webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = payload.get("meta", {}).get("event_name", "")
    data = payload.get("data", {})
    attrs = data.get("attributes", {})

    # email: custom_data 우선, 없으면 user_email
    meta_custom = payload.get("meta", {}).get("custom_data") or {}
    attr_custom = attrs.get("custom_data") or {}
    custom_data = meta_custom or attr_custom
    email = (custom_data.get("email") or attrs.get("user_email") or "").lower().strip()

    starter_vid = os.environ.get("STARTER_VARIANT_ID", "")
    pro_vid = os.environ.get("PRO_VARIANT_ID", "")

    if event_type == "order_created":
        variant_id = str(attrs.get("first_order_item", {}).get("variant_id", ""))
        tier = _variant_to_tier(variant_id, starter_vid, pro_vid)
        if email and tier:
            updated = update_user_tier(email, tier)
            logger.info("order_created: email=%s variant=%s tier=%s updated=%s", email, variant_id, tier, updated)
        else:
            logger.warning("order_created: email=%s or tier=%s missing, skipped", email, tier)

    elif event_type in ("subscription_created", "subscription_updated"):
        variant_id = str(attrs.get("variant_id", ""))
        tier = _variant_to_tier(variant_id, starter_vid, pro_vid)
        if email and tier:
            updated = update_user_tier(email, tier)
            logger.info("%s: email=%s variant=%s tier=%s updated=%s", event_type, email, variant_id, tier, updated)
        else:
            logger.warning("%s: email=%s or tier=%s missing, skipped", event_type, email, tier)

    elif event_type == "subscription_cancelled":
        if email:
            updated = update_user_tier(email, "free")
            logger.info("subscription_cancelled: email=%s → free updated=%s", email, updated)
        else:
            logger.warning("subscription_cancelled: email missing, skipped")

    else:
        logger.info("Lemon Squeezy webhook: unhandled event_type=%s", event_type)

    return {"received": True}


@router.post("/confirm-payment")
async def confirm_payment(req: ConfirmPaymentRequest):
    import base64
    auth = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TOSS_API_BASE}/payments/confirm",
                json={"paymentKey": req.payment_key, "orderId": req.order_id, "amount": req.amount},
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                timeout=15,
            )
        data = resp.json()
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=data.get("message", "결제 승인 실패"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"결제 서버 오류: {e}")

    api_key = create_key(tier=req.plan, email=req.email)
    logger.info("결제 완료 및 API 키 발급: %s / %s", req.plan, req.email)
    return {"success": True, "api_key": api_key, "plan": req.plan, "message": "결제 완료! API 키를 안전하게 보관하세요."}
