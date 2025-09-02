from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime, timezone
import requests, os
from openai import OpenAI

# Взимаме ключовете от Render Environment
API_KEY = os.getenv("API_KEY", "demo123")
ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="Forex Scalp Signals AI", version="1.1.0")

client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------
# Schemas
# --------------------
class GenerateReq(BaseModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    timeframe: Literal["M1", "M5", "M15"]
    lookback: int = 400
    min_confidence: int = 80


class AlphaReq(BaseModel):
    symbol: Literal["EURUSD", "XAUUSD"]
    interval: Literal["1min", "5min", "15min"]
    limit: int = 10


class AnalyzeReq(BaseModel):
    symbol: Literal["EURUSD", "XAUUSD"]
    interval: Literal["1min", "5min", "15min"]
    candles: Optional[int] = 20


@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------
# Dummy generate (стария, за тестове)
# --------------------
@app.post("/generate")
def generate(req: GenerateReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "direction": "long",
        "entry": 1.2345,
        "sl": 1.2300,
        "tp1": 1.2380,
        "tp2": 1.2400,
        "tp3": 1.2450,
        "confidence": 90,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# --------------------
# Ново: взимане на свещи от Alpha Vantage
# --------------------
@app.post("/candles_alpha")
def candles_alpha(req: AlphaReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": "EUR" if req.symbol == "EURUSD" else "XAU",
        "to_symbol": "USD",
        "interval": req.interval,
        "apikey": ALPHA_API_KEY
    }
    r = requests.get(url, params=params)
    data = r.json()

    if "Time Series FX" not in data:
        raise HTTPException(status_code=500, detail="Alpha Vantage error")

    candles = []
    for ts, values in list(data[f"Time Series FX ({req.interval})"].items())[:req.limit]:
        candles.append({
            "time": ts,
            "open": float(values["1. open"]),
            "high": float(values["2. high"]),
            "low": float(values["3. low"]),
            "close": float(values["4. close"])
        })

    return {"symbol": req.symbol, "interval": req.interval, "candles": candles}


# --------------------
# Ново: AI анализ със свещите
# --------------------
@app.post("/llm_analyze")
def llm_analyze(req: AnalyzeReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Взимаме последните свещи
    candles_resp = candles_alpha(AlphaReq(symbol=req.symbol, interval=req.interval, limit=req.candles), x_api_key=API_KEY)
    candles = candles_resp["candles"]

    # Подготвяме текст за LLM
    candle_text = "\n".join([f"{c['time']} O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']}" for c in candles])

    prompt = f"""
    Analyze the following forex candlesticks for {req.symbol} ({req.interval}):
    {candle_text}

    Based on the data, provide a trading signal with:
    - Direction (long/short)
    - Entry
    - Stop Loss
    - Take Profits (3 levels)
    - Confidence % (0-100)
    - Rationale in 1-2 sentences
    """

    # Извикваме OpenAI
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional forex analyst generating scalp signals."},
            {"role": "user", "content": prompt}
        ]
    )

    return {"symbol": req.symbol, "interval": req.interval, "analysis": completion.choices[0].message.content}
