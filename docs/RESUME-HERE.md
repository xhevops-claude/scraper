# Resume here

Last updated 2026-10-27 by the Claude cloud session
(https://claude.ai/code/session_01TaFuhUT1hkbaxPQeREF9wU).
Branch: `claude/zealous-tesla-trgrsh` (all work pushed; no PR opened).

## Where things stand, in one minute

- Working Python scraper → SQLite, with price history, for **five
  Macedonian sportswear shops** on two platforms. Crawls can be filtered
  by brand (`--brand adidas`), by site listing, or by title.
- Every shop stores the brand's own article code as `sku`, so cross-shop
  and shop↔official-catalog matching is exact (adidas `HP6005` etc.).
- Direction agreed: grow this into an **ecosystem** (central Postgres,
  ingestion pipelines, catalog sources, matching). See
  [ARCHITECTURE.md](ARCHITECTURE.md). Brands onboarded one at a time:
  **adidas first, Nike second.**
- The cloud session's IP is blocked by Cloudflare on dsport.mk and by
  Akamai on adidas.com. That is why work moves to a local machine.

## Set up locally

```bash
git clone <repo> && cd scraper
git checkout claude/zealous-tesla-trgrsh
python3 -m venv .venv && . .venv/bin/activate
pip install httpx
python -m aggregator sources
python -m aggregator crawl sportm_mk --db products.db --brand adidas --limit 5
```

No tests exist yet. Ad-hoc verification was done by parsing saved HTML and
by live `--limit` crawls (all passing on 2026-10-27).

## Sources

| Source key | Shop | Platform | Status | adidas | Nike |
|---|---|---|---|---|---|
| `sportvision_mk` | sportvision.mk | NBSHOP | live | 2,051 | 2,784 |
| `sportreality_mk` | sportreality.mk | NBSHOP | live | 1,324 | 1,183 |
| `buzzsneakers_mk` | buzzsneakers.mk | NBSHOP | live | 911 | 1,569 |
| `sportm_mk` | sport-m.com.mk | Sport M (ASP.NET) | live | ~4,000 | ~380 |
| `intersport_mk` | intersport.mk | Sport M (ASP.NET) | live | ~1,150 | ~160 |
| — | dsport.mk | Magento 2 + Cloudflare | **blocked from cloud IP** | ? | ? |

Per-site research: `docs/research/*.md`; overview with SKU levels:
`docs/research/sources.md`. Wrong domains to avoid: `sportm.mk` (news
site), `buzz.mk` (parked), `intersport.com.mk` / `sportm.com.mk`
(unreachable).

## Verified facts worth not re-deriving

- adidas VS Pace 2.0 on Sport Vision/Sport Reality: article codes
  `HP6005`, `HP6002`, `KI6514` (three colourways); model code `LSH59`
  ("Код на производителот" on Sport Vision); per-size EAN-13 in
  `data-combination-code` on Sport Vision size `<li>`s.
- Sport M platform brand codes (same on both shops): adidas `01`, Nike
  `02`, Puma `04`; full list in `aggregator/adapters/sportm.py`.
- Sport M listing: 18 tiles/page; stop when a page yields no new tiles
  (the "next" arrow is always rendered). Sport M and Intersport use
  different tile layouts; both handled.
- NBSHOP: JSON-LD descriptions can contain raw newlines → parse with
  `strict=False` (fixed). `/mk/proizvodi/sale` is 404 on Sport Reality;
  use `/mk/proizvodi/?outlet=yes`. Filter slugs differ per shop
  (`/mk/patiki/zenski` is 404 on Buzz).
- Sizes are parsed on the Sport M platform but **not stored** (no field
  in `Product` yet). Any listed size = purchasable; sold-out sizes are
  omitted, not marked.
- Brand casing differs ("adidas" NBSHOP vs "Adidas" Sport M).

## Next steps, in order

1. **Decide the three open items** in ARCHITECTURE.md § Open decisions
   (hosting, database, adidas catalog source).
2. **Check the two blocked sites from a normal IP**:
   - `https://www.dsport.mk/media/sitemap/dsport.xml` and whether
     `/amfeed/feed/download` serves a public product feed
     (docs/research/dsport-mk.md has the plan).
   - `https://www.adidas.com/us/vs-pace-2.0-shoes/HP6005.html` resolves
     (confirms article-code URLs); look for a product API/feed.
3. **Schema**: create the Postgres schema from ARCHITECTURE.md § 3; port
   `aggregator/db.py`; add `sizes` (+EAN) to `Product` and both adapters.
4. **Pipeline**: `runs` + raw page snapshots + a `run <source> <brand>`
   command with metrics; cron it daily for adidas on all five sources.
5. **adidas catalog connector** → `catalog_variants`; matcher on article
   code; report match rate.
6. Then Nike, then the rest.

## Things explicitly not done / not to do

- No PR was opened; no tests written; no CI.
- Do not try to get around Cloudflare/Akamai (also refused by the cloud
  session's policy). Use an allowed IP and the polite client.
- The 13 non-MK Sport Vision storefronts are commented out in
  `sportvision.py`; enable only when needed (currency/sitemap region per
  site are guesses until checked).

## Artifacts from the session

- One-page visual plan: https://claude.ai/artifact/Sz7KqmAcHnceRKNyMeamys
  (private to the owner; superseded by ARCHITECTURE.md for detail).
