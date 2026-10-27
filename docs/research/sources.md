# Stock ingestion sources — overview

Status as of 2026-10-27. "Stock ingestion" = we read each shop's live
catalog for price, discount and availability; "catalog ingestion" (official
brand sources for canonical product data) is a separate, later track.

| Source | Domain | Platform | Reachable from cloud session | Catalog size | Adapter | Notes |
|---|---|---|---|---|---|---|
| Sport Vision MK | www.sportvision.mk | NBSHOP 7 | yes | ~13,000 | `sportvision_mk` (live) | [sportvision-mk.md](sportvision-mk.md) |
| Sport Reality MK | www.sportreality.mk | NBSHOP 5.9.58 | yes (occasional TCP resets, retry works) | 5,605 | `sportreality_mk` (live, same adapter) | [sportreality-mk.md](sportreality-mk.md) |
| Buzz Sneakers MK | www.buzzsneakers.mk | NBSHOP 5.9.58 | yes | 4,337 | `buzzsneakers_mk` (live, same adapter) | [buzzsneakers-mk.md](buzzsneakers-mk.md). `buzz.mk` is a parked domain, not the shop. |
| Sport M | sport-m.com.mk | custom ASP.NET MVC + DevExpress | yes | ~6,400 | **to build** | [sport-m-platform.md](sport-m-platform.md). `sportm.mk` is a sports news site, not the shop. |
| Intersport MK | intersport.mk | same codebase as Sport M (operated by Sport M) | yes | ~4,700 | **to build** (shared with Sport M) | [sport-m-platform.md](sport-m-platform.md) |
| D Sport MK | www.dsport.mk | Magento 2 (Betech) + Amasty feed, behind Cloudflare | **no** — Cloudflare blocks this environment's IP | unknown | blocked | [dsport-mk.md](dsport-mk.md). Research from a normal machine/IP needed. |

## Platform families

Three adapters cover all six shops:

1. **NBSHOP** (Sport Vision Group): `aggregator/adapters/sportvision.py`.
   Sitemap-driven discovery, JSON-LD product pages. Three MK shops live;
   13 more countries available by config.
2. **Sport M platform** (Sport M + Intersport): one adapter to write.
   No sitemap, no JSON-LD; paginated HTML catalog with a clean tile
   structure and price/discount args embedded in the add-to-cart call.
3. **Magento 2** (D Sport): standard Magento sitemap + product pages, or
   the Amasty product feed, once it can be reached.
