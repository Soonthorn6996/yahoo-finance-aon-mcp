"""
Yahoo Finance MCP Server
========================
Tools:
  - get_stock_price        : Real-time & historical OHLCV
  - get_technical_indicators: RSI, MACD, EMA, Bollinger Bands
  - get_company_info       : Profile, Financials, Balance Sheet, Cash Flow
  - get_crypto             : Crypto real-time & historical price

Requirements (NO pandas-ta needed — works on Python 3.14+):
  pip install mcp yfinance pandas
"""

import json
from typing import Any

import pandas as pd
import yfinance as yf
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ─────────────────────────────────────────────
app = Server("yahoo-finance-mcp")
# ─────────────────────────────────────────────


# ══════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════
def _to_json(obj: Any) -> str:
    """Convert DataFrames / dicts / lists to a clean JSON string."""
    if isinstance(obj, pd.DataFrame):
        obj = obj.reset_index()
        obj.columns = [str(c) for c in obj.columns]
        return obj.to_json(orient="records", date_format="iso", indent=2)
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _ok(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=_to_json(data))]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}))]


# ══════════════════════════════════════════════
# Tool Definitions
# ══════════════════════════════════════════════
TOOLS: list[Tool] = [
    Tool(
        name="get_stock_price",
        description=(
            "ดึงราคาหุ้น Real-time (ปัจจุบัน) หรือ Historical OHLCV "
            "เช่น AAPL, MSFT, PTT.BK, KBANK.BK"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker เช่น 'AAPL', 'PTT.BK'",
                },
                "period": {
                    "type": "string",
                    "description": "ช่วงเวลา: 1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max",
                    "default": "1mo",
                },
                "interval": {
                    "type": "string",
                    "description": "ความถี่: 1m 5m 15m 30m 1h 1d 1wk 1mo",
                    "default": "1d",
                },
                "realtime": {
                    "type": "boolean",
                    "description": "True = ราคาล่าสุดอย่างเดียว, False = ข้อมูล OHLCV",
                    "default": False,
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_technical_indicators",
        description=(
            "คำนวณ Technical Indicators: RSI, MACD, EMA, Bollinger Bands "
            "สำหรับหุ้นหรือ crypto ใดก็ได้"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker เช่น 'AAPL', 'BTC-USD'",
                },
                "period": {
                    "type": "string",
                    "description": "ช่วงเวลาที่ดึงข้อมูล เช่น 3mo, 6mo, 1y",
                    "default": "6mo",
                },
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "รายการ indicator: ['RSI','MACD','EMA','BB']",
                    "default": ["RSI", "MACD", "EMA", "BB"],
                },
                "ema_periods": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "EMA periods เช่น [9, 20, 50, 200]",
                    "default": [9, 20, 50, 200],
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_company_info",
        description=(
            "ดึงข้อมูลบริษัท: Profile, Financials (Income Statement), "
            "Balance Sheet, Cash Flow Statement"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker เช่น 'AAPL', 'PTT.BK'",
                },
                "info_type": {
                    "type": "string",
                    "description": (
                        "ประเภทข้อมูล: "
                        "'profile' (ข้อมูลทั่วไป), "
                        "'financials' (Income Statement), "
                        "'balance_sheet', "
                        "'cashflow', "
                        "'all' (ทั้งหมด)"
                    ),
                    "default": "profile",
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_crypto",
        description=(
            "ดึงข้อมูล Cryptocurrency เช่น BTC, ETH, BNB "
            "ทั้งราคาปัจจุบัน และ Historical"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Crypto ticker เช่น 'BTC-USD', 'ETH-USD', 'BNB-USD'",
                },
                "period": {
                    "type": "string",
                    "description": "ช่วงเวลา: 1d 7d 1mo 3mo 6mo 1y",
                    "default": "1mo",
                },
                "interval": {
                    "type": "string",
                    "description": "ความถี่: 1h 1d 1wk",
                    "default": "1d",
                },
                "realtime": {
                    "type": "boolean",
                    "description": "True = ราคาล่าสุดอย่างเดียว",
                    "default": False,
                },
            },
            "required": ["symbol"],
        },
    ),
]


# ══════════════════════════════════════════════
# List Tools
# ══════════════════════════════════════════════
@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


# ══════════════════════════════════════════════
# Call Tool
# ══════════════════════════════════════════════
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── 1. get_stock_price ──────────────────────
    if name == "get_stock_price":
        symbol   = arguments["symbol"].upper()
        period   = arguments.get("period", "1mo")
        interval = arguments.get("interval", "1d")
        realtime = arguments.get("realtime", False)

        ticker = yf.Ticker(symbol)

        if realtime:
            info = ticker.fast_info
            result = {
                "symbol":        symbol,
                "last_price":    info.last_price,
                "previous_close":info.previous_close,
                "market_cap":    info.market_cap,
                "currency":      info.currency,
            }
            return _ok(result)

        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return _err(f"ไม่พบข้อมูลสำหรับ {symbol}")
        return _ok(hist[["Open", "High", "Low", "Close", "Volume"]])

    # ── 2. get_technical_indicators ─────────────
    elif name == "get_technical_indicators":
        symbol      = arguments["symbol"].upper()
        period      = arguments.get("period", "6mo")
        indicators  = [i.upper() for i in arguments.get("indicators", ["RSI","MACD","EMA","BB"])]
        ema_periods = arguments.get("ema_periods", [9, 20, 50, 200])

        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return _err(f"ไม่พบข้อมูลสำหรับ {symbol}")

        close = hist["Close"]
        result_df = pd.DataFrame(index=hist.index)
        result_df["Close"] = close

        # ── RSI (14) ──────────────────────────────
        if "RSI" in indicators:
            delta   = close.diff()
            gain    = delta.clip(lower=0)
            loss    = (-delta).clip(lower=0)
            avg_g   = gain.ewm(com=13, adjust=False).mean()
            avg_l   = loss.ewm(com=13, adjust=False).mean()
            rs      = avg_g / avg_l
            result_df["RSI_14"] = 100 - (100 / (1 + rs))

        # ── MACD (12/26/9) ────────────────────────
        if "MACD" in indicators:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line   = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            result_df["MACD"]        = macd_line
            result_df["MACD_Signal"] = signal_line
            result_df["MACD_Hist"]   = macd_line - signal_line

        # ── EMA ───────────────────────────────────
        if "EMA" in indicators:
            for p in ema_periods:
                result_df[f"EMA_{p}"] = close.ewm(span=p, adjust=False).mean()

        # ── Bollinger Bands (20, ±2σ) ─────────────
        if "BB" in indicators:
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            result_df["BB_Upper"]  = sma20 + 2 * std20
            result_df["BB_Middle"] = sma20
            result_df["BB_Lower"]  = sma20 - 2 * std20

        return _ok(result_df.dropna(how="all").tail(100))

    # ── 3. get_company_info ─────────────────────
    elif name == "get_company_info":
        symbol    = arguments["symbol"].upper()
        info_type = arguments.get("info_type", "profile")
        ticker    = yf.Ticker(symbol)

        if info_type == "profile":
            raw = ticker.info
            keys = [
                "longName","sector","industry","country","fullTimeEmployees",
                "website","businessSummary","marketCap","trailingPE",
                "forwardPE","dividendYield","52WeekChange","beta",
                "recommendationKey","targetMeanPrice",
            ]
            result = {k: raw.get(k) for k in keys if raw.get(k) is not None}
            return _ok(result)

        elif info_type == "financials":
            df = ticker.financials
            return _ok(df) if not df.empty else _err("ไม่มีข้อมูล Financials")

        elif info_type == "balance_sheet":
            df = ticker.balance_sheet
            return _ok(df) if not df.empty else _err("ไม่มีข้อมูล Balance Sheet")

        elif info_type == "cashflow":
            df = ticker.cashflow
            return _ok(df) if not df.empty else _err("ไม่มีข้อมูล Cash Flow")

        elif info_type == "all":
            raw = ticker.info
            return _ok({
                "profile":       {k: raw.get(k) for k in ["longName","sector","industry",
                                   "country","marketCap","trailingPE","forwardPE",
                                   "dividendYield","beta","recommendationKey"] if raw.get(k)},
                "financials":    ticker.financials.to_dict()    if not ticker.financials.empty    else {},
                "balance_sheet": ticker.balance_sheet.to_dict() if not ticker.balance_sheet.empty else {},
                "cashflow":      ticker.cashflow.to_dict()      if not ticker.cashflow.empty      else {},
            })

        return _err(f"info_type '{info_type}' ไม่ถูกต้อง")

    # ── 4. get_crypto ───────────────────────────
    elif name == "get_crypto":
        symbol   = arguments["symbol"].upper()
        period   = arguments.get("period", "1mo")
        interval = arguments.get("interval", "1d")
        realtime = arguments.get("realtime", False)

        # Auto-append -USD if not present
        if "-" not in symbol:
            symbol = f"{symbol}-USD"

        ticker = yf.Ticker(symbol)

        if realtime:
            info = ticker.fast_info
            return _ok({
                "symbol":     symbol,
                "last_price": info.last_price,
                "currency":   info.currency,
                "market_cap": info.market_cap,
            })

        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return _err(f"ไม่พบข้อมูลสำหรับ {symbol}")
        return _ok(hist[["Open", "High", "Low", "Close", "Volume"]])

    return _err(f"ไม่พบ tool ชื่อ '{name}'")


# ══════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())