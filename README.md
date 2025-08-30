# Forex Scalp Signals AI — FastAPI

## Run locally
1) Install Python 3.10+
2) Create venv and install deps:
```
python -m venv .venv
# Win: .\.venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```
3) Set API key:
```
# Win PowerShell:  $env:API_KEY="demo123"
# Mac/Linux:       export API_KEY="demo123"
```
4) Start:
```
uvicorn fastapi_server_env:app --host 0.0.0.0 --port 8000
```
Docs: http://localhost:8000/docs

## Deploy on Render
- Build: `pip install -r requirements.txt`
- Start: `uvicorn fastapi_server_env:app --host 0.0.0.0 --port $PORT`
- Env var: `API_KEY=demo123`

## Endpoint
POST /generate  (Header: X-API-Key: <your key>)

Body:
```
{ "symbol": "XAUUSD", "timeframe": "M5" }
```

Response (example):
```
{
 "symbol":"XAUUSD","timeframe":"M5","direction":"long",
 "entry":2412.10,"sl":2409.90,"tp1":2413.10,"tp2":2414.10,"tp3":2415.60,
 "rr_tp1":1.0,"rr_tp2":2.0,"rr_tp3":3.0,"confidence":88,
 "valid_minutes":30,"be_on_tp1":true,"news_ok":true,"news_note":"",
 "rationale":"Placeholder scalp setup. Manage 50/30/20; move SL to BE at TP1.",
 "generated_at":"2025-08-30T09:40:00Z"
}
```
