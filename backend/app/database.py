"""SQLite 연결/초기화."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_catalog (
    symbol            TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    market            TEXT NOT NULL,
    security_type     TEXT NOT NULL,
    is_common_share   INTEGER NOT NULL,
    isin_code         TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_catalog_market_type ON stock_catalog (market, security_type);

CREATE TABLE IF NOT EXISTS stocks (
    symbol          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    market          TEXT NOT NULL,
    security_type   TEXT NOT NULL,
    sort_order      INTEGER NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prices (
    symbol        TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    open_price    REAL NOT NULL,
    high_price    REAL NOT NULL,
    low_price     REAL NOT NULL,
    close_price   REAL NOT NULL,
    volume        INTEGER NOT NULL,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices (symbol, trade_date DESC);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """데이터 디렉터리를 생성하고 스키마를 초기화한다(멱등)."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
