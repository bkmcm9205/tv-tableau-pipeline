-- Run this in your Postgres (psql/GUI). The table is also created by app.py on startup.
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

-- View pairs entries with the next exit (assumes no pyramiding).
-- trade_id groups each entry with its subsequent rows; we pick the first exit after the entry.
CREATE OR REPLACE VIEW v_trades AS
WITH ordered AS (
  SELECT
    id, received_at, strategy, action, side, symbol, time_ms, price, qty, sl, tp, equity, reason,
    ROW_NUMBER() OVER (PARTITION BY strategy, symbol, side ORDER BY time_ms, id) AS rn,
    -- cumulative entries to build trade_id
    SUM(CASE WHEN action='entry' THEN 1 ELSE 0 END)
      OVER (PARTITION BY strategy, symbol, side ORDER BY time_ms, id) AS entry_count
  FROM tv_trades
),
entries AS (
  SELECT *
  FROM ordered
  WHERE action = 'entry'
),
exits AS (
  SELECT *
  FROM ordered
  WHERE action = 'exit'
)
SELECT
  e.strategy,
  e.symbol,
  e.side,
  e.time_ms       AS entry_time_ms,
  e.price         AS entry_price,
  e.qty           AS entry_qty,
  x.time_ms       AS exit_time_ms,
  x.price         AS exit_price,
  -- PnL: if long, exit - entry; if short, entry - exit
  CASE 
    WHEN e.side = 'long' THEN (COALESCE(x.price, e.price) - e.price) * COALESCE(e.qty,1)
    WHEN e.side = 'short' THEN (e.price - COALESCE(x.price, e.price)) * COALESCE(e.qty,1)
    ELSE NULL
  END AS pnl,
  e.received_at   AS entry_received_at,
  x.received_at   AS exit_received_at,
  e.id            AS entry_id,
  x.id            AS exit_id
FROM entries e
LEFT JOIN LATERAL (
  SELECT *
  FROM ordered o
  WHERE o.strategy = e.strategy
    AND o.symbol   = e.symbol
    AND o.side     = e.side
    AND o.action   = 'exit'
    AND (o.time_ms, o.id) > (e.time_ms, e.id)
  ORDER BY o.time_ms, o.id
  LIMIT 1
) x ON TRUE
ORDER BY e.time_ms, e.id;
