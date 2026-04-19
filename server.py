"""
Yahoo Finance MCP Server — FastMCP Version
==========================================
ใช้ FastMCP สำหรับ SSE transport ที่ compatible กว่า

Requirements:
  pip install mcp yfinance pandas
"""

import json
import logging
import os
import sys
import warnings
from typing import Any

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP

# ─────────────────────────────────────────────
# Suppress stdout noise
# ─────────────────────────────────────────────
warnings.filterwarnings("ignore")
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
for name in ("yfinance", "peewee", "urllib3", "httpx"):
    logging.getLogger(name).setLevel(logging.CRITICAL)

# ─────────────────────────────────────────────
port = int(os.environ.get("PORT", 8080))
mcp  = FastMCP("efin-data", port=port)
# ─────────────────────────────────────────────


def _to_json(obj: Any) -> str:
    if isinstance(obj, pd.DataFrame):
        obj = obj.reset_index()
        obj.columns = [str(c) for c in obj.columns]
        return obj.to_json(orient="records", date_format="iso", indent=2)
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


# ══════════════════════════════════════════════
# Tools
# ══════════════════════════════════════════════

@mcp.tool()
def get_stock_price(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
    realtime: bool = False,
) -> str:
    """ดึงราคาหุ้น Real-time หรือ Historical OHLCV เช่น AAPL, PTT.BK, KBANK.BK"""
    ticker = yf.Ticker(symbol.upper())
    if realtime:
        info = ticker.fast_info
        return _to_json({
            "symbol":         symbol.upper(),
            "last_price":     info.last_price,
            "previous_close": info.previous_close,
            "market_cap":     info.market_cap,
            "currency":       info.currency,
        })
    hist = ticker.history(period=period, interval=interval)
    if hist.empty:
        return json.dumps({"error": f"ไม่พบข้อมูล {symbol}"})
    return _to_json(hist[["Open", "High", "Low", "Close", "Volume"]])


@mcp.tool()
def get_technical_indicators(
    symbol: str,
    period: str = "6mo",
    indicators: list[str] = ["RSI", "MACD", "EMA", "BB"],
    ema_periods: list[int] = [9, 20, 50, 200],
) -> str:
    """คำนวณ RSI, MACD, EMA, Bollinger Bands สำหรับหุ้นหรือ crypto"""
    hist = yf.Ticker(symbol.upper()).history(period=period)
    if hist.empty:
        return json.dumps({"error": f"ไม่พบข้อมูล {symbol}"})

    close      = hist["Close"]
    indicators = [i.upper() for i in indicators]
    df         = pd.DataFrame({"Close": close}, index=hist.index)

    if "RSI" in indicators:
        delta = close.diff()
        avg_g = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_l = (-delta).clip(lower=0).ewm(com=13, adjust=False).mean()
        df["RSI_14"] = 100 - (100 / (1 + avg_g / avg_l))

    if "MACD" in indicators:
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        df["MACD"]        = macd
        df["MACD_Signal"] = macd.ewm(span=9, adjust=False).mean()
        df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

    if "EMA" in indicators:
        for p in ema_periods:
            df[f"EMA_{p}"] = close.ewm(span=p, adjust=False).mean()

    if "BB" in indicators:
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        df["BB_Upper"]  = sma + 2 * std
        df["BB_Middle"] = sma
        df["BB_Lower"]  = sma - 2 * std

    return _to_json(df.dropna(how="all").tail(100))


@mcp.tool()
def get_company_info(
    symbol: str,
    info_type: str = "profile",
) -> str:
    """ดึงข้อมูลบริษัท: profile | financials | balance_sheet | cashflow | all"""
    ticker = yf.Ticker(symbol.upper())

    if info_type == "profile":
        raw  = ticker.info
        keys = ["longName", "sector", "industry", "country", "fullTimeEmployees",
                "website", "businessSummary", "marketCap", "trailingPE", "forwardPE",
                "dividendYield", "beta", "recommendationKey", "targetMeanPrice"]
        return _to_json({k: raw.get(k) for k in keys if raw.get(k) is not None})

    elif info_type == "financials":
        df = ticker.financials
        return _to_json(df) if not df.empty else json.dumps({"error": "ไม่มีข้อมูล"})

    elif info_type == "balance_sheet":
        df = ticker.balance_sheet
        return _to_json(df) if not df.empty else json.dumps({"error": "ไม่มีข้อมูล"})

    elif info_type == "cashflow":
        df = ticker.cashflow
        return _to_json(df) if not df.empty else json.dumps({"error": "ไม่มีข้อมูล"})

    elif info_type == "all":
        raw = ticker.info
        return _to_json({
            "profile":       {k: raw.get(k) for k in ["longName","sector","industry",
                               "country","marketCap","trailingPE","beta","recommendationKey"] if raw.get(k)},
            "financials":    ticker.financials.to_dict()    if not ticker.financials.empty    else {},
            "balance_sheet": ticker.balance_sheet.to_dict() if not ticker.balance_sheet.empty else {},
            "cashflow":      ticker.cashflow.to_dict()      if not ticker.cashflow.empty      else {},
        })

    return json.dumps({"error": f"info_type '{info_type}' ไม่ถูกต้อง"})


@mcp.tool()
def get_crypto(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
    realtime: bool = False,
) -> str:
    """ดึงข้อมูล Cryptocurrency เช่น BTC-USD, ETH-USD, BNB-USD"""
    if "-" not in symbol:
        symbol = f"{symbol.upper()}-USD"
    ticker = yf.Ticker(symbol.upper())

    if realtime:
        info = ticker.fast_info
        return _to_json({
            "symbol":     symbol.upper(),
            "last_price": info.last_price,
            "currency":   info.currency,
            "market_cap": info.market_cap,
        })

    hist = ticker.history(period=period, interval=interval)
    if hist.empty:
        return json.dumps({"error": f"ไม่พบข้อมูล {symbol}"})
    return _to_json(hist[["Open", "High", "Low", "Close", "Volume"]])


# ══════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print(f"🚀 efin-data MCP Server running on port {port}", file=sys.stderr)
    mcp.run()