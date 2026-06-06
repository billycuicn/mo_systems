from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .chan_analyzer import analyze_confirmed_pens, build_candidate_pens
from .data_fetcher import DEFAULT_SYMBOL, fetch_sina_klines
from .models import Pen


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Chan Trading MVP")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class FetchRequest(BaseModel):
    symbol: str = DEFAULT_SYMBOL
    scale: int = 30
    datalen: int = 800


class PenUpdate(BaseModel):
    status: Optional[str] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    start_price: Optional[float] = None
    end_price: Optional[float] = None
    direction: Optional[str] = None


class ManualPenRequest(BaseModel):
    symbol: str = DEFAULT_SYMBOL
    start_dt: str
    end_dt: str
    start_price: float
    end_price: float


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
def state(symbol: str = DEFAULT_SYMBOL, limit: int = 800) -> dict:
    klines = db.list_klines(symbol, limit)
    pens = db.list_pens(symbol)
    analysis = analyze_confirmed_pens(pens)
    db.save_analysis(symbol, analysis)
    return {
        "symbol": symbol,
        "klines": [item.to_dict() for item in klines],
        "pens": [item.to_dict() for item in pens],
        "analysis": analysis,
    }


@app.post("/api/fetch")
def fetch_data(payload: FetchRequest) -> dict:
    try:
        klines = fetch_sina_klines(payload.symbol, payload.scale, payload.datalen)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"拉取新浪K线失败：{exc}") from exc
    db.upsert_klines(klines)
    return {"count": len(klines), "symbol": payload.symbol}


@app.post("/api/candidates/generate")
def generate_candidates(symbol: str = DEFAULT_SYMBOL, limit: int = 800) -> dict:
    klines = db.list_klines(symbol, limit)
    if not klines:
        raise HTTPException(status_code=400, detail="没有K线数据，请先拉取数据。")
    candidates = build_candidate_pens(klines)
    ids = [db.insert_pen(item, record_undo=False) for item in candidates]
    return {"count": len(ids), "ids": ids}


@app.patch("/api/pens/{pen_id}")
def patch_pen(pen_id: int, payload: PenUpdate) -> dict:
    fields = {key: value for key, value in payload.dict().items() if value is not None}
    try:
        pen = db.update_pen(pen_id, fields)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return pen.to_dict()


@app.post("/api/pens/confirm-all")
def confirm_all(symbol: str = DEFAULT_SYMBOL) -> dict:
    count = db.confirm_all_candidates(symbol)
    return {"count": count}


@app.post("/api/pens/manual")
def create_manual_pen(payload: ManualPenRequest) -> dict:
    direction = "up" if payload.end_price >= payload.start_price else "down"
    pen = Pen(
        id=None,
        symbol=payload.symbol,
        status="confirmed",
        source="manual",
        start_dt=payload.start_dt,
        end_dt=payload.end_dt,
        start_price=payload.start_price,
        end_price=payload.end_price,
        direction=direction,
    )
    pen_id = db.insert_pen(pen)
    return db.get_pen(pen_id).to_dict()


@app.post("/api/undo")
def undo() -> dict:
    return db.undo_last_action()
