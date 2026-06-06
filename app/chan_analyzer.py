from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import KLine, Pen


@dataclass(frozen=True)
class Fractal:
    kind: str
    index: int
    dt: str
    price: float


def normalize_inclusion(klines: Iterable[KLine]) -> list[KLine]:
    """合并简单包含关系，减少分型误判。"""
    normalized: list[KLine] = []
    trend = "up"
    for item in klines:
        if not normalized:
            normalized.append(item)
            continue
        prev = normalized[-1]
        contains = (item.high <= prev.high and item.low >= prev.low) or (
            item.high >= prev.high and item.low <= prev.low
        )
        if not contains:
            trend = "up" if item.high >= prev.high else "down"
            normalized.append(item)
            continue
        if trend == "up":
            merged = KLine(
                symbol=item.symbol,
                dt=item.dt,
                open=prev.open,
                high=max(prev.high, item.high),
                low=max(prev.low, item.low),
                close=item.close,
                volume=prev.volume + item.volume,
            )
        else:
            merged = KLine(
                symbol=item.symbol,
                dt=item.dt,
                open=prev.open,
                high=min(prev.high, item.high),
                low=min(prev.low, item.low),
                close=item.close,
                volume=prev.volume + item.volume,
            )
        normalized[-1] = merged
    return normalized


def find_fractals(klines: list[KLine]) -> list[Fractal]:
    fractals: list[Fractal] = []
    for index in range(1, len(klines) - 1):
        left = klines[index - 1]
        mid = klines[index]
        right = klines[index + 1]
        if mid.high > left.high and mid.high > right.high and mid.low > left.low and mid.low > right.low:
            fractals.append(Fractal("top", index, mid.dt, mid.high))
        elif mid.low < left.low and mid.low < right.low and mid.high < left.high and mid.high < right.high:
            fractals.append(Fractal("bottom", index, mid.dt, mid.low))
    return fractals


def build_candidate_pens(klines: list[KLine], min_gap: int = 4) -> list[Pen]:
    normalized = normalize_inclusion(klines)
    fractals = find_fractals(normalized)
    pens: list[Pen] = []
    last: Fractal | None = None
    for current in fractals:
        if last is None:
            last = current
            continue
        if current.kind == last.kind:
            if current.kind == "top" and current.price > last.price:
                last = current
            elif current.kind == "bottom" and current.price < last.price:
                last = current
            continue
        if current.index - last.index < min_gap:
            continue
        direction = "up" if last.kind == "bottom" and current.kind == "top" else "down"
        pens.append(
            Pen(
                id=None,
                symbol=normalized[0].symbol if normalized else "sh000852",
                status="candidate",
                source="auto",
                start_dt=last.dt,
                end_dt=current.dt,
                start_price=last.price,
                end_price=current.price,
                direction=direction,
            )
        )
        last = current
    return pens


def analyze_confirmed_pens(pens: list[Pen]) -> dict:
    confirmed = [pen for pen in pens if pen.status == "confirmed"]
    confirmed.sort(key=lambda item: item.start_dt)
    segments = build_segments(confirmed)
    centers = build_centers(segments)
    signals = build_signals(confirmed, centers)
    return {"segments": segments, "centers": centers, "signals": signals}


def build_segments(pens: list[Pen]) -> list[dict]:
    segments: list[dict] = []
    for index in range(0, max(len(pens) - 2, 0), 3):
        group = pens[index : index + 3]
        if len(group) < 3:
            continue
        segments.append(
            {
                "id": len(segments) + 1,
                "start_dt": group[0].start_dt,
                "end_dt": group[-1].end_dt,
                "high": max(max(p.start_price, p.end_price) for p in group),
                "low": min(min(p.start_price, p.end_price) for p in group),
                "direction": group[-1].direction,
            }
        )
    return segments


def build_centers(segments: list[dict]) -> list[dict]:
    centers: list[dict] = []
    for index in range(0, max(len(segments) - 2, 0)):
        group = segments[index : index + 3]
        zone_high = min(item["high"] for item in group)
        zone_low = max(item["low"] for item in group)
        if zone_high >= zone_low:
            centers.append(
                {
                    "id": len(centers) + 1,
                    "start_dt": group[0]["start_dt"],
                    "end_dt": group[-1]["end_dt"],
                    "high": zone_high,
                    "low": zone_low,
                }
            )
    return centers


def build_signals(pens: list[Pen], centers: list[dict]) -> list[dict]:
    if not pens or not centers:
        return []
    latest_pen = pens[-1]
    latest_center = centers[-1]
    signals: list[dict] = []
    if latest_pen.end_price > latest_center["high"]:
        signals.append(
            {
                "kind": "buy_watch",
                "dt": latest_pen.end_dt,
                "price": latest_pen.end_price,
                "message": "确认笔向上离开最近中枢，关注回拉后的买点。",
            }
        )
    elif latest_pen.end_price < latest_center["low"]:
        signals.append(
            {
                "kind": "sell_watch",
                "dt": latest_pen.end_dt,
                "price": latest_pen.end_price,
                "message": "确认笔向下离开最近中枢，关注反抽后的卖点。",
            }
        )
    return signals

