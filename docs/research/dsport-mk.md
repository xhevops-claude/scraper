# D Sport MK — site research

Status: **blocked from this environment** (2026-10-27). Cloudflare returns
`403 "Sorry, you have been blocked"` for every page request from the cloud
session's egress IP (plain curl with a browser UA, and even the sitemap
URL). Only `robots.txt` is served. Research below is from that file alone
and must be completed from a normal machine/IP.

- Site: https://www.dsport.mk (`dsport.mk` → 403 as well).
- Platform: **Magento 2**, managed by an agency ("Betech standard" header in
  robots.txt), with the **Amasty Product Feed** extension installed.
- Note: the older Sport Vision research listed dsport.mk as a Sport Vision
  sister brand on NBSHOP; that is no longer true — it has moved to Magento.

## What robots.txt tells us

- Sitemap: `https://www.dsport.mk/media/sitemap/dsport.xml` (standard
  Magento sitemap — products, categories, CMS pages in one file).
- Query-string URLs are disallowed except clean pagination `?p=N`:
  crawl category pages as `/<category>.html?p=N`, never with facet params.
- Explicitly **allowed**: `/amfeed/feed/download` — an Amasty product feed
  download endpoint. If a public feed is configured (typically Google
  Shopping XML/CSV with id, title, price, sale_price, availability, brand,
  link, image_link), it is the cheapest possible stock source: one request
  for the whole catalog. Needs the feed filename/parameter, which the
  storefront HTML or a search engine cache would reveal.
- Standard Magento disallows (`/checkout/`, `/customer/`, `/catalogsearch/`,
  `/catalog/product/view/` ...) — we don't need any of them.
- Each rule is listed twice (`/x` and `/*/x`), meaning store-code URLs
  (e.g. `/mk/`, `/en/`) may exist.

## Plan once reachable

1. Fetch the sitemap; separate product URLs (usually `<slug>.html`).
2. Product pages: Magento 2 ships schema.org Product JSON-LD on many themes,
   otherwise the `Magento_Catalog` price box has
   `data-price-type="finalPrice"` / `"oldPrice"` spans with
   `data-price-amount`, and `product-info-stock-sku` carries SKU and
   "In stock"/"Out of stock". Size availability comes from the
   `jsonConfig` of the configurable-product swatch renderer embedded in
   the page.
3. Check the Amasty feed first — if it exists it replaces steps 1–2.

Cloudflare: the block is IP/reputation based (no JS challenge was served,
just a hard 403). Running from a residential/office IP with the normal
polite client is the expected fix; do not attempt to evade the challenge.
