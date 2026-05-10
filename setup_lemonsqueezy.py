"""
Lemon Squeezy 상품 자동 생성 스크립트
Usage:
  1. LEMON_API_KEY 환경변수 설정 (Lemon Squeezy Dashboard → Settings → API)
  2. python setup_lemonsqueezy.py
  3. 성공 시 .env 파일에 STARTER_VARIANT_ID, PRO_VARIANT_ID 자동 업데이트
"""

import os
import sys
import json
import re
import httpx

API_BASE = "https://api.lemonsqueezy.com/v1"
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

PLANS = [
    {
        "key": "starter",
        "name": "스타터",
        "description": "개인 투자자를 위한 AI 주식 분석 입문 플랜 — AI 분석 30회/일",
        "price": 9900,          # KRW
        "interval": "month",
        "env_key": "STARTER_VARIANT_ID",
    },
    {
        "key": "pro",
        "name": "프로",
        "description": "적극적인 투자자를 위한 AI 주식 분석 풀 플랜 — AI 분석 100회/일 + 포트폴리오 리뷰",
        "price": 29900,         # KRW
        "interval": "month",
        "env_key": "PRO_VARIANT_ID",
    },
]


def get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def get_store_id(client: httpx.Client) -> str:
    r = client.get(f"{API_BASE}/stores")
    r.raise_for_status()
    stores = r.json()["data"]
    if not stores:
        raise RuntimeError("Lemon Squeezy 스토어가 없습니다. 대시보드에서 먼저 스토어를 생성해주세요.")
    store = stores[0]
    print(f"✅ 스토어 확인: {store['attributes']['name']} (ID: {store['id']})")
    return store["id"]


def create_product(client: httpx.Client, store_id: str, plan: dict) -> str:
    payload = {
        "data": {
            "type": "products",
            "attributes": {
                "name": plan["name"],
                "description": plan["description"],
                "status": "published",
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": store_id}}
            },
        }
    }
    r = client.post(f"{API_BASE}/products", json=payload)
    r.raise_for_status()
    product_id = r.json()["data"]["id"]
    print(f"✅ 상품 생성: {plan['name']} (Product ID: {product_id})")
    return product_id


def create_variant(client: httpx.Client, product_id: str, plan: dict) -> str:
    # Lemon Squeezy 가격 단위: 센트 (USD) 또는 원화는 정수 (ex: 9900 = ₩9,900)
    payload = {
        "data": {
            "type": "variants",
            "attributes": {
                "name": f"{plan['name']} 월간",
                "price": plan["price"],
                "is_subscription": True,
                "interval": plan["interval"],
                "interval_count": 1,
                "status": "published",
            },
            "relationships": {
                "product": {"data": {"type": "products", "id": product_id}}
            },
        }
    }
    r = client.post(f"{API_BASE}/variants", json=payload)
    r.raise_for_status()
    variant_id = r.json()["data"]["id"]
    print(f"✅ 가격 플랜 생성: {plan['name']} ₩{plan['price']:,}/월 (Variant ID: {variant_id})")
    return variant_id


def update_env(updates: dict):
    """기존 .env 파일의 특정 키 값을 업데이트"""
    if not os.path.exists(ENV_FILE):
        print(f"⚠️  .env 파일 없음: {ENV_FILE}")
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    for key, value in updates.items():
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={value}"

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ .env 업데이트 완료:")
    for k, v in updates.items():
        print(f"   {k}={v}")


def main():
    api_key = os.environ.get("LEMON_API_KEY") or os.environ.get("LEMONSQUEEZY_API_KEY")
    if not api_key:
        print("❌ LEMON_API_KEY 환경변수가 없습니다.")
        print()
        print("설정 방법:")
        print("  PowerShell: $env:LEMON_API_KEY='your_key_here'")
        print("  CMD:        set LEMON_API_KEY=your_key_here")
        print()
        print("API 키 발급: https://app.lemonsqueezy.com/settings/api")
        sys.exit(1)

    print("🍋 Lemon Squeezy 상품 생성 시작...\n")

    with httpx.Client(headers=get_headers(api_key), timeout=30) as client:
        store_id = get_store_id(client)

        env_updates = {}
        for plan in PLANS:
            print(f"\n--- {plan['name']} 플랜 ---")
            product_id = create_product(client, store_id, plan)
            variant_id = create_variant(client, product_id, plan)
            env_updates[plan["env_key"]] = variant_id

        update_env(env_updates)

    print("\n🎉 완료! .env에 Variant ID가 저장되었습니다.")
    print("다음 단계: Railway 환경변수에도 동일하게 추가해주세요.")


if __name__ == "__main__":
    main()
