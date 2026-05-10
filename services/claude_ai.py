"""
Claude AI 분석 엔진
- 종목 변동 브리핑 / 시장 개요 / 포트폴리오 복기
- 5월 7일 이전 Claude 크레딧 소진 시 Ollama로 자동 폴백(Fallback) 기능 탑재
"""
import os
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
        if not ollama_ai.get_ollama_status().get("available"):
            return fallback_text or "현재 AI 엔진 점검 중입니다. 잠시 후 다시 시도해주세요."
        return ollama_ai.quick_summary(prompt, max_chars=max_tokens)
    except Exception as ollama_err:
        logger.error("Ollama 엔진 오류: %s", ollama_err)
        return fallback_text or "현재 AI 엔진 점검 중입니다. 잠시 후 다시 시도해주세요."


SYSTEM_PROMPT = """당신은 한국 주식 시장의 변동 이유를 설명하는 AI 브리핑 애널리스트입니다.
목표는 매수/매도 추천이 아니라, 사용자가 주가 변화의 맥락을 빠르게 이해하도록 돕는 것입니다.
제공된 가격/거래량/지표 데이터 안에서만 판단하고, 외부 뉴스·공시·수급 데이터가 없으면 확인 필요라고 명확히 말합니다.
수익 보장, 목표가 제시, 매수/매도 지시, 개인별 투자자문처럼 보이는 표현은 피합니다.
분석 결과는 마크다운 형식으로 작성하고, 마지막에 "투자 판단은 본인 책임이며 이 내용은 투자자문이 아닌 정보 브리핑입니다."를 포함합니다.
"""


def stock_analysis(ticker: str, data: dict) -> str:
    info = data["info"]
    ind = data["indicators"]
    user_msg = f"""
다음은 주식 시장 데이터입니다. **{info['name']} ({ticker})** 종목의 변동 이유를 브리핑해주세요.

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

다음 형식으로 작성해줘:
## 한줄 브리핑
- 오늘 가격 변화가 어떤 상태인지 한 문장으로 요약

## 데이터로 확인되는 변화
- 현재가, 등락률, 이동평균, RSI, 52주 위치를 바탕으로 관찰 가능한 변화만 설명

## 아직 확인이 필요한 것
- 뉴스, 공시, 외국인/기관 수급, 테마 이슈처럼 현재 데이터에 없는 항목은 단정하지 말고 확인 필요로 분리

## 체크 포인트
- 추격 매수/손절 같은 지시 대신, 사용자가 추가로 확인해야 할 리스크와 지표를 정리
""".strip()
    fallback = f"""## 한줄 브리핑
- {info['name']}({ticker})은 현재 {ind['current_price']:,.0f}원이며 전일 대비 {data.get('change_pct', 0):+.2f}% 변동했습니다.

## 데이터로 확인되는 변화
- 5일평균 {ind['ma5']:,.0f}원, 20일평균 {ind['ma20']:,.0f}원, RSI(14) {ind['rsi14']} 기준으로 단기 가격 위치를 확인할 수 있습니다.
- 52주 최고가 대비 {ind['pct_from_high']:+.1f}%, 52주 최저가 대비 {ind['pct_from_low']:+.1f}% 위치입니다.

## 아직 확인이 필요한 것
- 뉴스, 공시, 외국인/기관 수급 데이터는 현재 응답 데이터에 포함되어 있지 않아 별도 확인이 필요합니다.

## 체크 포인트
- 급등락 원인을 단정하기보다 공시, 거래량 변화, 업종 동향을 함께 확인하세요.

투자 판단은 본인 책임이며 이 내용은 투자자문이 아닌 정보 브리핑입니다."""
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500, fallback_text=fallback)


def market_overview(indices: dict) -> str:
    lines = [f"- {name}: {d['value']:,.2f} ({d['change_pct']:+.2f}%)" for name, d in indices.items()]
    user_msg = f"""현재 시장 지수 현황입니다.\n{chr(10).join(lines)}\n\n1. 오늘 시장 분위기 2. 지수별 특징 3. 추가 확인이 필요한 변수 4. 투자자가 체크할 리스크를 정보 브리핑 형식으로 작성하세요.""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1000)


def sector_analysis(sector: str, stocks: list) -> str:
    lines = [f"- {s['name']} ({s['code']}): {s['current_price']:,.0f}원 ({s['change_pct']:+.2f}%)" for s in stocks]
    user_msg = f"""**{sector}** 섹터 내 주요 종목 현황입니다:\n{chr(10).join(lines)}\n\n1. 섹터 내부에서 강한 종목과 약한 종목 2. 데이터로만 확인되는 공통점 3. 추가 확인이 필요한 뉴스/공시/수급 4. 체크할 리스크를 정보 브리핑 형식으로 작성하세요.""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1200)


def portfolio_review(holdings: list) -> str:
    total = sum(h.get("current_value", 0) for h in holdings)
    lines = [f"- {h['name']} ({h['ticker']}): 매수 {h.get('avg_price',0):,.0f} / 현재 {h.get('current_price',0):,.0f} / 수익률 {h.get('return_pct',0):+.1f}%" for h in holdings]
    user_msg = f"""사용자 포트폴리오(총액 {total:,.0f}원) 현황:\n{chr(10).join(lines)}\n\n매수/매도 지시 없이 1. 손익 구조 요약 2. 특정 종목 쏠림 여부 3. 추가 확인이 필요한 리스크 4. 사용자가 직접 복기할 질문을 작성하세요.""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500)
