"""
Claude AI 분석 엔진
- 종목 분석 / 시장 개요 / 포트폴리오 리뷰
- 5월 7일 이전 Claude 크레딧 소진 시 Ollama로 자동 폴백(Fallback) 기능 탑재
"""
import os
import json
import logging
from anthropic import Anthropic
from . import ollama_ai

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or "your_anthropic_api_key" in key:
        return None
    if _client is None:
        try:
            _client = Anthropic(api_key=key)
        except Exception as e:
            logger.warning("Anthropic 클라이언트 생성 실패: %s", e)
            return None
    return _client


def _ask(system: str, user: str, max_tokens: int = 1200, fallback_text: str = "") -> str:
    client = _get_client()
    if client:
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text
        except Exception as e:
            logger.warning("Claude API 호출 실패: %s", e)
    
    # Fallback to Ollama
    logger.info("Ollama 엔진 분석 수행 중...")
    prompt = f"System: {system}\n\nUser: {user}"
    try:
        return ollama_ai.quick_summary(prompt, max_chars=max_tokens)
    except Exception as ollama_err:
        logger.error("Ollama 엔진 오류: %s", ollama_err)
        return "현재 AI 엔진 점검 중입니다. 잠시 후 다시 시도해주세요."


SYSTEM_PROMPT = """주식 시장 전문가이자 AI 투자 비서입니다.
KOSPI, KOSDAQ, 테마주 등 한국 시장의 수급과 차트 데이터를 분석하여, 주가 변동의 이유를 한국어로 쉽고 명확하게 설명합니다.
분석 결과는 마크다운(## 제목, **강조**, - 목록) 형식을 사용하며 감정적인 예측보다는 데이터 기반의 팩트 위주로 전달해야 합니다.
"""


def stock_analysis(ticker: str, data: dict) -> str:
    info = data["info"]
    ind = data["indicators"]
    user_msg = f"""
다음은 주식 시장 데이터입니다. **{info['name']} ({ticker})** 종목에 대해 심층 분석해주세요.

## 기본 정보
- 종목명: {info['name']} / 시장: {info.get('market', '')} / 섹터: {info.get('sector', '')}

## 주요 지표
- 현재가: {ind['current_price']:,.0f}원 (전일비 {data.get('change_pct', 0):+.2f}%)
- 5일평균: {ind['ma5']:,.0f} / 20일평균: {ind['ma20']:,.0f} / 60일평균: {ind.get('ma60', 'N/A')}
- RSI(14): {ind['rsi14']}
- 52주 최고가: {ind['high_52w']:,.0f}원 ({ind['pct_from_high']:+.1f}%)
- 52주 최저가: {ind['low_52w']:,.0f}원 ({ind['pct_from_low']:+.1f}%)
- 데이터 기준일: {data.get('data_date', '')}

## 최근 가격 추이
{data['recent_prices']}

다음을 포함하여 분석해줘:
1. 오늘 주가 변동의 핵심 원인 2. 수급(외인/기관) 동향 3. 기술적 분석(이평선, RSI) 4. 향후 주의/기대 포인트 5. 한줄 요약
""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500)


def market_overview(indices: dict) -> str:
    lines = [f"- {name}: {d['value']:,.2f} ({d['change_pct']:+.2f}%)" for name, d in indices.items()]
    user_msg = f"""현재 시장 지수 현황입니다.\n{chr(10).join(lines)}\n\n1. 전체 시장 심리 2. 주요 지수 변동 요인 3. 섹터별 특징 4. 투자자 주의사항""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1000)


def sector_analysis(sector: str, stocks: list) -> str:
    lines = [f"- {s['name']} ({s['code']}): {s['current_price']:,.0f}원 ({s['change_pct']:+.2f}%)" for s in stocks]
    user_msg = f"""**{sector}** 섹터 내 주요 종목 현황입니다:\n{chr(10).join(lines)}\n\n1. 섹터 주도 테마 2. 대장주/수혜주 분석 3. 향후 전망 4. 리스크 요인""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1200)


def portfolio_review(holdings: list) -> str:
    total = sum(h.get("current_value", 0) for h in holdings)
    lines = [f"- {h['name']} ({h['ticker']}): 매수 {h.get('avg_price',0):,.0f} / 현재 {h.get('current_price',0):,.0f} / 수익률 {h.get('return_pct',0):+.1f}%" for h in holdings]
    user_msg = f"""사용자 포트폴리오(총액 {total:,.0f}원) 현황:\n{chr(10).join(lines)}\n\n1. 포트폴리오 총평 2. 종목별 비중 분석 3. 기술적 매도/매수 의견 5. 포트폴리오 관리 제언""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500)
