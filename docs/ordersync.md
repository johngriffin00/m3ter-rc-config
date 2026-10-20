# Order activation → m3ter sync (`sync/ordersync/`)

Moved from `m3ter-config/README.md` on 20 Oct 2026 with the code; paths updated, text otherwise as written on 15 Oct. The shared bricks (`Step`, `BaseSyncContext`, `dates`, `soql`) now live in `sync/core/`.


**What it is.** The Python port of the m3sh *Order Handler* workflow set: when
an order is activated in Revenue Cloud, create everything the customer needs
in m3ter. Built 15 Oct 2026 as a teaching exercise, one brick at a time, and
proven end to end against order `00000102` (Acme, Document Check) in the
JPG Playground org (`parameters/m3ter.env`).

```bash
set -a; source parameters/m3ter.env; set +a                  # m3ter creds; Salesforce comes from the sf CLI session
uv run python -m sync.ordersync.sync_order --order 00000102 --dry-run   # reads both sides, posts nothing
uv run python -m sync.ordersync.sync_order --order 00000102             # the real thing; safe to re-run
uv run python -m sync.ordersync.sync_order --from-file customers/entrust/snapshots/orders/00000102.json --dry-run
uv run python -m sync.ordersync.sync_order --inspect                    # read-only tour of the m3ter org
uv run python -m sync.ordersync.sync_order --describe OrderItemRateCardEntry   # sObject field names
```

**The bricks.** `sync_order.py` is the parent script: it builds a `SyncContext`
(the m3sh "state": `snapshot` = what Salesforce said, `state` = what m3ter steps
created, `log`) and runs a list of `Step`s in order. Every m3ter step looks
before it creates — `ExternalMapping.find(Salesforce/<table>/<id>)`, then by
code — so a re-run finds everything and creates nothing. `--dry-run` still does
the lookups but prints payloads instead of posting.

| Step | File | Salesforce → m3ter | Key (ExternalMapping) |
|---|---|---|---|
| 1 | `sf_order.py` `ReadOrder` | Order, Account, Contacts, OrderItems, TransactionUsageEntitlements, Assets, UsageEntitlementBuckets, OrderItem/Asset rate card entries → `ctx.snapshot`, saved to `customers/entrust/snapshots/orders/<OrderNumber>.json` | — |
| 2 | `step_account.py` `EnsureAccount` | Account → `Account` (code = SF Account Id, email from the first Contact, currency from the rate unit, billing address) | `Salesforce/Account/<Id>` |
| 3 | `step_plan.py` `EnsurePlans` | OrderItem → bespoke `Plan` from the product's template (`mapping.py`), `standingCharge` = UnitPrice × Quantity, code `<product>_<OrderNumber>` | `Salesforce/OrderItem/<Id>` |
| 4 | `step_pricing.py` `EnsurePricings` | TransactionUsageEntitlement + its rate row on `mapping.RATE_CARD` → plan-level `Pricing` (aggregation + segment from `mapping.py`, one band, `unitPrice` = NegotiatedRate, 0.0 included) | `Salesforce/TransactionUsageEntitlement/<Id>` |
| 5 | `step_accountplan.py` `EnsureAccountPlans` | Asset lifecycle → `AccountPlan` (end shifted +1 s to m3ter's exclusive midnight, `dates.py`) | `Salesforce/Asset/<Id>` |

`mapping.py` is the only catalog-specific brick: product code → plan template,
`RES-DOC-CHECK-<FEATURE>-<REGION>` → aggregation + segment (`USA` →
`{country: USA}`, `ANY` → `{}`), the plan code format, and `RATE_CARD`.
`salesforcesdk` gained `SalesforceCliAuth` (token from `sf org auth
show-access-token`, org alias `m3ter`, API v66.0) and `query_all` (paging,
raises on SOQL errors).

**Decisions made on the way, and why**

- *Plan per OrderItem, not per Order.* A Plan belongs to one PlanTemplate
  which belongs to one Product; an order with two products needs two plans.
  For this catalog every order yields one plan.
- *Bespoke plan with plan-level Pricings* rather than attaching the shared
  default plan: a negotiated rate is a Pricing on a Plan that overrides the
  template's, and a plan carrying one customer's rates must never be
  attachable to another. (Entrust production does the same:
  `checks_<opportunityId>`.) The template pricings stay untouched.
- *Rate card.* Order `00000102` carried BOTH cards on every resource with
  `IsChosenRate = false` on all 12 rows — Salesforce chose neither. The six
  Base rows carried negotiated rates; the six Commit (Tier) rows were null
  with their 18 bands on the asset untouched. For now `mapping.RATE_CARD`
  picks Base and the step warns if Salesforce ever chooses a different card.
  John is revisiting the Revenue Cloud side so the choice is made at quote
  time (separate price books, or the *Willingness to Commit* field).
- *The 1,000 USD* line price is a `standingCharge` on the plan — the
  first-pass stand-in for the commitment.
- *Dates.* Revenue Cloud ends a lifecycle at 23:59:59 inclusive; m3ter is
  exclusive, so the AccountPlan ends at midnight of the next day (what m3sh
  does with `dateAdd(…, 1, "SECONDS")`).
- *m3ter rule to remember:* one active AccountPlan per Product per Account
  unless the org allows overlapping plans — a renewal must start after the
  previous AccountPlan ends.

**Design document.** `customers/entrust/docs/order-sync-design.html` —
overview, structure chart of the Python, and the full Salesforce → m3ter
object and field mapping tables; the companion to
`entrust-order-handler-structure.html` (the m3sh workflows it ports).

**Proof.** `customers/entrust/snapshots/orders/00000102.json` is the Salesforce snapshot;
`customers/entrust/snapshots/001Ws00005YYRPSIA5-config.json` is the m3ter dump of Acme after
the sync (`generate_json_from_existing_org.py`). Plan `vc_doc_check_00000102`,
six pricings matching the negotiated rates, AccountPlan 14 Oct → 14 Nov.

**Parked for the next pass** (in this order): the commitment as a
`Commitment` or `Balance` instead of a standing charge, replacing the
m3sh Balance/Balance Cloner steps; the Commit card's tiers as `pricingBands`
(`cumulative` true for tiered, false for volume — the template pricings are
`cumulative: true`, the sync's are the API default `false`, harmless with one
band); amendments and re-activation (end-date pricings, new ones); the Flask
front door in `webhooks/` calling `sync_order.run(order_ref)` with
`SalesforceAuth` (connected app) swapped in for `SalesforceCliAuth`.

**Running from Claude's shell is not possible:** neither the Mac sandbox
shell nor the cloud container can reach `api.m3ter.com` (proxy 403) and the
sandbox has no `sf` CLI, so every live run is John's terminal; Claude reads
the saved snapshot and dumps. `uv run` from the sandbox also rebuilds `.venv`
with sandbox paths — avoid it there.

---

