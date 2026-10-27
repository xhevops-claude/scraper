# Buzz Sneakers MK — site research

Status: **verified with direct access** (2026-10-27). Live as
`buzzsneakers_mk` through the shared Sport Vision adapter.

- Site: https://www.buzzsneakers.mk (redirects to `/mk/`). `buzz.mk` is a
  parked domain (atom.com landing page) — not the shop.
- Operator: Sport Vision Group sneaker/streetwear brand (Jordan, adidas,
  The North Face, Crocs, Juicy Couture...). Platform: **NBSHOP 5.9.58**.
- Currency: MKD. Macedonian only (`/mk/`), no `/al/` links on the homepage
  though an `MAK_al` sitemap exists.

## Everything matches sportvision.mk

| Item | Buzz |
|---|---|
| robots.txt | Same NBSHOP template; sitemap at `/files/sitemap/sitemap.xml` |
| Product sitemap | `/files/sitemap/MAK_mk/product.xml` — **4,337 URLs** |
| Listing sitemap | `list_product.xml` — 118 campaign listings under `/mk/proizvodi/<slug>` (`sale`, `new`, `mid_season_sale`, `sneaker_of_the_week`, ...) |
| Product URL | `/mk/<category>/<numeric-id>-<slug>`, e.g. `/mk/jakna/396309-the-north-face-jakna-w-saikuru-jacket` |
| Product page | JSON-LD Product, same fields; product names are prefixed with the Cyrillic category word ("The North Face Јакна W SAIKURU JACKET") |
| Old price | `product-oldprice` block; verified on Crocs Classic: 3,032 MKD, old 3,790 MKD |
| Listing tiles | `TILE_RE` matches (83 tiles on `/mk/patiki`); `/page-N` pagination works |
| Sale listing | `/mk/proizvodi/sale` works (77 tiles) |

Caveat on filter vocabulary: `/mk/patiki/zenski` is **404** on Buzz
(works on Sport Vision and Sport Reality) — each shop defines its own
filter segments, so `--listing` paths are not portable across the family.

## Bug found while testing (fixed)

The discounted Crocs page carries a literal newline inside the JSON-LD
`description` string. Python's strict JSON parser rejects it ("Invalid
control character"), so `parse_product` returned `None`. The adapter now
parses with `strict=False`; this affects every NBSHOP shop, not just Buzz.

## Usage

```bash
python -m aggregator crawl buzzsneakers_mk --db products.db                   # full, ~4.3k requests
python -m aggregator crawl buzzsneakers_mk --db products.db --listing "proizvodi/sale"
```
