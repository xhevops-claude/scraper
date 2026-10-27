# Architecture — from scraper to ecosystem

Status: **proposal, agreed in principle on 2026-10-27**, not yet built.
The current repo (`aggregator/`) is the seed of layer 1 and a throwaway
version of layer 3. Everything else below is to build.

## Goal

A centralized, standardized product database for sportswear in North
Macedonia, fed by ingestion pipelines from two kinds of sources:

- **Stock sources** — shops. What it costs, whether it is in stock, in
  which sizes, and how that changes over time.
- **Catalog sources** — official brand data. What the product *is*:
  canonical name, model, colourway, images, specs.

They join on the brand's own article code (adidas `HP6005`, Nike
`IB1895-006`), which every shop we researched exposes as its SKU.

Brands are onboarded one at a time: **adidas first, Nike second.**

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ 5. Consumers      read API · price alerts · exports · dashboards │
├──────────────────────────────────────────────────────────────┤
│ 4. Standardize    brand normalization · match offers→catalog  │
│                   (exact on article code, then rules, then    │
│                   review queue)                               │
├──────────────────────────────────────────────────────────────┤
│ 3. Central DB     Postgres: offers + price/size history,      │
│                   catalog products/variants, matches, runs    │
├──────────────────────────────────────────────────────────────┤
│ 2. Ingestion      scheduler → jobs (source × brand) → fetch → │
│                   raw snapshot → parse → normalize → load,    │
│                   with run metrics                            │
├──────────────────────────────────────────────────────────────┤
│ 1. Connectors     one adapter per platform, registered by     │
│                   source; typed stock | catalog               │
└──────────────────────────────────────────────────────────────┘
```

### 1. Connectors (exists, keep)

`aggregator/adapters/*.py`. Interface today:

- `discover(client)` → product URLs (whole site)
- `discover_listing(client, path_or_query)` → (url, title) for one filtered listing
- `brand_listing(brand)` → the site's own filter for a brand
- `fetch_product(client, url)` → `Product | None`

Two adapters, five live sources:

| Adapter | Sources | Discovery | Extraction |
|---|---|---|---|
| `sportvision.py` (NBSHOP) | sportvision_mk, sportreality_mk, buzzsneakers_mk (+13 countries by config) | sitemap or listing pages | JSON-LD + old-price block |
| `sportm.py` | sportm_mk, intersport_mk | paginated catalog | HTML by element ids |

To add for the ecosystem: a `kind` (stock/catalog), a `sizes` output, and
a stable connector registry (`sources` table) instead of the module-level
dict.

### 2. Ingestion pipeline (to build)

- **Jobs** are `(source, brand)` units, e.g. `sportm_mk × adidas`. Small
  enough to retry, big enough to schedule. A full pass over a source is
  just all its brand jobs.
- **Raw snapshots**: store the fetched HTML (or JSON) per URL per run
  before parsing. Re-parsing after a parser fix then needs no re-crawl.
  Filesystem to start (`raw/<source>/<date>/<id>.html.gz`), object storage
  later.
- **Run log**: per job — started/finished, pages fetched, products parsed,
  failures, parse-rate. A site redesign shows up as parse-rate dropping to
  zero on one source, not as silently empty data.
- **Scheduler**: cron is enough for daily runs; a DB-backed job table
  (`runs` with status) gives retries and visibility. Prefect/Dagster only
  if the number of jobs grows past what cron + a worker can show.
- **Politeness** stays as is: 1 req/s per host, retries with backoff,
  browser UA, robots respected. Never bypass a bot wall; run from an IP
  that is allowed.

### 3. Central database (to build) — Postgres

Draft schema. Names are proposals; keep the stock/catalog split.

```sql
-- reference
brands(id, name, slug)                                  -- "adidas", canonical casing
sources(id, key, kind, platform, base_url, enabled)     -- kind: stock | catalog

-- stock side (what shops say)
offers(id, source_id, source_product_id, sku, brand_id, name, url,
       category, currency, first_seen, last_seen)       -- unique (source_id, source_product_id)
offer_prices(offer_id, observed_at, price, old_price)   -- append on change
offer_sizes(offer_id, size_label, size_system, ean, in_stock, observed_at)
runs(id, source_id, brand_id, started_at, finished_at, status,
     pages, products, failures)
raw_pages(run_id, url, fetched_at, status, path)        -- pointer to snapshot

-- catalog side (what brands say)
catalog_products(id, brand_id, model_code, name)        -- adidas model code e.g. LSH59
catalog_variants(id, product_id, article_code, colourway, images, attrs jsonb)
catalog_variant_sizes(variant_id, size_label, ean)

-- the join
matches(offer_id, variant_id, method, confidence, reviewed_by, created_at)
```

Identifier levels (see docs/research/sources.md § SKU alignment):

| Level | Example | Where it comes from |
|---|---|---|
| model | `LSH59` | Sport Vision "manufacturer code"; brand catalog |
| model + colourway = article code | `HP6005` | every shop's SKU; brand catalog |
| + size = EAN-13 | `4066748660636` | Sport Vision per-size attribute; brand catalog |

### 4. Standardization and matching (to build)

1. Normalize brand names (`adidas` vs `Adidas`) and article codes (trim,
   upper-case, Nike `STYLE-COLOR` kept with the dash).
2. Exact match `offers.sku = catalog_variants.article_code` → confidence 1.
3. Fallback rules (model code + colour words, EAN overlap) → lower
   confidence, flagged.
4. Review queue for unmatched offers of onboarded brands.

### 5. Consumers (later)

Read API (FastAPI), price-drop alerts, CSV/Parquet exports, dashboards.
All read from layer 3 only.

## Recommended stack

Python 3.11+, Postgres, one worker process + cron, raw snapshots on disk,
FastAPI later. No Kafka/Airflow/microservices at this scale (~40k offers,
daily refresh).

## Build order

1. Postgres schema above; port `db.py` to it (keep SQLite for dev tests).
2. `sources`/`runs`/`raw_pages` + a `run` command that executes one
   (source, brand) job with snapshotting and metrics.
3. Store sizes (+EAN where available) from the adapters.
4. First catalog connector: adidas. Then the matcher on article code.
5. Nike catalog connector; remaining brands; D Sport once reachable.
6. API, alerts, exports.

## Open decisions (owner: you)

- **Where it runs.** Daily crawls and the two blocked sites (dsport.mk,
  adidas.com) need an IP that isn't the Claude cloud session's.
- **Database.** Postgres proposed; confirm or name an existing one.
- **adidas catalog source.** A feed/API you have access to, or scraping
  adidas.com (blocked from the cloud IP; needs a check from a normal
  connection).
- **Size-level stock**: wanted from day one (doubles product-page
  requests on the Sport M platform) or later?
