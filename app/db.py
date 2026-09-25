"""Short-lived SQLite connections; explicit write transactions serialize decisions."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self, *, write: bool = False, snapshot: bool = False):
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            elif snapshot:
                connection.execute("BEGIN")
            yield connection
            if write or snapshot:
                connection.commit()
        except BaseException:
            if write or snapshot:
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, schema: str):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(schema)


APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_hash TEXT NOT NULL,
    stay_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(id),
    stay_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('towel','pizza')),
    service TEXT NOT NULL CHECK(service IN ('housekeeping','kitchen')),
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
    status TEXT NOT NULL CHECK(status IN
        ('saved','uncertain','transmitted','in_progress','completed')),
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(request_id, kind)
);
CREATE INDEX IF NOT EXISTS orders_stay_kind ON orders(stay_id, kind, status);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id),
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_order ON events(order_id, id);
"""

RECEIVER_SCHEMA = """
CREATE TABLE IF NOT EXISTS modes (
    service TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK(mode IN ('normal','offline','lose_response_once'))
);
INSERT OR IGNORE INTO modes VALUES ('housekeeping','normal'), ('kitchen','normal');
CREATE TABLE IF NOT EXISTS receipts (
    reference TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    stay_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
    status TEXT NOT NULL CHECK(status IN ('transmitted','in_progress','completed')),
    created_at TEXT NOT NULL
);
"""
