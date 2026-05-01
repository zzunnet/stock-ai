"""
Ollama 로컬 LLM 서비스 (저비용 빠른 전처리용)
- 뉴스 요약, 감성 분석, 빠른 종목 스크리닝
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def _is_available() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def quick_sentiment(text: str) -> dict:
    """뉴스/공시 감성 분석"""
    if not _is_available():
        return {"sentiment": "unknown", "score": 0, "reason": "Ollama 미연결"}
    prompt = f"""다음 텍스트의 주식 투자 관점 감성을 분석하세요.
JSON 형태로만 답하세요: {{"sentiment": "positive/negative/neutral", "score": -1.0~1.0, "reason": "한줄이유"}}

텍스트: {text[:500]}"""
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=30)
        response_text = r.json().get("response", "{}")
        import json, re
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"sentiment": "neutral", "score": 0, "reason": response_text[:100]}
    except Exception as e:
        logger.warning("Ollama 감성 분석 실패: %s", e)
        return {"sentiment": "unknown", "score": 0, "reason": str(e)}


def quick_summary(text: str, max_chars: int = 200) -> str:
    """텍스트 빠른 요약"""
    if not _is_available():
        return text[:max_chars]
    prompt = f"다음 내용을 한국어로 {max_chars}자 이내로 요약하세요. 요약만 출력하세요.\n\n{text[:1000]}"
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get("response", text[:max_chars])
    except Exception as e:
        logger.warning("Ollama 요약 실패: %s", e)
        return text[:max_chars]


def screen_stocks(stocks: list, criteria: str) -> list:
    """종목 스크리닝"""
    if not _is_available() or not stocks:
        return stocks[:10]
    stock_list = "\n".join([f"- {s.get('name','')} ({s.get('code','')}): {s.get('change_pct',0):+.2f}%" for s in stocks[:30]])
    prompt = f"""다음 종목들 중 "{criteria}" 조건에 가장 적합한 종목 코드 5개를 JSON 배열로만 답하세요.
예: ["005930", "000660"]

{stock_list}"""
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=30)
        import json, re
        match = re.search(r'\[.*\]', r.json().get("response", "[]"), re.DOTALL)
        if match:
            codes = json.loads(match.group())
            return [s for s in stocks if s.get("code") in codes]
    except Exception as e:
        logger.warning("Ollama 스크리닝 실패: %s", e)
    return stocks[:5]


def get_ollama_status() -> dict:
    """Ollama 연결 상태 확인"""
    if not _is_available():
        return {"available": False, "models": []}
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"available": True, "models": models, "url": OLLAMA_URL}
    except Exception:
        return {"available": False, "models": []}
