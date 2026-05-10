from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.stocks import _ticker_counters
from services import claude_ai, stock_data, ollama_ai

router = APIRouter(prefix="/api/ai", tags=["ai"])

_stock_briefing_cache: dict = {}


class StockAnalysisRequest(BaseModel):
    ticker: str


class MarketOverviewRequest(BaseModel):
    pass


class SectorAnalysisRequest(BaseModel):
    sector: str


class PortfolioHolding(BaseModel):
    ticker: str
    name: str
    avg_price: float
    current_price: float
    quantity: int

    @property
    def current_value(self) -> float:
        return self.current_price * self.quantity

    @property
    def return_pct(self) -> float:
        return (self.current_price - self.avg_price) / self.avg_price * 100


class PortfolioReviewRequest(BaseModel):
    holdings: list[PortfolioHolding]


class SentimentRequest(BaseModel):
    text: str


@router.post("/stock-analysis")
def stock_analysis(req: StockAnalysisRequest):
    _ticker_counters[req.ticker] += 1
    try:
        data = stock_data.get_stock_analysis_data(req.ticker)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"데이터 조회 실패: {e}")
    cache_key = (req.ticker, data.get("data_date", ""))
    if cache_key in _stock_briefing_cache:
        result = _stock_briefing_cache[cache_key]
    else:
        try:
            result = claude_ai.stock_analysis(req.ticker, data)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 분석 오류: {e}")
        _stock_briefing_cache[cache_key] = result
    return {
        "result": result,
        "ticker": req.ticker,
        "name": data["info"].get("name", req.ticker),
        "current_price": data["indicators"]["current_price"],
        "change_pct": data.get("change_pct"),
        "briefing_type": "stock_movement",
        "disclaimer": "투자자문이 아닌 정보 브리핑입니다.",
    }


@router.post("/market-overview")
def market_overview(req: MarketOverviewRequest):
    try:
        indices = stock_data.get_market_indices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"지수 조회 실패: {e}")
    if not indices:
        raise HTTPException(status_code=503, detail="시장 지수 데이터 없음")
    try:
        result = claude_ai.market_overview(indices)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {e}")
    return {"result": result, "indices": indices}


@router.post("/sector-analysis")
def sector_analysis(req: SectorAnalysisRequest):
    try:
        stocks = stock_data.get_sector_stocks(req.sector, limit=10)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"섹터 데이터 조회 실패: {e}")
    if not stocks:
        raise HTTPException(status_code=404, detail=f"섹터 '{req.sector}' 종목 없음")
    try:
        result = claude_ai.sector_analysis(req.sector, stocks)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {e}")
    return {"result": result, "sector": req.sector, "stocks": stocks}


@router.post("/portfolio-review")
def portfolio_review(req: PortfolioReviewRequest):
    holdings_data = [{"ticker": h.ticker, "name": h.name, "avg_price": h.avg_price, "current_price": h.current_price, "quantity": h.quantity, "current_value": h.current_value, "return_pct": h.return_pct} for h in req.holdings]
    try:
        result = claude_ai.portfolio_review(holdings_data)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {e}")
    total_value = sum(h["current_value"] for h in holdings_data)
    total_return = sum((h["return_pct"] * h["current_value"]) for h in holdings_data) / total_value if total_value else 0
    return {"result": result, "total_value": total_value, "total_return_pct": round(total_return, 2), "holdings_count": len(holdings_data)}


@router.post("/sentiment")
def sentiment_analysis(req: SentimentRequest):
    """Ollama 로컬 LLM으로 빠른 감성 분석 (무료)"""
    return ollama_ai.quick_sentiment(req.text)


@router.get("/ollama-status")
def ollama_status():
    return ollama_ai.get_ollama_status()


@router.get("/engine-status")
def engine_status():
    return claude_ai.get_engine_status()
