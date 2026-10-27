# Project notes for Claude

Start with `docs/RESUME-HERE.md` (current state, next steps) and
`docs/ARCHITECTURE.md` (target design). Site-specific facts live in
`docs/research/`; read the relevant file before touching an adapter.

Conventions
- Python 3.11+, only dependency is `httpx`. Run with `python -m aggregator`.
- Crawling is polite by design: 1 req/s per host, retries with backoff,
  robots respected. Never add bot-wall evasion.
- Every product record keeps the brand's own article code in `sku`; do not
  replace it with a shop-internal id.
- Verify adapter changes against a live `--limit 3` crawl and, when a
  site's HTML is involved, against saved page samples.
- Record new site findings in `docs/research/<site>.md` and update
  `docs/research/sources.md` and `docs/RESUME-HERE.md` when state changes.
