"""
Claude AI 분석 서비스
- 종목 분석 / 시장 동향 / 포트폴리오 리뷰
"""
import os
import json
import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다")
        _client = Anthropic(api_key=key)
    return _client


def _ask(system: str, user: str, max_tokens: int = 1200) -> str:
    client = _get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


SYSTEM_PROMPT = """당신은 한국 주식시장 전문 AI 애널리스트입니다.
KOSPI, KOSDAQ, 국내외 경제 환경에 정통하며, 투자자들이 이해하기 쉬운 한국어로 명확한 분석을 제공합니다.
분석은 데이터 기반으로 객관적이어야 하며, 투자 결정은 최종적으로 투자자 본인의 판단임을 항상 명시하세요.
마크다운 형식(## 제목, **굵게**, - 항목)을 사용해 가독성 높게 작성하세요.
"""


def stock_analysis(ticker: str, data: dict) -> str:
    info = data["info"]
    ind = data["indicators"]
    user_msg = f"""
다음 데이터를 바탕으로 **{info['name']} ({ticker})** 종목을 분석해주세요.

## 기본 정보
- 종목명: {info['name']} / 시장: {info.get('market', '')} / 섹터: {info.get('sector', '')}

## 가격 지표
- 현재가: {ind['current_price']:,.0f}원 (전일대비 {data.get('change_pct', 0):+.2f}%)
- 5일 이평: {ind['ma5']:,.0f} / 20일 이평: {ind['ma20']:,.0f} / 60일 이평: {ind.get('ma60', 'N/A')}
- RSI(14): {ind['rsi14']}
- 52주 고가: {ind['high_52w']:,.0f}원 ({ind['pct_from_high']:+.1f}%)
- 52주 저가: {ind['low_52w']:,.0f}원 ({ind['pct_from_low']:+.1f}%)
- 기준일: {data.get('data_date', '')}

## 최근 20일 종가
{data['recent_prices']}

1. **현황 요약** 2. **기술적 분석** 3. **투자 포인트** 4. **리스크 요인** 5. **종합 의견**
""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500)


def market_overview(indices: dict) -> str:
    lines = [f"- {name}: {d['value']:,.2f} ({d['change_pct']:+.2f}%)" for name, d in indices.items()]
    user_msg = f"""현재 시장 지수:\n{chr(10).join(lines)}\n\n1. 국내 시장 동향 2. 글로벌 영향 3. 주목 섹터 4. 단기 전망""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1000)


def sector_analysis(sector: str, stocks: list) -> str:
    lines = [f"- {s['name']} ({s['code']}): {s['current_price']:,.0f}원 ({s['change_pct']:+.2f}%)" for s in stocks]
    user_msg = f"""**{sector}** 섹터:\n{chr(10).join(lines)}\n\n1. 섹터 동향 2. 강세/약세 3. 투자 포인트 4. 관심 종목""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1200)


def portfolio_review(holdings: list) -> str:
    total = sum(h.get("current_value", 0) for h in holdings)
    lines = [f"- {h['name']} ({h['ticker']}): 평단 {h.get('avg_price',0):,.0f} / 현재 {h.get('current_price',0):,.0f} / {h.get('return_pct',0):+.1f}%" for h in holdings]
    user_msg = f"""포트폴리오 (총 {total:,.0f}원):\n{chr(10).join(lines)}\n\n1. 구성 평가 2. 종목별 의견 3. 리밸런싱 4. 리스크 5. 종합""".strip()
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1500)


def earnings_summary(ticker: str, name: str, financials: dict) -> str:
    user_msg = f"**{name} ({ticker})** 재무:\n{json.dumps(financials, ensure_ascii=False, indent=2)}\n\n1. 성장성 2. 수익성 3. 안정성 4. 밸류에이션 5. 종합"
    return _ask(SYSTEM_PROMPT, user_msg, max_tokens=1000)
