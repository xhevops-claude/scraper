# Project notes for Claude

Start with `docs/RESUME-HERE.md` (current state, next steps) and
`docs/ARCHITECTURE.md` (the Collector platform design and vocabulary).
Site-specific facts live in `docs/research/`; read the relevant file
before touching a harvest command or an adapter.

Stack
- Target: C# on .NET 10 / ASP.NET Core, RabbitMQ between stages, EF Core +
  Npgsql on Postgres, AngleSharp for HTML, `System.Text.Json` for JSON-LD,
  Playwright for browser harvesting, xUnit. Solution layout in
  `docs/ARCHITECTURE.md`. Build and test with `dotnet build` /
  `dotnet test`.
- `aggregator/` (Python 3.11+, `httpx`, `python -m aggregator`) is the
  working prototype and the reference for site behaviour. Do not extend it;
  port from it. It is deleted once the .NET harvesters reach parity.

Vocabulary (use these words, in code and docs; full table in ARCHITECTURE.md)
- Collector = the whole pipeline. Harvester = fetches only. Lake = raw
  items. Adapter = raw → domain entities. Store = Postgres.
- Command = smallest unit, provider + id. Job = ordered list of commands
  (what). Strategy = how a job executes (mechanism, nodes, pacing, retry
  budget). Run = job × strategy × project. Conductor = runs a run.
- Project = tenant and ecosystem, a hard partition, the root of a tree of
  Operations. Operation = a node of that tree, "what we want"
  (`clothing/shoes`); a leaf operation is bound to one provider
  (`clothing/shoes/sportm`) and holds its job × strategy pairs. Namespace =
  an operation's path. No separate "ecosystem" level.
- Provider = whose ids we keep. Source = one site of a provider, one
  record however many leaves use it. Node = a device that harvests.
- Product = ours, one per real thing. Listing = one provider's view of it,
  with `infoCheckedAt` and `stockCheckedAt`.
- Not "connector", not "scraper", not "step", not "policy".

Rules
- Harvesters and adapters are leaves. They never start a harvest, an adapt
  or a run. Only the conductor, following a job, decides what comes next.
- A command reads its input from the store ("every listing with no
  details"), never from the previous command.
- Harvesting is polite by design: the source's rate floor, retries with
  backoff, robots respected. Never add bot-wall evasion.
- Failure is per item. The system never marks a run failed on its own; a
  spent retry budget pauses the run for an administrator's decision.
- Every product keeps the brand's own article code in `sku` and the
  provider's own id in `providerId`; never replace one with the other.
- Our ids are deterministic (project seed + provider key); the same input
  must always produce the same id.
- Every table and every message carries `projectId`.
- The apples rule: the operation owns the common model and decides what
  is harvested; a leaf only says how its provider fills that model; a page
  harvested under `clothing/shoes/sportm` can only produce Shoes entities.
  Never harvest a whole site because an operation needs one category.
- Nothing in the platform is specific to a domain. Shoes is the first
  operation, not the design. The domain lives on the operation, not on
  the project.
- Verify harvest-command changes against a live `--limit 3` run and, when
  a site's HTML is involved, against saved page samples under `tests/`.
- Record new site findings in `docs/research/<site>.md` and update
  `docs/research/sources.md` and `docs/RESUME-HERE.md` when state changes.
