from fastapi import APIRouter, HTTPException, Query

from services import stock_data

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/list")
def stock_list(market: str = Query("KOSPI", description="KOSPI | KOSDAQ | KRX")):
    try:
        return stock_data.get_stock_list(market.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/ohlcv/{ticker}")
def ohlcv(ticker: str, days: int = Query(90, ge=10, le=500)):
    try:
        return {"ticker": ticker, "data": stock_data.get_ohlcv(ticker, days)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/info/{ticker}")
def stock_info(ticker: str):
    return stock_data.get_stock_info(ticker)


@router.get("/indices")
def market_indices():
    try:
        return stock_data.get_market_indices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sector/{sector}")
def sector_stocks(sector: str, limit: int = Query(10, ge=1, le=30)):
    try:
        return {"sector": sector, "stocks": stock_data.get_sector_stocks(sector, limit)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
