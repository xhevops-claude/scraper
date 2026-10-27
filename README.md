# Product aggregator

Scrapes sportswear products from multiple shop websites into one normalized
SQLite database, with price history.

Live sources (all on the Sport Vision Group's NBSHOP platform, one adapter):
`sportvision_mk`, `sportreality_mk`, `buzzsneakers_mk`. The same platform
runs Sport Vision storefronts in 13 more countries, ready to enable in
`aggregator/adapters/sportvision.py`.

Researched, adapter not yet written: Sport M and Intersport MK (shared
custom platform), D Sport MK (Magento, blocked by Cloudflare from the cloud
session). See `docs/research/sources.md` for the overview.

## Usage

```bash
pip install httpx           # only dependency

python -m aggregator sources                       # list available sites
python -m aggregator crawl sportvision_mk \
    --db products.db --limit 50 --delay 1.0        # test crawl
python -m aggregator crawl sportvision_mk --db products.db   # full crawl (~13k products)

# Targeted crawls (a handful of requests instead of thousands):

# One filtered listing, using the site's own URL filter segments
# (category/gender/brand/...), e.g. women's New Balance sneakers:
python -m aggregator crawl sportvision_mk --db products.db \
    --listing "patiki/zenski/new-balance"

# Plus a title filter (checked BEFORE fetching each product page):
python -m aggregator crawl sportvision_mk --db products.db \
    --listing "patiki/zenski/new-balance" --contains 9060

# Or search the whole catalog by name via the sitemap slug
# (1 sitemap request + only the matching product pages):
python -m aggregator crawl sportvision_mk --db products.db --contains 9060
```

Re-running a crawl updates `products` in place (`last_seen` bumps) and appends
to `price_history` only when a product's price changed.

## How it works

1. **Discover** — reads the site's product sitemap
   (`/files/sitemap/MAK_mk/product.xml`, ~13k URLs, permitted by robots.txt).
2. **Extract** — product pages are server-rendered and embed schema.org
   Product JSON-LD: name, SKU, product id, brand, images, price, currency,
   availability. Previous price (for discounts) is read from the page's
   `product-oldprice` block.
3. **Store** — upsert into SQLite keyed on `(source, source_id)`.

Site research notes live in `docs/research/`.

## Schema

`products`: source, source_id, url, name, sku, brand, category, price,
old_price, currency, availability, images (JSON), first_seen, last_seen.

`price_history`: source, source_id, price, old_price, currency, scraped_at.

## Adding a site

Implement an adapter with `discover()` and `fetch_product()` returning the
`Product` model (see `aggregator/adapters/sportvision.py`) and register it in
`aggregator/adapters/__init__.py`. For other Sport Vision Group storefronts,
add a `SiteConfig` line.

## Politeness

Single connection, 1 req/s default delay (`--delay`), honors robots.txt
(which allows product pages), identifies with a browser UA, exponential
backoff on 5xx/429.
