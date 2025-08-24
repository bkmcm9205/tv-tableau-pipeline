from fastapi import FastAPI, Request, HTTPException
from datetime import datetime, timezone
import asyncpg, os, json, httpx, asyncio

# =================== CONFIG (env) ===================
APP_SECRET = os.getenv("APP_SECRET", "change-me")
DB_URL     = os.getenv("DATABASE_URL", "")  # may be empty; we'll handle it
FORWARD_URL= os.getenv("FORWARD_URL", "")   # optional: TradersPost webhook

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
    """
    Try to connect to Postgres, but DO NOT crash if it's unavailable.
    This lets the service start and respond at /health so you can debug.
    """
    global pool
    if not DB_URL:
        print("[WARN] DATABASE_URL is empty; API will start without DB.")
        return
    try:
        # Try quickly; if it fails, just warn and continue
        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5, timeout=5)
        async with pool.acquire() as con:
            await con.execute(CREATE_SQL)
        print("[OK] Connected to Postgres and ensured schema.")
    except Exception as e:
        pool = None
        print(f"[WARN] Could not connect to Postgres at startup: {e}. API will still run; /webhook will return 503.")

@app.get("/health")
async def health():
    return {"ok": True, "db_connected": pool is not None}

@app.post("/webhook/{secret}")
async def webhook(secret: str, request: Request):
    if secret != APP_SECRET:
        raise HTTPException(403, "Forbidden")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    now = datetime.now(timezone.utc)

    # If DB not connected, return a clear 503 so you know what's wrong
    if pool is None:
        raise HTTPException(503, "Database not connected. Check DATABASE_URL and network/SSL settings.")

    # Extract fields
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

    # Optional forward
    if FORWARD_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(FORWARD_URL, json=payload)
        except Exception as e:
            print(f"[WARN] Forward to FORWARD_URL failed: {e}")

    return {"ok": True, "stored": True}
