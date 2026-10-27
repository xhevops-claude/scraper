# Sport Reality MK — site research

Status: **verified with direct access** (2026-10-27). Live as
`sportreality_mk` through the shared Sport Vision adapter.

- Site: https://www.sportreality.mk (redirects to `/mk/`), Macedonian;
  `/al/` Albanian mirror exists.
- Operator: Sport Vision Group sister brand (value/outlet positioning:
  Kronos, Nike, adidas, Under Armour...). Platform: **NBSHOP 5.9.58**
  (sportvision.mk runs NBSHOP 7; markup is identical for our purposes).
- Currency: MKD.
- Quirk: the server occasionally resets the TCP connection on the first
  request (`Recv failure: Connection reset by peer`); the client's retry
  handles it.

## Everything matches sportvision.mk

| Item | Sport Reality |
|---|---|
| robots.txt | Same template as Sport Vision: blocks `?search=`, `?SID=`, `*.php`; allows products/listings. |
| Sitemap index | `/files/sitemap/sitemap.xml` → `MAK_mk/` and `MAK_al/` |
| Product sitemap | `/files/sitemap/MAK_mk/product.xml` — **5,605 URLs** |
| Listing sitemap | `/files/sitemap/MAK_mk/list_product.xml` — 121 campaign listings under `/mk/proizvodi/<slug>` (e.g. `sezonsko_namaluvanje`, `posledni-parcinja`, `na-akciji`) |
| Product URL | `/mk/<category>/<numeric-id>-<slug>`, e.g. `/mk/dukser/181711-under-armour-icon-fleece-hoodie` |
| Product page | Server-rendered, schema.org Product JSON-LD (name, sku, productID, brand, image[], offers.price/priceCurrency/availability) |
| Old price | `product-oldprice` block, `hide` class when not discounted — parsed correctly, e.g. Kronos Hell: 327 MKD, old 1,090 MKD |
| Listing tiles | `TILE_RE` matches (48 tiles on `/mk/patiki/zenski`, duplicates per colour de-duped) and `/page-N` pagination works |
| Sale listing | `/mk/proizvodi/?outlet=yes` (NB: `/mk/proizvodi/sale` is 404 here, unlike Sport Vision) |

Verified parse of a live page:

```
Product(source='sportreality_mk', source_id='181711', name='Under Armour Icon Fleece Hoodie',
        sku='6013544-622', brand='Under Armour', category='dukser', price=3490.0,
        old_price=None, currency='MKD', availability='InStock', images=[3 urls])
```

## Usage

```bash
python -m aggregator crawl sportreality_mk --db products.db            # full, ~5.6k requests
python -m aggregator crawl sportreality_mk --db products.db --listing "patiki/zenski"
```
