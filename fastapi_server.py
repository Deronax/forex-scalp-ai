from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, conlist
from typing import Literal
from datetime import datetime, timezone
import random, os, json, requests

# ──────────────────────────────────────────────────────────────────────────────
# ENV / CONFIG
# ──────────────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("API_KEY", "demo123")              # <— сложи си го в Render
ALPHA_API_KEY = os.environ.get("ALPHA_API_KEY")             # <— вече го добави
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")           # <— добави го в Render

# OpenAI клиент (lazy import)
try:
    from openai import OpenAI
    oai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    oai = None

app = FastAPI(title="Forex Scalp Signals AI", version="1.2.0")


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return round(reward / risk, 2) if risk else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────────
# PLACEHOLDER /generate (оставено както беше, но ползва ENV API_KEY)
# ──────────────────────────────────────────────────────────────────────────────
class GenerateReq(BaseModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    timeframe: Literal["M1", "M5", "M15"]
    lookback: int = 400
    session_filter: bool = True
    min_rr: float = 1.5
    min_confidence: int = 85
    news_block_minutes: int = 30

@app.post("/generate")
def generate(req: GenerateReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # synthetic placeholder
    tick = 0.01 if req.symbol == "XAUUSD" else 0.0001
    risk_ticks = {"M1": 20, "M5": 30, "M15": 40}[req.timeframe]
    ref = 2410.0 if req.symbol == "XAUUSD" else 1.0850
    direction = random.choice(["long", "short"])
    entry = ref + random.randint(-50, 50) * tick
    if direction == "long":
        sl = entry - risk_ticks * tick
        tp1 = entry + risk_ticks * tick
        tp2 = entry + int(risk_ticks * 1.5) * tick
        tp3 = entry + int(risk_ticks * 2.5) * tick
    else:
        sl = entry + risk_ticks * tick
        tp1 = entry - risk_ticks * tick
        tp2 = entry - int(risk_ticks * 1.5) * tick
        tp3 = entry - int(risk_ticks * 2.5) * tick
    rr2 = rr(entry, sl, tp2)
    conf = 70 + random.randint(0, 20)
    if rr2 < req.min_rr or conf < req.min_confidence:
        return Response(status_code=204)
    return {
        "symbol": req.symbol, "timeframe": req.timeframe, "direction": direction,
        "entry": round(entry, 5), "sl": round(sl, 5),
        "tp1": round(tp1, 5), "tp2": round(tp2, 5), "tp3": round(tp3, 5),
        "rr_tp1": rr(entry, sl, tp1), "rr_tp2": rr2, "rr_tp3": rr(entry, sl, tp3),
        "confidence": conf,
        "valid_minutes": 30 if req.timeframe == "M5" else 15 if req.timeframe == "M1" else 60,
        "be_on_tp1": True, "news_ok": True, "news_note": "",
        "rationale": "Placeholder scalp setup. Manage 50/30/20; move SL to BE at TP1.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ──────────────────────────────────────────────────────────────────────────────
# NEW: /candles_alpha – свещи от Alpha Vantage (за XAUUSD/EURUSD)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/candles_alpha")
def get_candles(
    symbol: str = Query("EURUSD", description="e.g. EURUSD or XAUUSD"),
    interval: str = Query("5min", description="1min | 5min | 15min"),
    limit: int = Query(120, description="candles to return (max ~500)")
):
    if not ALPHA_API_KEY:
        raise HTTPException(status_code=500, detail="Missing ALPHA_API_KEY")

    if len(symbol) != 6:
        raise HTTPException(status_code=400, detail="Symbol must be 6 letters, e.g. EURUSD")

    from_symbol, to_symbol = symbol[:3], symbol[3:]
    url = (
        "https://www.alphavantage.co/query?"
        f"function=FX_INTRADAY&from_symbol={from_symbol}&to_symbol={to_symbol}"
        f"&interval={interval}&outputsize=compact&apikey={ALPHA_API_KEY}"
    )

    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Alpha Vantage request failed")

    data = r.json()
    key = f"Time Series FX ({interval})"
    if key not in data:
        # когато лимитът е ударен, Alpha Vantage връща Note/Error
        raise HTTPException(status_code=502, detail=f"Unexpected response: {data}")

    candles = []
    for ts, v in data[key].items():
        candles.append({
            "ts": ts,
            "open": float(v["1. open"]),
            "high": float(v["2. high"]),
            "low": float(v["3. low"]),
            "close": float(v["4. close"]),
        })
    candles.sort(key=lambda x: x["ts"])
    return {"symbol": symbol, "interval": interval, "candles": candles[:limit]}


# ──────────────────────────────────────────────────────────────────────────────
# NEW: /llm_analyze – AI анализатор (строги правила + JSON изход)
# ──────────────────────────────────────────────────────────────────────────────
class Candle(BaseModel):
    ts: str
    open: float
    high: float
    low: float
    close: float

class LLMReq(BaseModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    timeframe: Literal["M1", "M5", "M15"]
    candles: conlist(Candle, min_items=60, max_items=800)
    min_rr: float = 1.5
    min_confidence: int = 85
    default_valid_minutes: int = 30

SYSTEM_PROMPT = (
    "You are a disciplined FX scalping analyst. Symbols: XAUUSD, EURUSD; "
    "Timeframes: M1/M5/M15. Output ONLY a single JSON object with keys: "
    "symbol, timeframe, direction('long'|'short'), entry, sl, tp1, tp2, tp3, "
    "rr_tp1, rr_tp2, rr_tp3, confidence(0-100), valid_minutes(int), "
    "be_on_tp1(true), news_ok(true/false), news_note, rationale."
)

@app.post("/llm_analyze")
def llm_analyze(req: LLMReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if oai is None:
        raise HTTPException(status_code=500, detail="LLM not configured (missing OPENAI_API_KEY)")

    # подготвяме компактни редове със свещи (последните 120 стигат)
    rows = ", ".join(
        f"({c.ts[:19]}, {c.open:.5f},{c.high:.5f},{c.low:.5f},{c.close:.5f})"
        for c in req.candles[-120:]
    )
    user_prompt = (
        f"symbol={req.symbol}, timeframe={req.timeframe}\n"
        f"candles={rows}\n"
        f"Constraints: TP2 RR≥{req.min_rr}, confidence≥{req.min_confidence}. "
        "If setup not valid, return low confidence (server will discard)."
    )

    out = oai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=500,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    try:
        obj = json.loads(out.choices[0].message.content)
    except Exception:
        raise HTTPException(status_code=502, detail="LLM returned non-JSON")

    entry = float(obj["entry"]); sl = float(obj["sl"])
    tp1 = float(obj["tp1"]); tp2 = float(obj["tp2"]); tp3 = float(obj["tp3"])

    rr_tp1 = rr(entry, sl, tp1)
    rr_tp2 = rr(entry, sl, tp2)
    rr_tp3 = rr(entry, sl, tp3)

    conf = int(obj.get("confidence", 0))
    if rr_tp2 < req.min_rr or conf < req.min_confidence:
        return Response(status_code=204)

    return {
        "symbol": req.symbol, "timeframe": req.timeframe,
        "direction": obj["direction"],
        "entry": round(entry, 5), "sl": round(sl, 5),
        "tp1": round(tp1, 5), "tp2": round(tp2, 5), "tp3": round(tp3, 5),
        "rr_tp1": rr_tp1, "rr_tp2": rr_tp2, "rr_tp3": rr_tp3,
        "confidence": conf,
        "valid_minutes": int(obj.get("valid_minutes", req.default_valid_minutes)),
        "be_on_tp1": bool(obj.get("be_on_tp1", True)),
        "news_ok": bool(obj.get("news_ok", True)),
        "news_note": obj.get("news_note", ""),
        "rationale": obj.get("rationale", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
