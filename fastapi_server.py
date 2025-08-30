from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Literal
import random, os

API_KEY = "REPLACE_WITH_SECURE_KEY"

app = FastAPI(title="Forex Scalp Signals AI", version="1.0.0")

class GenerateReq(BaseModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    timeframe: Literal["M1", "M5", "M15"]
    lookback: int = 400
    session_filter: bool = True
    min_rr: float = 1.5
    min_confidence: int = 85
    news_block_minutes: int = 30

@app.get("/health")
def health():
    return {"status": "ok"}

def rr(entry, sl, tp):
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return round(reward / risk, 2) if risk else 0.0

@app.post("/generate")
def generate(req: GenerateReq, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # synthetic placeholder
    tick = 0.01 if req.symbol == "XAUUSD" else 0.0001
    risk_ticks = {"M1":20,"M5":30,"M15":40}[req.timeframe]
    ref = 2410.0 if req.symbol=="XAUUSD" else 1.0850
    direction = random.choice(["long","short"])
    entry = ref + random.randint(-50,50)*tick
    if direction=="long":
        sl = entry - risk_ticks*tick
        tp1 = entry + risk_ticks*tick
        tp2 = entry + int(risk_ticks*1.5)*tick
        tp3 = entry + int(risk_ticks*2.5)*tick
    else:
        sl = entry + risk_ticks*tick
        tp1 = entry - risk_ticks*tick
        tp2 = entry - int(risk_ticks*1.5)*tick
        tp3 = entry - int(risk_ticks*2.5)*tick
    rr2 = rr(entry, sl, tp2)
    conf = 70 + random.randint(0, 20)
    if rr2 < req.min_rr or conf < req.min_confidence:
        raise HTTPException(status_code=204, detail="Thresholds not met")
    return {
        "symbol": req.symbol, "timeframe": req.timeframe, "direction": direction,
        "entry": round(entry,5), "sl": round(sl,5),
        "tp1": round(tp1,5), "tp2": round(tp2,5), "tp3": round(tp3,5),
        "rr_tp1": rr(entry, sl, tp1), "rr_tp2": rr2, "rr_tp3": rr(entry, sl, tp3),
        "confidence": conf, "valid_minutes": 30 if req.timeframe=="M5" else 15 if req.timeframe=="M1" else 60,
        "be_on_tp1": True, "news_ok": True, "news_note": "",
        "rationale": "Placeholder scalp setup. Manage 50/30/20; move SL to BE at TP1.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
