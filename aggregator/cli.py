import argparse
import asyncio
import re
import sys

from .adapters import ADAPTERS
from .db import Database
from .fetch import PoliteClient


async def crawl(source: str, db_path: str, limit: int | None, delay: float,
                listing: str | None, contains: str | None) -> None:
    adapter = ADAPTERS[source]
    db = Database(db_path)
    client = PoliteClient(delay=delay)
    needle = contains.casefold() if contains else None
    scraped = failed = skipped = 0
    try:
        async for url, title in _discover(adapter, client, listing):
            if limit is not None and scraped + failed >= limit:
                break
            # In listing mode we know the title before fetching the product
            # page; in sitemap mode the URL slug carries the product name.
            # Match the slug only, not the numeric product id before it.
            match_text = title if title else _url_slug(url)
            if needle and needle not in match_text.casefold():
                skipped += 1
                continue
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
    filtered = f", {skipped} filtered out" if needle else ""
    print(f"\nDone: {scraped} scraped, {failed} failed{filtered}. "
          f"{total} products stored for {source} in {db_path}")


def _url_slug(url: str) -> str:
    match = re.search(r"/\d+-([^/?#]+)", url)
    return match.group(1) if match else url


async def _discover(adapter, client, listing: str | None):
    if listing:
        async for url, title in adapter.discover_listing(client, listing):
            yield url, title
    else:
        async for url in adapter.discover(client):
            yield url, None


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
    p_crawl.add_argument("--listing", default=None, metavar="PATH",
                         help="Crawl one filtered listing instead of the full "
                              "sitemap, using the site's URL filter segments, "
                              'e.g. "patiki/zenski/new-balance"')
    p_crawl.add_argument("--brand", default=None, metavar="NAME",
                         help="Crawl one brand's listing, e.g. adidas or "
                              '"new balance"; the adapter maps it to the '
                              "site's own filter")
    p_crawl.add_argument("--contains", default=None, metavar="TEXT",
                         help="Only keep products whose title (listing mode) "
                              "or URL slug (sitemap mode) contains TEXT, "
                              'case-insensitive, e.g. "9060"')

    sub.add_parser("sources", help="List available source sites")

    args = parser.parse_args()
    if args.command == "sources":
        for name in sorted(ADAPTERS):
            print(name)
    elif args.command == "crawl":
        listing = args.listing
        if args.brand:
            if listing:
                parser.error("--brand and --listing are mutually exclusive")
            listing = ADAPTERS[args.source].brand_listing(args.brand)
            if not listing:
                parser.error(f"{args.source} has no listing for brand "
                             f"{args.brand!r}")
        asyncio.run(crawl(args.source, args.db, args.limit, args.delay,
                          listing, args.contains))


if __name__ == "__main__":
    main()
