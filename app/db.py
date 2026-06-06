from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import KLine, Pen


DB_PATH = Path(__file__).resolve().parent.parent / "chan_mvp.sqlite3"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists klines (
                symbol text not null,
                dt text not null,
                open real not null,
                high real not null,
                low real not null,
                close real not null,
                volume real not null default 0,
                primary key (symbol, dt)
            );
            create table if not exists pens (
                id integer primary key autoincrement,
                symbol text not null,
                status text not null,
                source text not null,
                start_dt text not null,
                end_dt text not null,
                start_price real not null,
                end_price real not null,
                direction text not null,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            );
            create unique index if not exists idx_pens_unique_active
            on pens(symbol, start_dt, end_dt, start_price, end_price, direction, source);
            create table if not exists analysis_results (
                symbol text not null,
                kind text not null,
                payload text not null,
                updated_at text not null default current_timestamp,
                primary key (symbol, kind)
            );
            create table if not exists action_history (
                id integer primary key autoincrement,
                action text not null,
                payload text not null,
                created_at text not null default current_timestamp
            );
            """
        )


def upsert_klines(klines: list[KLine]) -> int:
    with connect() as conn:
        conn.executemany(
            """
            insert into klines(symbol, dt, open, high, low, close, volume)
            values(:symbol, :dt, :open, :high, :low, :close, :volume)
            on conflict(symbol, dt) do update set
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            [item.to_dict() for item in klines],
        )
    return len(klines)


def list_klines(symbol: str, limit: int = 240) -> list[KLine]:
    with connect() as conn:
        rows = conn.execute(
            """
            select * from (
                select * from klines where symbol = ? order by dt desc limit ?
            ) order by dt asc
            """,
            (symbol, limit),
        ).fetchall()
    return [_row_to_kline(row) for row in rows]


def list_pens(symbol: str, include_deleted: bool = False) -> list[Pen]:
    sql = "select * from pens where symbol = ?"
    params: list[object] = [symbol]
    if not include_deleted:
        sql += " and status != ?"
        params.append("deleted")
    sql += " order by start_dt asc, end_dt asc, id asc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_pen(row) for row in rows]


def insert_pen(pen: Pen, record_undo: bool = True) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            insert or ignore into pens(symbol, status, source, start_dt, end_dt, start_price, end_price, direction)
            values(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pen.symbol,
                pen.status,
                pen.source,
                pen.start_dt,
                pen.end_dt,
                pen.start_price,
                pen.end_price,
                pen.direction,
            ),
        )
        pen_id = cursor.lastrowid
        if pen_id and record_undo:
            _record_action(conn, "insert_pen", {"id": pen_id})
        if pen_id:
            return int(pen_id)
        row = conn.execute(
            """
            select id from pens
            where symbol = ? and start_dt = ? and end_dt = ? and start_price = ?
              and end_price = ? and direction = ? and source = ?
            """,
            (pen.symbol, pen.start_dt, pen.end_dt, pen.start_price, pen.end_price, pen.direction, pen.source),
        ).fetchone()
        return int(row["id"])


def update_pen(pen_id: int, fields: dict) -> Pen:
    allowed = {"status", "start_dt", "end_dt", "start_price", "end_price", "direction"}
    update_fields = {key: value for key, value in fields.items() if key in allowed}
    if not update_fields:
        return get_pen(pen_id)
    old = get_pen(pen_id).to_dict()
    with connect() as conn:
        assignments = ", ".join(f"{key} = ?" for key in update_fields)
        values = list(update_fields.values()) + [pen_id]
        conn.execute(f"update pens set {assignments}, updated_at = current_timestamp where id = ?", values)
        _record_action(conn, "update_pen", {"before": old})
    return get_pen(pen_id)

def confirm_all_candidates(symbol: str) -> int:
    with connect() as conn:
        rows = conn.execute("select * from pens where symbol = ? and status = 'candidate'", (symbol,)).fetchall()
        conn.execute(
            "update pens set status = 'confirmed', updated_at = current_timestamp where symbol = ? and status = 'candidate'",
            (symbol,),
        )
        if rows:
            _record_action(conn, "bulk_update_pen", {"before": [dict(row) for row in rows]})
    return len(rows)


def get_pen(pen_id: int) -> Pen:
    with connect() as conn:
        row = conn.execute("select * from pens where id = ?", (pen_id,)).fetchone()
    if row is None:
        raise KeyError(f"找不到笔：{pen_id}")
    return _row_to_pen(row)


def save_analysis(symbol: str, result: dict) -> None:
    with connect() as conn:
        for kind, payload in result.items():
            conn.execute(
                """
                insert into analysis_results(symbol, kind, payload)
                values(?, ?, ?)
                on conflict(symbol, kind) do update set
                    payload = excluded.payload,
                    updated_at = current_timestamp
                """,
                (symbol, kind, json.dumps(payload, ensure_ascii=False)),
            )


def undo_last_action() -> dict:
    with connect() as conn:
        row = conn.execute("select * from action_history order by id desc limit 1").fetchone()
        if row is None:
            return {"undone": False, "message": "没有可撤销的操作。"}
        payload = json.loads(row["payload"])
        if row["action"] == "insert_pen":
            conn.execute("delete from pens where id = ?", (payload["id"],))
        elif row["action"] == "update_pen":
            before = payload["before"]
            conn.execute(
                """
                update pens set status = ?, start_dt = ?, end_dt = ?, start_price = ?,
                    end_price = ?, direction = ?, updated_at = current_timestamp
                where id = ?
                """,
                (
                    before["status"],
                    before["start_dt"],
                    before["end_dt"],
                    before["start_price"],
                    before["end_price"],
                    before["direction"],
                    before["id"],
                ),
            )
        elif row["action"] == "bulk_update_pen":
            for before in payload["before"]:
                conn.execute(
                    "update pens set status = ?, updated_at = current_timestamp where id = ?",
                    (before["status"], before["id"]),
                )
        conn.execute("delete from action_history where id = ?", (row["id"],))
    return {"undone": True, "message": "已撤销上一步。"}


def _record_action(conn: sqlite3.Connection, action: str, payload: dict) -> None:
    conn.execute(
        "insert into action_history(action, payload) values(?, ?)",
        (action, json.dumps(payload, ensure_ascii=False)),
    )


def _row_to_kline(row: sqlite3.Row) -> KLine:
    return KLine(
        symbol=row["symbol"],
        dt=row["dt"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
    )


def _row_to_pen(row: sqlite3.Row) -> Pen:
    return Pen(
        id=row["id"],
        symbol=row["symbol"],
        status=row["status"],
        source=row["source"],
        start_dt=row["start_dt"],
        end_dt=row["end_dt"],
        start_price=row["start_price"],
        end_price=row["end_price"],
        direction=row["direction"],
    )

