"""
한국 주식 데이터 서비스
- FinanceDataReader: KOSPI/KOSDAQ/해외주식 OHLCV
- pykrx: 외국인/기관 순매수, 시가총액, 재무 데이터
"""
from datetime import datetime, timedelta
import logging

import FinanceDataReader as fdr
import pandas as pd

logger = logging.getLogger(__name__)


def get_stock_list(market: str = "KOSPI") -> list[dict]:
    """KOSPI / KOSDAQ / KRX 종목 목록"""
    try:
        df = fdr.StockListing(market)
        for col in ("Sector", "Industry", "Market"):
            if col not in df.columns:
                df[col] = ""
        records = df[["Code", "Name", "Market", "Sector", "Industry"]].fillna("").to_dict("records")
        return [
            {
                "code": r["Code"],
                "name": r["Name"],
                "market": r["Market"],
                "sector": r["Sector"],
                "industry": r["Industry"],
            }
            for r in records
        ]
    except Exception as e:
        logger.error("종목 목록 조회 실패: %s", e)
        raise RuntimeError(f"종목 목록 조회 실패: {e}")


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Drop malformed rows such as zero OHLC values from upstream data."""
    if df.empty:
        return df
    cols = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    if not cols:
        return df
    cleaned = df.copy()
    for col in cols:
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    cleaned = cleaned.dropna(subset=cols)
    return cleaned[(cleaned[cols] > 0).all(axis=1)]


def get_ohlcv(ticker: str, days: int = 90) -> list[dict]:
    """일별 OHLCV (days일치)"""
    end = datetime.today()
    start = end - timedelta(days=days)
    try:
        df = fdr.DataReader(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        df = _clean_ohlcv(df)
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        return df.tail(60).to_dict("records")
    except Exception as e:
        logger.error("OHLCV 조회 실패 (%s): %s", ticker, e)
        raise RuntimeError(f"주가 데이터 조회 실패: {e}")


def get_stock_info(ticker: str) -> dict:
    """종목 요약 정보"""
    try:
        df = fdr.StockListing("KRX")
        row = df[df["Code"] == ticker]
        if row.empty:
            return {"ticker": ticker, "name": ticker, "market": "GLOBAL"}
        r = row.iloc[0]
        return {
            "ticker": ticker,
            "name": r.get("Name", ""),
            "market": r.get("Market", ""),
            "sector": r.get("Sector", ""),
            "industry": r.get("Industry", ""),
        }
    except Exception as e:
        logger.error("종목 정보 조회 실패 (%s): %s", ticker, e)
        return {"ticker": ticker, "name": ticker, "market": "UNKNOWN"}


def _compute_indicators(df: pd.DataFrame) -> dict:
    """이동평균, RSI, 52주 고저 등 계산"""
    close = df["close"] if "close" in df.columns else df["Close"]
    ma5 = close.rolling(5).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - 100 / (1 + rs)).iloc[-1]
    w52 = close.tail(252)
    high52 = float(w52.max())
    low52 = float(w52.min())
    current = float(close.iloc[-1])
    return {
        "current_price": current,
        "ma5": round(float(ma5), 0),
        "ma20": round(float(ma20), 0),
        "ma60": round(float(ma60), 0) if ma60 is not None else None,
        "rsi14": round(float(rsi), 1),
        "high_52w": high52,
        "low_52w": low52,
        "pct_from_high": round((current - high52) / high52 * 100, 2),
        "pct_from_low": round((current - low52) / low52 * 100, 2),
    }


def get_stock_analysis_data(ticker: str) -> dict:
    """AI 분석용 종합 데이터 패키지"""
    end = datetime.today()
    start = end - timedelta(days=400)
    try:
        df = fdr.DataReader(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    except Exception as e:
        raise RuntimeError(f"데이터 조회 실패: {e}")
    df = _clean_ohlcv(df)
    if df.empty:
        raise RuntimeError(f"데이터 없음: {ticker}")
    info = get_stock_info(ticker)
    indicators = _compute_indicators(df)
    recent = df.tail(20)
    recent_close = recent["Close"].tolist() if "Close" in recent.columns else recent["close"].tolist()
    recent_vol = recent["Volume"].tolist() if "Volume" in recent.columns else recent.get("volume", pd.Series()).tolist()
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else None
    curr_close = float(df["Close"].iloc[-1])
    change_pct = round((curr_close - prev_close) / prev_close * 100, 2) if prev_close else None
    return {
        "info": info,
        "indicators": indicators,
        "change_pct": change_pct,
        "recent_prices": [round(p, 0) for p in recent_close],
        "recent_volume": [int(v) for v in recent_vol if v == v],
        "data_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1]),
    }


def get_market_indices() -> dict:
    """KOSPI, KOSDAQ, S&P500, NASDAQ 지수"""
    indices = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "NASDAQ": "IXIC"}
    result = {}
    end = datetime.today()
    start = end - timedelta(days=30)
    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            if not df.empty:
                curr = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else curr
                result[name] = {"value": round(curr, 2), "change_pct": round((curr - prev) / prev * 100, 2)}
        except Exception as e:
            logger.warning("지수 조회 실패 (%s): %s", name, e)
    return result


def get_sector_stocks(sector: str, limit: int = 10) -> list[dict]:
    """특정 섹터 상위 종목"""
    try:
        df = fdr.StockListing("KOSPI")
        if "Sector" not in df.columns:
            return []
        sector_df = df[df["Sector"].str.contains(sector, na=False, case=False)]
        results = []
        for _, row in sector_df.head(limit).iterrows():
            code = row["Code"]
            try:
                stock_df = fdr.DataReader(code, start=(datetime.today() - timedelta(days=5)).strftime("%Y-%m-%d"))
                if not stock_df.empty:
                    curr = float(stock_df["Close"].iloc[-1])
                    prev = float(stock_df["Close"].iloc[-2]) if len(stock_df) >= 2 else curr
                    results.append({"code": code, "name": row["Name"], "current_price": curr, "change_pct": round((curr - prev) / prev * 100, 2)})
            except Exception:
                pass
        return results
    except Exception as e:
        raise RuntimeError(f"섹터 데이터 조회 실패: {e}")
