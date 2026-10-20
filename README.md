# m3ter-rc-config

John Griffin's repo for the **m3ter ↔ Salesforce Revenue Cloud integration**: the sync
code that carries an activated Revenue Cloud order into m3ter and a rated m3ter bill
back into Revenue Cloud's usage chain, and the customers — Entrust first — that span
both platforms.

This README is the single source of truth for how the repo is laid out and worked on.
`CLAUDE.md` holds the working rules for Claude sessions and points back here.
`docs/restructure-plan.md` is why this repo exists and what moves into it from where.

---

## Where things live

Three repos, one loop. The two platform repos are **tools**; this one is the
**integration** and depends on both as editable path dependencies (sibling checkouts).

| | Local (Mac) | GitHub | Role |
| --- | --- | --- | --- |
| m3ter tool | `~/PycharmProjects/m3ter-config` | `johngriffin00/m3ter-config` (`master`) | `m3sdk`, `m3shsdk`, `m3utils`; generic config/usage scripts; m3ter-only customer JSON |
| Revenue Cloud tool | `~/PycharmProjects/revenue-cloud-config` | `johngriffin00/revenue-cloud-config` (`main`) | `rc-config` (idempotent catalog build/teardown), simulated org, platform docs |
| this repo | `~/PycharmProjects/m3ter-rc-config` | `johngriffin00/m3ter-rc-config` (`main`) | syncs, Salesforce SDK, webhook front doors, `customers/` |

Rule: **a customer that spans both platforms lives here** (`customers/<name>/`); an
m3ter-only customer stays in `m3ter-config/json/<name>/`.

Other resources: Salesforce org alias `m3ter` (`admin@m3ter-arm.260`, REST API pinned at
v66.0); m3ter org credentials in `parameters/<org>.env` (never committed); local Postgres
`customerdb`, schema `entrust`; Google Drive `Entrust / m3sh Workflows`.

## Repo layout

```
sync/
  core/         bricks shared by every sync: SyncContext, Step/run_steps, dates, SalesforceStep
  ordersync/    activated order → m3ter Account, bespoke Plan + negotiated Pricings, AccountPlan
  billsync/     rated m3ter bill → UsageSummary, UsageRatableSummary, UsageBillingPeriodItem
salesforcesdk/  the thin Salesforce SDK the syncs use (sf CLI token, SOQL paging, writes)
webhooks/       Flask front doors (order activated → sync_order; bill created/updated → sync_bill)
customers/
  entrust/
    README.md       the customer's loop on one page
    DECISIONS.md    the one open-questions / decision log
    m3ter/          m3ter JSON config (applied with the m3ter tool)
    revenue-cloud/  rc-config JSON + catalog.toml + the generator that writes them
    m3sh/           m3sh workflow exports and their decompiled DSL
    snapshots/      saved Salesforce orders, m3ter bills, org dumps — what the syncs replay
    analysis/       recommendations, mapping rationale, quote reconstructions
    docs/           the documentation set (index, end-to-end flow, walkthroughs, designs)
tests/
docs/             repo-level docs (the restructure plan)
parameters/       gitignored credentials
```

`customers/entrust/README.md` is the map of the customer folder. A customer folder holds
everything about that customer and one thing the syncs import: `mapping.py`.

## Install and run

```bash
uv sync --extra dev          # installs both tools editable from ../m3ter-config and ../revenue-cloud-config
uv run pytest                # tests/test_skeleton.py proves the wiring
uv run ruff check sync salesforcesdk webhooks tests
```

The syncs:

```bash
set -a; source parameters/m3ter.env; set +a
uv run python -m sync.ordersync.sync_order --order 00000102 [--dry-run] [--from-file customers/entrust/snapshots/orders/00000102.json]
uv run python -m sync.billsync.sync_bill --bill <id> [--dry-run] [--latest --account <code>]
#   both take --customer <name> (default entrust): customers/<name>/mapping.py and snapshots/
rc-config check --config-dir customers/entrust/revenue-cloud     # the Revenue Cloud catalog, from here
uv run pytest                                                      # 29: the sync replays + the catalog against the simulated org
```

Live runs against the orgs are John's terminal; Claude proves bricks offline against the
snapshots with stubbed clients — `tests/test_replay.py` runs both syncs end to end in
`--dry-run` from `customers/entrust/snapshots/` with fake m3ter and Salesforce clients that
answer the reads and refuse every write.

### How the syncs are built

Lego, not scripts. `sync/core/` holds what every sync shares: `Step` (one `run(ctx)`
brick) and `run_steps` (run the list, stop at the first failure); `BaseSyncContext`
(snapshot / state / log, lazy m3ter and Salesforce clients); `SalesforceStep`
(find-or-create by natural key with dry-run honoured); `dates` (both directions:
Revenue Cloud's inclusive 23:59:59 ↔ m3ter's exclusive midnight) and `soql` helpers.
Each sync is a package of bricks and one parent script, and keeps the design notes in
its docstrings — `sync/ordersync/sync_order.py` and `sync/billsync/sync_bill.py` are the
place to start reading. Nothing in `sync/` knows about Document Check: the catalog-specific
lookups are `customers/<name>/mapping.py`, loaded by `sync/core/customer.py` for the
`--customer` the sync runs for (default `entrust`), together with that customer's
`snapshots/`. A second customer is a second folder.

## Status

**20 Oct 2026 — phase 3 done.** `sync/` (ordersync, billsync, core), `salesforcesdk/`,
the Entrust snapshots and the legacy Python handlers moved here from `m3ter-config`;
both syncs replay offline from the snapshots (`tests/test_replay.py`, 7 tests). Behaviour
is unchanged from the 15 Oct / 20 Oct versions except: the two context classes share
`BaseSyncContext`, the date helpers live in one module, and snapshots are written under
`customers/entrust/snapshots/`. Confirmed live the same evening: the order sync replayed
from the 00000102 snapshot in `--dry-run` against the m3ter org from John's terminal —
everything found via external mapping, nothing to create.

**20 Oct 2026 — phase 4 done.** The Entrust catalog config and its generator, the
documentation set, the analysis models and `tests/test_entrust.py` moved here from
`revenue-cloud-config`, which gained `rc_config.testing` (the simulated org and CLI
harness) so the catalog test runs from here against the same fake org; the m3ter config,
account dumps, m3sh exports and DSL moved from `m3ter-config`, which keeps a frozen copy
of the exports as its round-trip test corpus and now takes config paths on
`create_config.py`.

**20 Oct 2026 — phase 6 done.** `--customer`: `mapping.py` lives in the customer folder
and the syncs are customer-agnostic. **The restructure is complete** (`docs/restructure-plan.md`);
what remains is ordinary work, starting with the next iteration in
`customers/entrust/README.md`. Next: the Entrust next iteration (`customers/entrust/README.md` § Where things stand), and
the first live run of `billsync` from here.
