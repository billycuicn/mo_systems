from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import KLine


SINA_KLINE_URL = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
DEFAULT_SYMBOL = "sh000852"


def fetch_sina_klines(symbol: str = DEFAULT_SYMBOL, scale: int = 30, datalen: int = 800) -> list[KLine]:
    params = urlencode({"symbol": symbol, "scale": scale, "ma": "no", "datalen": datalen})
    request = Request(f"{SINA_KLINE_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=12) as response:
        raw = response.read().decode("gbk", errors="replace")
    payload = _parse_sina_payload(raw)
    klines = [
        KLine(
            symbol=symbol,
            dt=str(item["day"]),
            open=float(item["open"]),
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
            volume=float(item.get("volume") or 0),
        )
        for item in payload
    ]
    return sorted(klines, key=lambda item: item.dt)


def _parse_sina_payload(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        raise RuntimeError("新浪接口返回为空。")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = re.sub(r"([{,])(\w+):", r'\1"\2":', text)
        fixed = fixed.replace("'", '"')
        return json.loads(fixed)
