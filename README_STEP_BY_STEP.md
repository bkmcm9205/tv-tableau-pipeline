# TradingView → FastAPI → Postgres → Tableau (plus optional forward to TradersPost)

This stack lets you send **TradingView alert JSON** into a tiny API, store it in **PostgreSQL**, and visualize in **Tableau**. You can also forward the same alert to **TradersPost** from the API.

## Files
- `app.py`              — FastAPI webhook
- `requirements.txt`    — Python deps
- `schema.sql`          — DB schema + view `v_trades` for entry/exit pairing

## 1) Deploy the API (Render / Railway)
### a) Create a new Web Service
- Runtime: Python 3.10+
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Add environment variables:
  - `APP_SECRET` = a long random string (you will append this to the webhook path)
  - `DATABASE_URL` = `postgresql://USER:PASS@HOST:PORT/DBNAME`
  - (Optional) `FORWARD_URL` = your TradersPost webhook URL

### b) Create a Postgres database (managed add-on)
- Copy its connection URL into `DATABASE_URL`

### c) First boot
- The app will auto-create the table on startup.
- Health check: `GET https://<your-service>/health`

## 2) Create the SQL view (optional but recommended)
Run `schema.sql` in your Postgres (psql or GUI). This also re-creates the table and indexes (safe). The view `v_trades` pairs entries and exits when there is no pyramiding.

## 3) Set the TradingView alert
- In the alert dialog, enable Webhook URL:
  `https://<your-service>/webhook/<APP_SECRET>`
- Use a JSON body like:
```
{
  "strategy":"PoC_FVG_RSI_VWAP_ADX",
  "action":"entry",
  "side":"long",
  "symbol":"{{ticker}}",
  "time_ms":{{timenow}},
  "price":{{close}},
  "qty":{{strategy.position_size}},
  "sl":{{plot_0}},
  "tp":{{plot_1}},
  "equity":{{strategy.equity}}
}
```
And for exit:
```
{
  "strategy":"PoC_FVG_RSI_VWAP_ADX",
  "action":"exit",
  "side":"long",
  "symbol":"{{ticker}}",
  "time_ms":{{timenow}},
  "price":{{close}},
  "equity":{{strategy.equity}},
  "reason":"position_closed"
}
```

> Use the JSON your Pine strategy already emits; the API stores any extra fields in `raw`.

## 4) (Optional) Fan-out to TradersPost
Set `FORWARD_URL` to your TradersPost webhook in the API env vars. The API will store the alert and also forward it.

## 5) Connect Tableau
- Add a PostgreSQL connection to your DB.
- Use table: `v_trades` for analysis.
- Example metrics:
  - **Total P&L**: SUM([pnl])
  - **Trades**: COUNT([entry_id])
  - **Win %**: SUM(IIF([pnl]>0,1,0)) / COUNT([entry_id])
  - **Profit Factor**: SUM(IIF([pnl]>0,[pnl],0)) / ABS(SUM(IIF([pnl]<0,[pnl],0)))
  - **Max Drawdown** (table calc): RUNNING_MAX(RUNNING_SUM([pnl])) - RUNNING_SUM([pnl]); then MIN() of that with a table direction by time.

- Filters: [strategy], [symbol], and time window.

## 6) Local test (optional)
Create a virtualenv and install deps:
```
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB
export APP_SECRET=change-me
uvicorn app:app --reload
```
Test webhook:
```
curl -X POST "http://127.0.0.1:8000/webhook/change-me"   -H "Content-Type: application/json"   -d '{"strategy":"TEST","action":"entry","side":"long","symbol":"AAPL","time_ms":1724412345678,"price":230.12,"qty":10}'
```
