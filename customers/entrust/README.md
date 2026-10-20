# Entrust

Identity-verification checks (Document Check: Flash / Boost / Sherlock, per check, per
region), sold through Revenue Cloud and metered and rated in m3ter.

**The loop:** quote → order → activate (Revenue Cloud) → `ordersync` → account, bespoke plan,
negotiated pricings, account plan (m3ter) → usage, bill (m3ter) → `billsync` → liable
summaries (Revenue Cloud) → Generate Invoices.

## What is here

| Folder | What | How it is kept right |
| --- | --- | --- |
| `revenue-cloud/` | the Document Check catalog as rc-config JSON + `catalog.toml`; `archive/` is the retired 7 Oct EUR catalog, never applied | **generated** by `build_config.py` beside it — edit the generator, run it, `--check` compares; `tests/test_entrust.py` fails on drift |
| `m3ter/` | the m3ter product / meters / plan template config | (phase 4b — still in `m3ter-config/json/entrust/`) |
| `m3sh/` | the m3sh Order Handler and Usage Data workflow exports and their DSL; `python-handlers/` is the pre-m3sh Python half | (exports still in `m3ter-config/json/entrust/m3sh/`) |
| `snapshots/` | order `00000102`, Acme's bill — what the syncs replay | written by `ReadOrder` / `ReadBill` |
| `analysis/` | the catalog and quoting recommendation YAMLs (+ `build_quoting_recommendation.py`, `build_structure_chart.py` + `structure-chart/`), `m3ter-to-revenue-cloud.md` (mapping rationale, decisions D1–D7), the two quote-reconstruction workbooks, the Alloy account structure chart | hand-written / generated from the workbooks |
| `docs/` | the documentation set — open `index.html` | see below |
| `DECISIONS.md` | every open question in one place | hand-written |

### The documentation set (`docs/`)

| Page | Kind | Source |
| --- | --- | --- |
| `index.html` | hand-written | contents page |
| `end-to-end-flow.html` | hand-written | the lane diagram, 20 Oct |
| `document-check-console-walkthrough.md` / `.html` | hand-written | the click-by-click build of 13–14 Oct; the `.md` is the source, the `.html` its rendering |
| `verification-catalog-setup-guide.html` | **generated** | `build_setup_guide.py` from `../revenue-cloud/*.json` — regenerate, never edit |
| `claude-catalog-data-model.html` | **generated** (in `revenue-cloud-config/models/`, 2 Oct) | the 25-object catalog model; the template the billing model copies its runtime from |
| `claude-billing-data-model.html` | **generated** | `build_billing_data_model.py` from `billing-fields.json` (EntityParticle, 20 Oct) |
| `entrust-order-handler-structure.html`, `entrust-usage-data-structure.html` | **generated** read-outs | from the m3sh JSON exports (the structure-chart tooling in `m3ter-config`) |
| `order-sync-design.html`, `bill-sync-design.html` | hand-written | the two syncs' designs, 15 and 20 Oct; the running notes are `../../../docs/{ordersync,billsync}.md` |
| `catalog-history.md` | hand-written | what `revenue-cloud-config`'s README said about this catalog and its earlier shapes (moved 20 Oct) |
| `Entrust Product and Pricing Requirements.pdf` | source | the Salesforce team's solution notes, 13 Oct |
| `archive/` | superseded | `JG Entrust RCA Config.docx` (6 Oct, 33 Pack products + 2 bundles, USD/EUR) and `verification-catalog-build-steps.md` (7 Oct, 11 Pack products, Country attribute) — superseded by the walkthrough |

## Where things stand (20 Oct 2026)

Carried from `revenue-cloud-config/CLAUDE.md` when the catalog moved; paths updated.

**The org (m3ter-arm-260)** holds the build John made by hand on 13–14 Oct to the
Salesforce team's design: one Anchor `VC-DOC-CHECK` with a required, non-price-impacting
*Feature Type* attribute (Flash default / Boost / Sherlock), six resources
`RES-DOC-CHECK-{BOOST,SHERLOCK,FLASH}-{USA,ANY}` in `VERIFICATION-CHECK` (Type Custom),
six PURs + 0-quantity grants + policy rows, one Self binding policy, a 0.00 USD Term
Monthly PBE, *Entrust Catalog* / *Document Checks*, and two cards on the Standard Price
Book: *Document Check Rate Card - List (Base)* (6 entries with rates) and *Document Check
Rate Card - Commit (Tier)* (6 entries, 18 Override tiers 0–10k / 10k–25k / 25k+). All dates
`2026-09-01T19:00:00Z`. `revenue-cloud/` (79 records, 76 owned, 3 looked up) is generated
to match that exactly — change the org first, then the generator, never the JSON. On 14 Oct
`rc-config verify` was clean against it. **The tool has not written to the org** — `apply`
there would be `Unchanged 76`. Step 5 of the walkthrough (custom quote-line fields) is not
built.

**Order 00000102** (John's quote → order → activated, 14 Oct): every resource carries BOTH
cards on the line, order and asset (12 rows, `IsChosenRate` false), 18 tiers on the asset as
`AssetRateAdjustment`; Salesforce picks no card. The org is in the after-activation state
(asset `02iWs00000SreQbIAJ`, entitlement buckets, renewal opportunity, 7 billing schedules —
1 flat + 6 usage, all `ReadyForInvoicing`, org-default *USA - Advance* treatment). The
teardown is `revenue-cloud-config/scripts/teardown-after-assetization.apex` with this
build's codes, then the real end-to-end `destroy` → `apply` → `apply` → `verify` from empty
is the next tool milestone.

**Billing (current thread, 20 Oct):** `billsync` populates `UsageBillingPeriodItem` (the
liable summary) from m3ter bill data; the invoice run reads only that object. The usage
pipeline has never run in the org and no usage invoice exists yet. The chain, org read-back
and plan are `revenue-cloud-config/documents/billing-usage-to-invoice.md` and
`docs/bill-sync-design.html`.

**Next iteration (decided 15 Oct):** (1) tear down the 13–14 Oct build, then `rc-config
destroy` until the org holds only QuantumBit and the July Claude catalog; (2) settle with the
SI the region-band list / mapping owner and the commitment-card selection mechanism (price
book per model vs. *Willingness to Commit* as an attribute) — the second changes the
price-book layout, so it blocks the generator; (3) regenerate `revenue-cloud/` as feature ×
band resources with a catch-all band, one entry per resource per card, price books per model
if that wins; (4) `check` / `plan` / `apply` / `apply` / `verify` from empty; (5) quote →
order → activate and read `AssetRateCardEntry`: pass = one entry per resource per asset.
The open questions behind (2) are in `DECISIONS.md`.

Earlier shapes: the 8 Oct one-Pack / twelve-resource config and the 7 Oct eleven-product
config are in `revenue-cloud-config`'s git history (`f965adb`, `65902ea`); the 6 and 7 Oct
documents are in `docs/archive/`.

## Commands

```bash
rc-config check  --config-dir customers/entrust/revenue-cloud                # offline
uv run pytest tests/test_entrust.py                                           # the catalog against the simulated org
python3 customers/entrust/revenue-cloud/build_config.py [--check]            # regenerate / compare the config
python3 customers/entrust/docs/build_setup_guide.py                           # regenerate the setup guide
python3 customers/entrust/docs/build_billing_data_model.py                    # regenerate the billing data model
rc-config plan | verify | apply | destroy --org m3ter --config-dir customers/entrust/revenue-cloud   # John's terminal
```
