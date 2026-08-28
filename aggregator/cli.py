import argparse
import asyncio
import sys

from .adapters import ADAPTERS
from .db import Database
from .fetch import PoliteClient


async def crawl(source: str, db_path: str, limit: int | None,
                delay: float) -> None:
    adapter = ADAPTERS[source]
    db = Database(db_path)
    client = PoliteClient(delay=delay)
    scraped = failed = 0
    try:
        async for url in adapter.discover(client):
            if limit is not None and scraped + failed >= limit:
                break
            try:
                product = await adapter.fetch_product(client, url)
            except Exception as exc:
                failed += 1
                print(f"FAIL {url}: {exc}", file=sys.stderr)
                continue
            if product is None:
                failed += 1
                print(f"SKIP (no product data) {url}", file=sys.stderr)
                continue
            db.upsert_product(product)
            scraped += 1
            print(f"[{scraped}] {product.brand or '?'} | {product.name} | "
                  f"{product.price} {product.currency} | {product.availability}")
    finally:
        await client.aclose()
        total = db.count_products(source)
        db.close()
    print(f"\nDone: {scraped} scraped, {failed} failed. "
          f"{total} products stored for {source} in {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aggregator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_crawl = sub.add_parser("crawl", help="Crawl a source site into SQLite")
    p_crawl.add_argument("source", choices=sorted(ADAPTERS))
    p_crawl.add_argument("--db", default="products.db")
    p_crawl.add_argument("--limit", type=int, default=None,
                         help="Max products to fetch (default: all)")
    p_crawl.add_argument("--delay", type=float, default=1.0,
                         help="Seconds between requests (default: 1.0)")

    p_sources = sub.add_parser("sources", help="List available source sites")

    args = parser.parse_args()
    if args.command == "sources":
        for name in sorted(ADAPTERS):
            print(name)
    elif args.command == "crawl":
        asyncio.run(crawl(args.source, args.db, args.limit, args.delay))


if __name__ == "__main__":
    main()
