# Sport Vision MK — site research for product aggregation

Status: **indirect research only** (2026-08-27). Direct crawling from this
environment is blocked by the session network policy (egress proxy returns
403 CONNECT for non-allowlisted domains). Everything below was reconstructed
from search-engine-indexed URLs and public company info, and must be verified
against live pages once network access is granted.

## Target

- Site: https://www.sportvision.mk (Macedonian storefront)
- Language: Macedonian, locale prefix `/mk/` on canonical URLs
- Currency: MKD (ден); prices formatted like `2.490` (dot thousands separator)
- Catalog size: thousands of SKUs across footwear, apparel, equipment
- Operator: Sport Vision Group (HQ Belgrade) — same platform runs storefronts
  in 13 countries (sportvision.rs, .ba, .me, .ro, …) plus sister brands
  observed in the wild: dsport.mk, sportreality.mk, sportlife.com.mk.
  One adapter is expected to cover the whole family with per-site config
  (domain, locale slugs, currency).

## Observed URL formats

All examples were seen in search indexes (i.e., real, reachable URLs).

### Catalog / listing pages

| Purpose | Pattern | Example |
|---|---|---|
| All products | `/mk/proizvodi/` | https://www.sportvision.mk/mk/proizvodi/ |
| Category | `/mk/<category>` | `/mk/patiki`, `/mk/jakna`, `/mk/cizmi`, `/mk/trenerka`, `/mk/sandali`, `/mk/torbi`, `/mk/oprema` |
| Gender/age filter (path segment) | `/mk/<category>/<filter>` | `/mk/patiki/maski`, `/mk/jakna/zenski`, `/mk/patiki/maski/vozrasni` |
| Multi-value filter (`+`-joined) | `/mk/<cat>/<v1>+<v2>` | `/mk/patiki/maski+unisex/vozrasni`, `/mk/cizmi/deca-devojcinja+deca-momcinja` |
| Activity filter | `/mk/patiki/<activity>` | `/mk/patiki/trcanje`, `/mk/patiki/trening`, `/mk/patiki/fudbal` |
| Brand filter | `/mk/proizvodi/<brand>` or trailing segment | `/mk/proizvodi/nike`, `/mk/proizvodi/skechers`, `/mk/patiki/maski/trcanje/nike` |
| Sale/outlet | `/sale` segment or `?outlet=yes` | `/mk/proizvodi/nike/sale`, `/mk/patiki/maski/?outlet=yes` |
| Campaign landing | `/mk/<slug>` | `/mk/zimska-ponuda`, `/mk/proizvodi/skijanje` |

Filter vocabulary seen so far: `maski`, `zenski`, `unisex`, `vozrasni`,
`deca-devojcinja`, `deca-momcinja`, `kids`, `bebe`, `deca-malecki`,
`tinejdzeri`, `nova_kolekcija`, `summer_sport`, `sport-bonus`.

### Detail pages

| Purpose | Pattern | Example |
|---|---|---|
| Product | `/mk/<category>/<numeric-id>-<slug>` | `/mk/patiki/8426431-harden-stepback` |
| Promotion | `/mk/akcii/<id>-<slug>` | `/mk/akcii/255-akcija-1120` |
| Store | `/mk/prodavnici/<id>-<slug>` | `/mk/prodavnici/16-sport-vision-12-kumanovo` |

The numeric product id (`8426431`) is the stable key for dedup and price
history.

## Verified with direct access (2026-08-28)

1. `robots.txt` — permissive: only blocks `?search=`, `?SID=`, a few misc
   patterns. No crawl-delay. Points at the sitemap index:
   `https://www.sportvision.mk/files/sitemap/sitemap.xml`.
2. Sitemaps — index → `files/sitemap/MAK_mk/sitemap.xml` (Macedonian) and
   `MAK_al/` (Albanian). The MK set includes **`product.xml` with 12,979
   product URLs** plus `product_group.xml`, `list_product.xml`, `store.xml`.
   Product enumeration is trivial; no category crawling needed.
3. Pages are **fully server-rendered** — plain `curl` with a browser UA gets
   complete HTML (listing page ~780KB, product page ~360KB). No Playwright
   needed.
4. Pagination: path segment `page-N`, e.g. `/mk/patiki/page-2`. 48 product
   tiles per listing page.
5. Product pages embed **schema.org Product JSON-LD**: `name`, `sku`
   (style code like `150437-TPE`), `productID` (the URL's numeric id),
   `brand`, `image` (list or single string), `offers.price` /
   `priceCurrency` / `availability`, return/shipping policy. No GTIN.
   Caveats: one ld+json block on the page is commented-out invalid JSON
   (skip non-parsing blocks); breadcrumb JSON-LD gives the category tree.
   Previous/discount price is HTML-only: the `product-oldprice` block
   (carries class `hide` when no discount — related-product tiles use
   `prev-old-price`, don't match those). Sizes are HTML-only
   (`product-attributes` list, EU/CM tabs, `disabled` = size unavailable).
6. Images are same-domain: `/files/images/slike_proizvoda/...` (full size)
   and `/files/thumbs/...` (350px thumbs). No separate CDN domain.
7. Anti-bot: none observed — plain curl with a browser UA works at 1-2 req/s.
   Bare `sportvision.mk` (no `www`) redirects to `www`; crawl `www` directly.
8. Price formats differ by location: JSON-LD uses `4990.00`; HTML uses
   `4.990` (dot = thousands separator). Currency MKD.
9. .rs/.ba/.ro storefront markup share still unverified (their domains
   weren't in this session's network allowlist).

## Environment blocker and fix

This Claude Code environment uses a restricted egress allowlist (package
registries, GitHub, Anthropic only). Probes confirmed: github.com reachable,
example.com / sportvision.mk / sportvision.rs all rejected at the gateway.

Fix: in claude.ai Claude Code settings, edit this environment's **network
access** policy and allow at minimum:

- `sportvision.mk`, `www.sportvision.mk`

and, for the wider aggregator, the other target storefront domains (plus
their image CDNs once identified). Docs:
https://code.claude.com/docs/en/claude-code-on-the-web

## Proposed architecture (unchanged by findings so far)

- Python: `httpx` (HTTP/2, async) + `selectolax` for parsing; Playwright
  (pre-installed here) only if listings turn out to be JS-rendered.
- One `Adapter` interface per site family: `discover()` (sitemap or category
  walk) → `parse_listing()` → `parse_product()` → normalized `Product`
  record `{source, source_id, name, brand, category, gender, price, currency,
  sale_price, url, image_url, availability, scraped_at}`.
- SQLite to start; scraped snapshots kept append-only for price history.
- Politeness: honor robots.txt, throttle ~1 req/s per host, identify with a
  stable UA, cache pages during development to avoid re-hitting the site.
