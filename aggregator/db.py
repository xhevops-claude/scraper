import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    url          TEXT NOT NULL,
    name         TEXT NOT NULL,
    sku          TEXT,
    brand        TEXT,
    category     TEXT,
    price        REAL,
    old_price    REAL,
    currency     TEXT,
    availability TEXT,
    images       TEXT,               -- JSON array
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    source     TEXT NOT NULL,
    source_id  TEXT NOT NULL,
    price      REAL,
    old_price  REAL,
    currency   TEXT,
    scraped_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_history
    ON price_history (source, source_id, scraped_at);
"""


class Database:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def upsert_product(self, p: Product) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO products (source, source_id, url, name, sku, brand,
                                  category, price, old_price, currency,
                                  availability, images, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, source_id) DO UPDATE SET
                url = excluded.url,
                name = excluded.name,
                sku = excluded.sku,
                brand = excluded.brand,
                category = excluded.category,
                price = excluded.price,
                old_price = excluded.old_price,
                currency = excluded.currency,
                availability = excluded.availability,
                images = excluded.images,
                last_seen = excluded.last_seen
            """,
            (p.source, p.source_id, p.url, p.name, p.sku, p.brand, p.category,
             p.price, p.old_price, p.currency, p.availability,
             json.dumps(p.images), now, now),
        )
        # Append to history only when the price actually changed.
        row = self.conn.execute(
            """
            SELECT price FROM price_history
            WHERE source = ? AND source_id = ?
            ORDER BY scraped_at DESC LIMIT 1
            """,
            (p.source, p.source_id),
        ).fetchone()
        if row is None or row[0] != p.price:
            self.conn.execute(
                """
                INSERT INTO price_history (source, source_id, price, old_price,
                                           currency, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (p.source, p.source_id, p.price, p.old_price, p.currency, now),
            )
        self.conn.commit()

    def count_products(self, source: str | None = None) -> int:
        if source:
            q = self.conn.execute(
                "SELECT COUNT(*) FROM products WHERE source = ?", (source,))
        else:
            q = self.conn.execute("SELECT COUNT(*) FROM products")
        return q.fetchone()[0]

    def close(self) -> None:
        self.conn.close()
