# Architecture — the Collector platform

Status: **design agreed in discussion on 2026-10-27 and 2026-10-28**, not
yet built. Stack: **C# on .NET 10 / ASP.NET Core, RabbitMQ, Postgres.**
The Python tree in `aggregator/` is a prototype of fetching and parsing
for five shops and the reference for site behaviour; it is retired once
the .NET harvesters and adapters reach parity.

Read the vocabulary first. Every later section uses those words and no
others.

## Goal

A multi-purpose ingestion platform. A **project** is a tenant. Inside it,
a tree of **operations** says what we want: `clothing/shoes`,
`electronics/laptops`, each with the providers that supply it as leaves.
Each operation harvests only what it needs from its providers into a
lake, adapts it into entities of its domain with ids of our own, and the
project serves them through an API, MCP or exports, always scoped by
project id. Today: shoes in North Macedonia. Tomorrow: electronics. Later:
car parts. Operations run side by side.

The platform does not crawl a whole site to answer a question. It learns
what a provider has once, then checks only what it needs: stock for the
products it already knows, details for the ones that lack them, one live
check for the product someone is asking about.

## Vocabulary

### The pipeline

| Term | Meaning |
|---|---|
| **Collector** | The whole pipeline: Harvester → Lake → Adapter → Store, under a Conductor. |
| **Provider** | The party whose data we ingest and whose ids we keep: a shop (`sportvision`), a brand (`adidas`). |
| **Source** | One site or endpoint of a provider: base URL, platform, rate limit floor, robots. `sportvision_mk`, `sportm_mk`. |
| **Harvester** | Fetches. Nothing else. Given a command, it fetches with a mechanism (plain HTTP, or a browser that clicks) and emits one raw item per page. A leaf: it never starts another harvest or an adapt. Not "connector", not "scraper", not "collector". |
| **Raw item** | One fetched thing: a listing page, a product page, a sitemap, a feed, the JSON a page loaded after a click. Keyed by project, source, kind, provider id; stamped with harvest time. |
| **Lake** | Where raw items live. Retention per project: full history, changes only, latest only. |
| **Adapter** | Reads raw items from the lake and converts them into entities of one domain. One per provider × domain. A leaf: it never starts a harvest or another adapt. Re-runnable and idempotent. |
| **Store** | Postgres. Entities in domain tables, plus everything the platform needs to run. One database for all projects. |
| **Node** | A device that executes harvest commands. Today the box. Later a Raspberry Pi abroad, a laptop, a cloud VM. Declares capabilities (http, browser) and location. |

### What runs, and how

| Term | Meaning |
|---|---|
| **Command** | The smallest unit of work. A provider plus an id, and the provider decides what happens: "fetch product 4711 from Sport M", "fetch listing page 3 from Sport M", "adapt all unadapted Sport M listing pages". Commands are code, registered per provider. |
| **Job** | A template, a checklist. The ordered list of commands to run. Knows *what* and *in which order*, nothing about speed or nodes. Jobs are data. |
| **Strategy** | *How* a job executes: mechanism, nodes and geo, pacing, batch or streaming adapt, retry budget. Strategies are data. The same job can run with different strategies; the same strategy can drive many jobs. |
| **Run** | Job X executed with strategy Y, for one project, with parameters, at a time. Progress, failures and administrator decisions live on the run. |
| **Conductor** | Runs a run. Holds the sequence, dispatches commands, counts what comes back, applies the retry budget, pauses for decisions. The only component that knows what comes next. |
| **Schedule** | When runs start. Nightly, hourly, on demand. Creates runs; nothing else. |
| **Pacing** | The gaps between requests inside a command. Part of the strategy. |
| **Retry budget** | How long a run keeps trying before it stops and asks. Part of the strategy. |

### What we produce

| Term | Meaning |
|---|---|
| **Entity** | The base of everything we produce: our deterministic id, project, provider, provider id, kind, source URL, harvest time. Categories, products and listings are all entities. |
| **Domain** | A set of entity kinds with their extra fields and their own tables. `Shoes` first; `Electronics`, `CarParts` later. |
| **Product** | Ours. One per project per real thing. Name, brand, sku, category, chosen images, domain fields. |
| **Listing** | One provider's view of a product. Their title and description, price, stock, sizes, branch availability, URL, provider id, and the dates `infoCheckedAt` and `stockCheckedAt`. A product has one listing per provider that sells it. |
| **Provider id** | The id the provider uses. May equal the brand `sku` or be a shop-internal id kept next to the `sku`. Always prefixed with the provider in keys. |

### Where things live

| Term | Meaning |
|---|---|
| **Project** | A tenant, and the ecosystem: the whole tree of operations and everything they produce. Owns its operations, sources, jobs, strategies, runs, lake items, entities and id seed. A hard partition: nothing is shared across projects, even when two projects ingest the same site. Exported, archived or deleted as a unit. |
| **Operation** | A node in the project's tree. It says *what we want*: `clothing`, `clothing/shoes`, `clothing/shoes/sportm`. An operation carrying a domain owns that common model. Operations run in parallel. |
| **Leaf operation** | An operation bound to one provider: `clothing/shoes/sportm`. It says how that provider fills the operation's model, and holds the job × strategy pairs for it. |
| **Namespace** | The path of an operation in the tree. Runs, listings, adapters and settings attach to a namespace. |

## Operations: the tree

```
project mk-market                  the ecosystem
├─ electronics                     operation, a grouping
│  ├─ laptops                      operation, domain Electronics
│  │  ├─ anhoch.mk                 leaf: provider anhoch.mk, its own job × strategy pairs
│  │  ├─ setec.mk
│  │  └─ neptun.mk
│  └─ keyboards                    operation, domain Electronics
│     ├─ anhoch.mk                 same source record as above, another leaf
│     ├─ setec.mk
│     └─ neptun.mk
└─ clothing                        operation, a grouping
   └─ shoes                        operation, domain Shoes
      ├─ sportm.com.mk             leaf
      └─ sportvision.mk            leaf
```

Rules:

- **Every node is an operation.** The project is the root and the
  ecosystem; a leaf is an operation bound to a provider. Depth is not
  fixed; if laptops ever needs `gaming` and `office`, that is one more
  level. There is no separate "ecosystem" level.
- **Job × strategy pairs can sit on any node.** A leaf's pairs are its
  own: `shoes/sportm` discovers with a burst, `shoes/sportvision` checks
  stock with a browser strategy because of the sizes. A pair on a parent
  is the default for children that define none.
- **Running a node runs everything under it, in parallel.** "Run
  `clothing/shoes` stock" starts one run per leaf, each with its own
  strategy. "Run `clothing/shoes/sportm` stock" starts one.
- **Settings inherit down.** A request budget on `electronics` applies to
  every leaf under it. The pacing floor sits on the source and applies
  wherever that source appears.
- **One provider, one source record, many leaves.** anhoch.mk under
  laptops and under keyboards is one source: one rate floor, one budget
  across both, one quarantine when it blocks a node. What differs per leaf
  is the jobs and the adapter.
- **The adapter is selected by namespace.** `electronics/laptops/anhoch.mk`
  maps to the Anhoch laptops adapter. Nothing is guessed from the page.
- **A listing belongs to exactly one namespace.** A keyboard never shows
  up in `laptops`.

### The apples rule

The common model is the centre, and the operation owns it. We want
apples; the stores are where we get them. We go to each store, pick
apples, and leave.

- An operation defines its model. `shoes` says what a Shoes product and
  listing look like. Sport M's site structure never changes that.
- A leaf only says how its provider fills that model: which category
  slugs, brand codes and page fields map onto Shoes.
- We harvest only what the operation needs. The discover job under
  `shoes/sportm` walks the shoes category, not the whole site. If a
  provider cannot filter and a page comes back mixed, the adapter takes
  the apples and ignores the rest.
- A provider never decides which common models get updated. A page
  harvested under `shoes/sportm` can only produce Shoes entities. Sport M
  clothes, one day, is a new leaf under `clothing/<something>` with its own
  jobs, never a side effect of the shoes run.
- There is no shared "discover everything from provider X" job feeding
  several operations. Each operation discovers its own, even from the same
  store.

## The pipeline

```
                      ┌─────────────────────────────────────────────────┐
  schedule / CLI ───▶ │ Conductor   run = job × strategy × project      │
                      │ dispatches commands, counts items, applies      │
                      │ retry budget, pauses for decisions              │
                      └──────┬──────────────────────┬───────────────────┘
                harvest.command               adapt.command        ▲ item.completed
                             ▼                      ▼               │
 providers ──HTTP──▶ Harvester ─raw.item─▶ Lake ─lake.item.stored─▶ Adapter ─entity.upserted─▶ Store ─▶ API · MCP · exports
 (on a node)        (fetch only)         (retention)              (raw → entity)            (by project id)
```

Every arrow is a RabbitMQ message. Harvesters and adapters know only
their input command and their output message. They never decide what
happens next; the conductor does.

### Conductor, runs, and what a command reads

A run attaches to a namespace. Its job is a list such as this one, on the
leaf `clothing/shoes/sportm`:

```yaml
job: sportm.discover
commands:
  - harvest: sportm.listing-pages      # the shoes category only, by brand
  - adapt:   sportm.listings           # pages → Listing + Product entities, no details yet
```

Other jobs on the same leaf:

```yaml
job: sportm.details
commands:
  - harvest: sportm.product-detail     # for every Sport M listing with no details, or stale ones
  - adapt:   sportm.products

job: sportm.stock
commands:
  - harvest: sportm.stock              # for every Sport M listing due for a stock check
  - adapt:   sportm.stock

job: sportm.live-check                  # parameter: one listing id
commands:
  - harvest: sportm.stock
  - adapt:   sportm.stock
```

A command does not receive a list from the previous command. It reads the
state of the store: "every Sport M listing with no details", "every
listing whose `stockCheckedAt` is older than its refresh interval". That is
why a stock job needs no listing walk, and why a listing can be created
from a single URL ("watch this product") and have its details and stock
harvested by the ordinary jobs.

A run keeps a live record, updated on every message:

- **run**: namespace, job, strategy, project, parameters, who started it,
  state, started, finished; a run started on a parent node is one run per
  leaf, grouped;
- **run command**: one per line of the job; order, state, derived totals;
- **run item**: one per message; queued, running, done, failed, retrying,
  skipped, waiting for decision; attempts, node, started, finished, error
  class and text, the lake key or entity ids it produced;
- **run event**: an append-only log; every state change and every
  administrator decision.

Progress for the CLI, the API or a page is a query over run items, never a
counter.

### Strategy: how a run executes

```yaml
strategy: slow-and-spread
mechanism: http                       # or browser
nodes: { count: 1, geo: any }         # or geo: eu, or a named node
pacing: { mode: spread, window: 24h, jitter: 30s }
adapt: batch                          # or streaming
retry:
  attemptsPerItem: 3
  deadline: 36h
  failureRatio: 0.2                   # stop the command if more than 20 % of items fail
  nodesTried: 2                       # give up on an item after two different nodes failed it
```

Pacing modes: **burst** (everything at once), **interval** (one request
every N seconds), **jitter** (random gap in a range), **spread** (N requests
spread over a window), **budget** (at most N per hour against a host). The
source carries the politeness floor; a strategy can only be slower than
it.

### Failure, the retry budget, and decisions

- Failure is per item, never per batch. One blocked node fails its own
  items; those go back to the queue for another node, and the node is
  quarantined for that host for a while. The other 99 products never
  notice.
- The retry budget says how long to keep trying: attempts per item, a
  deadline for the command, a failure ratio, nodes tried, cost later.
- When the budget is spent, the item, or the whole command if the ratio
  tripped, goes to **waiting for decision** and the run pauses there. The
  system never marks anything failed on its own.
- An administrator decides: retry on another node, retry later, skip these
  items, abort the run, quarantine the provider. CLI first, a page later.
  Every decision is a run event.

### Harvester

- Input: a `harvest.command` with the command name, provider, the ids to
  fetch, the strategy's mechanism and pacing.
- Does: fetches, with the source's politeness floor and the strategy's
  pacing, on the node the strategy selected.
- Output: one `raw.item` per page: `{ project, source, kind, providerId,
  url, harvestedAt, contentType, body | blobRef }`. The body rides in the
  message under a size cap; above it the harvester writes a blob and sends
  a reference. Then `item.completed` to the conductor.
- Mechanisms: HTTP; a browser for pages that need clicks (sizes per branch,
  forum buttons). A browser harvest is an ordinary command that needs a
  node with a browser, paces slower, and emits whatever the page loaded,
  often the site's own JSON.
- Does not: parse, normalize, know what a product is, or start anything.

Commands known today, from the prototype: NBSHOP sitemap, NBSHOP listing
walk with filter slugs, NBSHOP product page, Sport M paginated catalog
with brand codes, Sport M product page. See `docs/research/`.

### Nodes and rate limits

- A node executes harvest commands. It declares mechanisms (http, browser)
  and location, and paces per host on its own IP.
- The conductor keeps a per-source budget across all nodes and all
  operations: a hundred polite IPs hitting one shop at once still looks
  like an attack, and so do the shoes run and the clothes run arriving in
  the same hour.
- The box is the first node and talks to RabbitMQ directly. Nodes outside
  the house never join RabbitMQ: they pull work and post raw items through
  a small HTTPS work API with a per-node token. The lake writer never sees
  the difference. A Raspberry Pi is fine; an Arduino is below the line.

### Lake

- Key: `project / source / kind / providerId`; every item carries
  `harvestedAt`.
- Retention per project: **full history** (every harvest a new version),
  **changes only** (a new version only when the body hash differs),
  **latest only** (overwrite).
- Storage (proposal): bodies compressed on disk or S3-compatible object
  storage; `lake_items` index in Postgres (key, version, harvestedAt,
  hash, size, location). Disk first.
- Publishes `lake.item.stored { project, key, version }`; answers queries
  by key or time for re-runs and later aggregations.
- Price history, where a project keeps history, is a reader of the lake,
  not a special table.

### Adapter

- Input: an `adapt.command` naming the namespace, which selects the
  adapter, and the lake items to read, either as they land (streaming) or
  once the harvest command is done (batch), as the strategy says.
- Does: parses the provider's raw shape, maps it to entities of the
  domain, assigns our ids, keeps provider id and `sku` both, sets
  `infoCheckedAt` or `stockCheckedAt` on the listing.
- Output: `entity.upserted` messages, one per entity, consumed by the
  store; then `item.completed`.
- Idempotent: the same raw item always yields the same entities with the
  same ids. Because ids are deterministic, an adapter can reference an
  entity it has not seen yet, a product's category, by computing its id.

### Ids

Deterministic: a UUIDv5-style hash of the project seed and the
provider-qualified key, `uuid5(projectSeed, "sportvision:listing:12345")`.
The same provider item in two projects yields two different ids; the same
item harvested twice in one project yields the same id. The seed is the
project id.

### Entities, domains, products and listings

```
Entity:   id, projectId, namespace, provider, providerId, kind, sourceUrl,
          harvestedAt, createdAt, updatedAt

Product:  Entity + name, brand, sku, categoryId, images, domain fields
Listing:  Entity + productId, title, description, price, oldPrice, currency,
          availability, sizes[] (label, system, ean, inStock, branch),
          url, refreshInterval, infoCheckedAt, stockCheckedAt
Category: Entity + name, parentId, path

Shoes domain fields on Product: colourway, model code.
Electronics, CarParts (later): their own.
```

The dates live on the listing because stock at one shop and stock at
another are checked by different runs at different times. The product
carries a derived "any listing in stock". Matching listings into one
product happens inside a project, on `sku` where providers expose it and
by rules where they do not. `refreshInterval` is a generic field on every
listing so a job can select "due for a check"; nothing in it is specific to
a domain.

### Store

Postgres, one database, `projectId` on every row, including sources,
jobs, strategies, runs and the lake index. Every index starts with
`projectId`. Export, archive and delete of a project are "everything where
projectId = X".

Platform tables: `projects(id, name, lakeRetention, seed)`,
`operations(id, projectId, parentId, path, domain, sourceId, settings)`,
`operation_jobs(operationId, jobId, strategyId, schedule)`, `providers`,
`sources`, `nodes`, `jobs`, `strategies`, `runs`, `run_commands`,
`run_items`, `run_events`, `lake_items`. The domain lives on the
operation, not on the project.

### Serving

Everything that reads takes a project id: the ASP.NET Core API, an MCP
server, CSV/Parquet exports, dashboards. A read returns what is known plus
`infoCheckedAt` and `stockCheckedAt`; the caller decides whether that is
fresh enough. A live check is a run of the provider's live-check job with
a priority strategy, for one listing. Who may trigger one, and how often,
is a per-project policy, decided per tenant later.

### Brand catalogs and matching

A brand's own catalog (adidas first, Nike second) is another provider
with its own commands and adapter into the same domain. Its output is
products and listings like any other; matching to shop listings on `sku`
is in-project work that comes after the pipeline runs end to end.

## Messaging

RabbitMQ, one queue per arrow:

| Message | Producer | Consumer |
|---|---|---|
| `harvest.command` | Conductor | Harvester on a node (or the work API for external nodes) |
| `raw.item` | Harvester | Lake writer |
| `lake.item.stored` | Lake writer | Conductor (counting), Adapter in streaming mode |
| `adapt.command` | Conductor | Adapter |
| `entity.upserted` | Adapter | Store |
| `item.completed` | Harvester, Adapter, Store | Conductor |

A priority queue for live checks. Retries with backoff and a dead-letter
queue per consumer. MassTransit over RabbitMQ is the default.

## Solution layout (proposed)

```
Collector.sln
src/Collector.Core/         Entity, domains, ids, message contracts, job and strategy schemas
src/Collector.Harvesting/   fetchers (http, browser), per-provider harvest commands, pacing
src/Collector.Lake/         lake writer, retention modes, lake queries
src/Collector.Adapting/     per-provider × domain adapters and adapt commands
src/Collector.Conducting/   conductor: runs, items, retry budget, decisions, schedule
src/Collector.Data/         EF Core DbContext, entities, migrations
src/Collector.Workers/      one host; the role it runs (conductor, harvester, lake, adapter) is configuration
src/Collector.Node/         the external node: pulls work over HTTPS, runs fetchers, posts raw items
src/Collector.Api/          project-scoped reads, run progress, admin decisions, work API for nodes
src/Collector.Cli/          run, decide, harvest, adapt, project export / archive / delete
tests/Collector.Tests/      xUnit; harvest commands and adapters against saved page samples
```

Libraries: AngleSharp for HTML, `System.Text.Json` for JSON-LD,
`IHttpClientFactory` with the standard resilience handler and a per-host
rate limiter, Playwright for the browser mechanism, EF Core + Npgsql,
MassTransit, xUnit.

## Build order

1. Solution skeleton; `Core` with Entity, ids, message contracts, the job
   and strategy schemas, the operations tree, the Shoes domain; `Data`
   with the platform tables, Product, Listing, Category, first migration.
   RabbitMQ and Postgres running locally.
2. Harvesting: HTTP fetcher, pacing, the NBSHOP and Sport M commands
   ported from the prototype; `raw.item`; lake writer with the three
   retention modes.
3. Conductor: jobs and strategies as data, runs with commands, items and
   events, retry budget, waiting for decision; CLI `run` and `decide`.
4. Adapters for Shoes on both platforms, producing Product and Listing;
   `discover` and `details` jobs end to end; CLI at parity with the Python
   `crawl`.
5. `stock` job with spread pacing; schedule; `live-check` job on the
   priority queue.
6. API: project-scoped reads with the two dates, run progress, decisions.
7. Node: `Collector.Node` and the work API; browser mechanism.
8. Brand catalogs and matching; project export, archive, delete. Retire
   `aggregator/`.

## Open decisions (owner: you)

- **Where it runs.** The first node needs an IP the sites allow (dsport.mk
  and adidas.com blocked the cloud session). RabbitMQ and Postgres on the
  box, in WSL, or on the Proxmox VM.
- **Lake bodies**: disk, S3-compatible store, or Postgres `bytea`. Disk
  proposed to start.
- **Message size cap** before a harvester offloads the body to a blob.
- **MassTransit or raw client.**
- **Live-check policy** per project: who may trigger, how often.
- **Refresh tiers**: `refreshInterval` exists on every listing from day
  one; the rule that sets it (popular daily, idle weekly) comes later.
- **Aggregations over the lake**: mechanism defined later.
