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

The directories exist; the contents arrive phase by phase (`docs/restructure-plan.md`
§ Phases). Until phase 3 the syncs still run from `m3ter-config/demoscripts/`.

## Install and run

```bash
uv sync --extra dev          # installs both tools editable from ../m3ter-config and ../revenue-cloud-config
uv run pytest                # tests/test_skeleton.py proves the wiring
uv run ruff check sync salesforcesdk webhooks tests
```

Once the syncs have moved (phase 3):

```bash
set -a; source parameters/m3ter.env; set +a
uv run python -m sync.ordersync.sync_order --order 00000102 [--dry-run] [--from-file customers/entrust/snapshots/orders/00000102.json]
uv run python -m sync.billsync.sync_bill --bill <id> [--dry-run] [--final]
rc-config check --config-dir customers/entrust/revenue-cloud     # the Revenue Cloud catalog, from here
```

Live runs against the orgs are John's terminal; Claude proves bricks offline against the
snapshots with stubbed clients (same rule as the m3ter tool).

## Status

**20 Oct 2026 — skeleton.** Layout, packaging and the dependency wiring exist and are
tested; nothing has moved yet. Next: `docs/restructure-plan.md` phase 3 (the syncs).
