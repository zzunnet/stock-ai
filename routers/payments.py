"""
토스페이먼츠 연동 (한국 결제)
"""
import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.api_keys import create_key

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
        "free": {"name": "무료", "price_krw": 0, "requests_per_day": 30, "ai_requests_per_day": 3, "features": ["종목 분석 3회/일", "시장 지수 조회"]},
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
