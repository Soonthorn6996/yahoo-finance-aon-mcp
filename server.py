"""
Yahoo Finance MCP Server — Remote / Cloud Version
==================================================
Transport : HTTP + SSE (Server-Sent Events)
Deploy on : Railway, Render, or any cloud platform

Requirements:
  pip install mcp yfinance pandas starlette uvicorn
"""
import os 
import json
import logging
import sys
import warnings
from typing import Any

import pandas as pd
import uvicorn
import yfinance as yf
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

# ─────────────────────────────────────────────
# Suppress all stdout noise
# ─────────────────────────────────────────────
warnings.filterwarnings("ignore")
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
for logger_name in ("yfinance", "peewee", "urllib3", "httpx"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# ─────────────────────────────────────────────
app = Server("yahoo-finance-mcp")
# ─────────────────────────────────────────────


# ══════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════
def _to_json(obj: Any) -> str:
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
        description="ดึงราคาหุ้น Real-time หรือ Historical OHLCV เช่น AAPL, PTT.BK",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol":   {"type": "string",  "description": "Ticker เช่น 'AAPL', 'PTT.BK'"},
                "period":   {"type": "string",  "description": "1d 5d 1mo 3mo 6mo 1y 2y 5y max", "default": "1mo"},
                "interval": {"type": "string",  "description": "1m 5m 15m 1h 1d 1wk 1mo",        "default": "1d"},
                "realtime": {"type": "boolean", "description": "True = ราคาล่าสุดเดียว",          "default": False},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_technical_indicators",
        description="คำนวณ RSI, MACD, EMA, Bollinger Bands",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol":      {"type": "string", "description": "Ticker เช่น 'AAPL', 'BTC-USD'"},
                "period":      {"type": "string", "description": "ช่วงเวลา เช่น 3mo 6mo 1y", "default": "6mo"},
                "indicators":  {"type": "array",  "items": {"type": "string"}, "default": ["RSI","MACD","EMA","BB"]},
                "ema_periods": {"type": "array",  "items": {"type": "integer"}, "default": [9, 20, 50, 200]},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_company_info",
        description="ดึงข้อมูลบริษัท: profile, financials, balance_sheet, cashflow, all",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol":    {"type": "string", "description": "Ticker เช่น 'AAPL', 'PTT.BK'"},
                "info_type": {"type": "string", "description": "profile | financials | balance_sheet | cashflow | all", "default": "profile"},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_crypto",
        description="ดึงข้อมูล Crypto เช่น BTC-USD, ETH-USD",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol":   {"type": "string",  "description": "เช่น 'BTC-USD', 'ETH-USD'"},
                "period":   {"type": "string",  "description": "1d 7d 1mo 3mo 6mo 1y", "default": "1mo"},
                "interval": {"type": "string",  "description": "1h 1d 1wk",             "default": "1d"},
                "realtime": {"type": "boolean", "description": "True = ราคาล่าสุด",     "default": False},
            },
            "required": ["symbol"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


# ══════════════════════════════════════════════
# Tool Handlers
# ══════════════════════════════════════════════
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── get_stock_price ─────────────────────────
    if name == "get_stock_price":
        symbol   = arguments["symbol"].upper()
        period   = arguments.get("period", "1mo")
        interval = arguments.get("interval", "1d")
        realtime = arguments.get("realtime", False)
        ticker   = yf.Ticker(symbol)

        if realtime:
            info = ticker.fast_info
            return _ok({"symbol": symbol, "last_price": info.last_price,
                        "previous_close": info.previous_close,
                        "market_cap": info.market_cap, "currency": info.currency})

        hist = ticker.history(period=period, interval=interval)
        return _ok(hist[["Open","High","Low","Close","Volume"]]) if not hist.empty else _err(f"ไม่พบข้อมูล {symbol}")

    # ── get_technical_indicators ────────────────
    elif name == "get_technical_indicators":
        symbol      = arguments["symbol"].upper()
        period      = arguments.get("period", "6mo")
        indicators  = [i.upper() for i in arguments.get("indicators", ["RSI","MACD","EMA","BB"])]
        ema_periods = arguments.get("ema_periods", [9, 20, 50, 200])

        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty:
            return _err(f"ไม่พบข้อมูล {symbol}")

        close = hist["Close"]
        df    = pd.DataFrame({"Close": close}, index=hist.index)

        if "RSI" in indicators:
            delta = close.diff()
            avg_g = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
            avg_l = (-delta).clip(lower=0).ewm(com=13, adjust=False).mean()
            df["RSI_14"] = 100 - (100 / (1 + avg_g / avg_l))

        if "MACD" in indicators:
            macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            df["MACD"]        = macd_line
            df["MACD_Signal"] = macd_line.ewm(span=9, adjust=False).mean()
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

        return _ok(df.dropna(how="all").tail(100))

    # ── get_company_info ────────────────────────
    elif name == "get_company_info":
        symbol    = arguments["symbol"].upper()
        info_type = arguments.get("info_type", "profile")
        ticker    = yf.Ticker(symbol)

        if info_type == "profile":
            raw  = ticker.info
            keys = ["longName","sector","industry","country","fullTimeEmployees","website",
                    "businessSummary","marketCap","trailingPE","forwardPE","dividendYield",
                    "beta","recommendationKey","targetMeanPrice"]
            return _ok({k: raw.get(k) for k in keys if raw.get(k) is not None})

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
                "profile":       {k: raw.get(k) for k in ["longName","sector","industry","country",
                                   "marketCap","trailingPE","beta","recommendationKey"] if raw.get(k)},
                "financials":    ticker.financials.to_dict()    if not ticker.financials.empty    else {},
                "balance_sheet": ticker.balance_sheet.to_dict() if not ticker.balance_sheet.empty else {},
                "cashflow":      ticker.cashflow.to_dict()      if not ticker.cashflow.empty      else {},
            })
        return _err(f"info_type '{info_type}' ไม่ถูกต้อง")

    # ── get_crypto ──────────────────────────────
    elif name == "get_crypto":
        symbol   = arguments["symbol"].upper()
        period   = arguments.get("period", "1mo")
        interval = arguments.get("interval", "1d")
        realtime = arguments.get("realtime", False)
        if "-" not in symbol:
            symbol = f"{symbol}-USD"
        ticker = yf.Ticker(symbol)

        if realtime:
            info = ticker.fast_info
            return _ok({"symbol": symbol, "last_price": info.last_price,
                        "currency": info.currency, "market_cap": info.market_cap})

        hist = ticker.history(period=period, interval=interval)
        return _ok(hist[["Open","High","Low","Close","Volume"]]) if not hist.empty else _err(f"ไม่พบข้อมูล {symbol}")

    return _err(f"ไม่พบ tool '{name}'")


# ══════════════════════════════════════════════
# SSE Transport (HTTP Server)
# ══════════════════════════════════════════════
sse = SseServerTransport("/messages/")


async def handle_sse(request: Request) -> Response:
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())
    return Response()


starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
        Route("/health", endpoint=lambda r: Response("OK")),   # health check
    ]
)

# ══════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Yahoo Finance MCP Server running on port {port}", file=sys.stderr)
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)