# Resume here

Last updated 2026-10-28 on the owner's box (local session).
Branch: `claude/zealous-tesla-trgrsh` (no PR opened).

## Where things stand, in one minute

- **Design agreed 2026-10-27/28: the Collector platform.** C# on .NET 10,
  RabbitMQ between stages, Postgres. A project is a tree of
  **operations** (`clothing/shoes/sportm`); each leaf holds job ×
  strategy pairs; a Conductor runs **runs** on a namespace; harvesters and
  adapters are leaves that never decide anything; a lake keeps raw items;
  adapters produce Products and Listings of the operation's domain with
  deterministic ids; the operation owns the model and harvests only what
  it needs (the apples rule); projects are hard partitions. All of it,
  with the vocabulary, in [ARCHITECTURE.md](ARCHITECTURE.md). Nothing of
  it is built yet.
- What exists is the **Python prototype** (`aggregator/`): fetch and parse
  for **five Macedonian sportswear shops** on two platforms, into SQLite.
  It is the reference for the harvest commands and the two Shoes adapters
  to be written, then it gets deleted.
- Every shop exposes the brand's own article code as `sku`, so matching to
  brand catalogs later is exact (adidas `HP6005` etc.). First project:
  shoes in North Macedonia; adidas first, Nike second.
- The cloud session's IP was blocked by Cloudflare on dsport.mk and by
  Akamai on adidas.com. That is why work moved to the owner's box, which
  is the first node.
- System map (visual): https://claude.ai/artifact/KVfRL3UyPBNhiJv6AG9FNn

## Set up locally

.NET SDK 10.0.401 is installed on the box (`dotnet --version`). RabbitMQ
and Postgres are not running anywhere yet. Once the solution skeleton
exists:

```bash
git checkout claude/zealous-tesla-trgrsh
dotnet build
dotnet test
dotnet run --project src/Collector.Cli -- run clothing/shoes/sportm sportm.discover --strategy fast --brand adidas --limit 5
dotnet run --project src/Collector.Cli -- runs                      # progress, per item
dotnet run --project src/Collector.Cli -- decide <run> retry-elsewhere
```

To run the Python prototype for comparison (no Python on Windows; the WSL
distros have 3.12 without `httpx`):

```bash
pip install httpx
python -m aggregator sources
python -m aggregator crawl sportm_mk --db products.db --brand adidas --limit 5
```

No tests exist yet. Ad-hoc verification of the prototype was done by
parsing saved HTML and by live `--limit` crawls (all passing on
2026-10-27).

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
- NBSHOP: JSON-LD descriptions can contain raw newlines → the prototype
  parses with `strict=False`; `System.Text.Json` needs the string
  sanitised before parsing. `/mk/proizvodi/sale` is 404 on Sport Reality;
  use `/mk/proizvodi/?outlet=yes`. Filter slugs differ per shop
  (`/mk/patiki/zenski` is 404 on Buzz).
- Sizes are parsed on the Sport M platform but **not stored** by the
  prototype. Any listed size = purchasable; sold-out sizes are omitted,
  not marked. `Listing.sizes[]` has a place for them, with branch.
- Brand casing differs ("adidas" NBSHOP vs "Adidas" Sport M).

## Next steps, in order

1. **Decide the open items** in ARCHITECTURE.md § Open decisions (where
   it runs, lake body storage, message size cap, MassTransit or raw,
   live-check policy).
2. **Check the two blocked sites from the box's IP**:
   - `https://www.dsport.mk/media/sitemap/dsport.xml` and whether
     `/amfeed/feed/download` serves a public product feed
     (docs/research/dsport-mk.md has the plan).
   - `https://www.adidas.com/us/vs-pace-2.0-shoes/HP6005.html` resolves
     (confirms article-code URLs); look for a product API/feed.
3. **Build order step 1**: solution skeleton, `Core` (Entity, ids,
   message contracts, job and strategy schemas, Shoes domain), `Data`
   (platform tables, Product, Listing, Category, first migration),
   RabbitMQ + Postgres running locally.
4. Then steps 2 to 8 of the build order in ARCHITECTURE.md.

## Things explicitly not done / not to do

- No PR was opened; no tests written; no CI; no .NET code yet.
- Do not try to get around Cloudflare/Akamai. Use an allowed node and the
  polite fetcher.
- Do not extend the Python prototype; port from it.
- The 13 non-MK Sport Vision storefronts are commented out in
  `sportvision.py`; enable only when needed (currency/sitemap region per
  site are guesses until checked).

## Artifacts

- System map of the Collector platform (private to the owner):
  https://claude.ai/artifact/KVfRL3UyPBNhiJv6AG9FNn
- Older one-page plan from the cloud session, superseded:
  https://claude.ai/artifact/Sz7KqmAcHnceRKNyMeamys
- Cloud session: https://claude.ai/code/session_01TaFuhUT1hkbaxPQeREF9wU
