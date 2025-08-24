import os, json, requests, time

URL = os.getenv("TEST_URL", "http://127.0.0.1:8000/webhook/change-me")

payloads = [
  {"strategy":"DEMO","action":"entry","side":"long","symbol":"AAPL","time_ms":int(time.time()*1000),"price":230.12,"qty":10},
  {"strategy":"DEMO","action":"exit","side":"long","symbol":"AAPL","time_ms":int(time.time()*1000)+60000,"price":232.00,"qty":10,"reason":"position_closed"}
]

for p in payloads:
    r = requests.post(URL, json=p, timeout=5)
    print(r.status_code, r.text)
