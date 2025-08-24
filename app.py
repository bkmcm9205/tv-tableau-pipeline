from fastapi import FastAPI, Request, HTTPException
from datetime import datetime, timezone
import asyncpg, os, json, httpx

# =================== CONFIG (env) ===================
APP_SECRET = os.getenv("APP_SECRET", "change-me")
DB_URL     = os.getenv("DATABASE_URL")  # e.g., postgresql://user:pass@host:port/db
FORWARD_URL= os.getenv("FORWARD_URL", "")  # optional: TradersPost webhook

if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Example: postgresql://user:pass@host:5432/dbname")

# =================== APP ===================
app = FastAPI(title="TradingView → DB (→ TradersPost) Webhook")
pool = None

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS tv_trades (
  id BIGSERIAL PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL,
  strategy TEXT,
  action TEXT,
  side TEXT,
  symbol TEXT,
  time_ms BIGINT,
  price DOUBLE PRECISION,
  qty DOUBLE PRECISION,
  sl DOUBLE PRECISION,
  tp DOUBLE PRECISION,
  equity DOUBLE PRECISION,
  reason TEXT,
  raw JSONB
);
CREATE INDEX IF NOT EXISTS idx_tv_trades_symbol_time ON tv_trades(symbol, time_ms);
CREATE INDEX IF NOT EXISTS idx_tv_trades_strategy ON tv_trades(strategy);
"""

INSERT_SQL = """
INSERT INTO tv_trades (received_at, strategy, action, side, symbol, time_ms, price, qty, sl, tp, equity, reason, raw)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13);
"""

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    async with pool.acquire() as con:
        await con.execute(CREATE_SQL)

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/webhook/{secret}")
async def webhook(secret: str, request: Request):
    if secret != APP_SECRET:
        raise HTTPException(403, "Forbidden")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    now = datetime.now(timezone.utc)

    # Extract fields (all optional except action/strategy/symbol ideally)
    s   = payload.get("strategy")
    act = payload.get("action")
    side= payload.get("side")
    sym = payload.get("symbol")
    tms = payload.get("time_ms")
    px  = payload.get("price")
    qty = payload.get("qty")
    sl  = payload.get("sl")
    tp  = payload.get("tp")
    eq  = payload.get("equity")
    rsn = payload.get("reason")

    # Persist
    async with pool.acquire() as con:
        await con.execute(
            INSERT_SQL, now, s, act, side, sym, tms, px, qty, sl, tp, eq, rsn, json.dumps(payload)
        )

    # Optional: forward to TradersPost (or any broker bridge)
    if FORWARD_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(FORWARD_URL, json=payload)
        except Exception:
            # don't block if forward fails
            pass

    return {"ok": True, "stored": True}
