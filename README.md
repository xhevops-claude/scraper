# Product aggregator

> **Status (2026-10-27):** this Python tree is the working prototype. The
> project continues as the **Collector** platform, C# / .NET 10 / ASP.NET
> Core with RabbitMQ and Postgres; see `docs/ARCHITECTURE.md` for the design
> and vocabulary and `docs/RESUME-HERE.md` for where things stand. The
> prototype stays as the reference until the .NET harvesters reach parity.

Scrapes sportswear products from multiple shop websites into one normalized
SQLite database, with price history.

Live sources:

- NBSHOP platform (Sport Vision Group), `aggregator/adapters/sportvision.py`:
  `sportvision_mk`, `sportreality_mk`, `buzzsneakers_mk`. The same platform
  runs Sport Vision storefronts in 13 more countries, ready to enable.
- Sport M platform, `aggregator/adapters/sportm.py`: `sportm_mk`,
  `intersport_mk`.

Researched but blocked from the cloud session: D Sport MK (Magento behind
Cloudflare). See `docs/research/sources.md` for the overview.

Every source stores the brand's own article code as `sku` (adidas `HP6005`,
Nike `IB1895-006`), so the same product can be matched across shops and
against official brand catalogs.

## Usage

```bash
pip install httpx           # only dependency

python -m aggregator sources                       # list available sites
python -m aggregator crawl sportvision_mk \
    --db products.db --limit 50 --delay 1.0        # test crawl
python -m aggregator crawl sportvision_mk --db products.db   # full crawl (~13k products)

# Brand by brand (every adapter maps the name to its site's own filter):
python -m aggregator crawl sportvision_mk --db products.db --brand adidas
python -m aggregator crawl sportm_mk      --db products.db --brand nike
python -m aggregator crawl intersport_mk  --db products.db --brand adidas --contains "vs pace"

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

# Sport M platform listings use the site's query string instead of a path:
python -m aggregator crawl sportm_mk --db products.db --listing "Segment=03&Grupa=01&Brend=01"
```

Re-running a crawl updates `products` in place (`last_seen` bumps) and appends
to `price_history` only when a product's price changed.

## How it works

1. **Discover** — NBSHOP: reads the site's product sitemap
   (`/files/sitemap/MAK_mk/product.xml`, ~13k URLs, permitted by robots.txt).
   Sport M platform: walks the paginated catalog (`/ProductCatalog?Page=N`,
   18 tiles per page) and remembers name, brand, image and prices per tile.
2. **Extract** — NBSHOP product pages embed schema.org Product JSON-LD:
   name, SKU, product id, brand, images, price, currency, availability;
   previous price comes from the `product-oldprice` block. Sport M pages
   are plain HTML: price by element id, old price, breadcrumb category,
   size list (any size listed = in stock), gallery images.
3. **Store** — upsert into SQLite keyed on `(source, source_id)`.

Site research notes live in `docs/research/`.

## Schema

`products`: source, source_id, url, name, sku, brand, category, price,
old_price, currency, availability, images (JSON), first_seen, last_seen.

`price_history`: source, source_id, price, old_price, currency, scraped_at.

## Adding a site

Implement an adapter with `discover()`, `discover_listing()`,
`brand_listing()` and `fetch_product()` returning the `Product` model (see
`aggregator/adapters/sportvision.py`) and register it in
`aggregator/adapters/__init__.py`. For other Sport Vision Group storefronts,
add a `SiteConfig` line.

## Politeness

Single connection, 1 req/s default delay (`--delay`), honors robots.txt
(which allows product pages), identifies with a browser UA, exponential
backoff on 5xx/429.
