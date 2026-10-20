# Bill → Revenue Cloud usage sync (`sync/billsync/`)

Moved from `m3ter-config/README.md` on 20 Oct 2026 with the code; paths updated, text otherwise as written on 20 Oct. `SalesforceStep`, `inclusive_end` and `sf_datetime` now live in `sync/core/`.


**What it is.** The Python port of the m3sh *m3ter -> SF RCA Usage Data*
workflow set (exports in `customers/entrust/m3sh/exports/`, chart in
`customers/entrust/docs/entrust-usage-data-structure.html`): when an m3ter
bill is ready, turn each USAGE line item into the Revenue Cloud usage records
Billing invoices from. Built 20 Oct 2026 the same way as the order sync — one
brick at a time, dry-run / run / re-run — and proven end to end against Acme's
November bill (`a080007f`, order `00000102`) in JPG Playground and the `m3ter`
Salesforce org, idempotent on re-run.

```bash
set -a; source parameters/m3ter.env; set +a
uv run python -m sync.billsync.sync_bill --latest --account 001Ws00005YYRPSIA5 --dry-run
uv run python -m sync.billsync.sync_bill --bill <bill uuid>
uv run python -m sync.billsync.sync_bill --from-file customers/entrust/snapshots/bills/<file>.json   # replay a snapshot
```

**The bricks.** `sync_bill.py` builds a `BillSyncContext` (`snapshot` = the
bill and ALL its line items, `state`, `log`; lazy m3ter and Salesforce
clients) and runs the steps in m3sh order. `sf_step.py` is what the writing
bricks share: `find_or_create` / `create_or_update` with `--dry-run` honoured
(lookups real, writes printed), `CREATE_ONLY` fields (`Status`,
`GrantBindingTargetId`) sent on create and stripped on update, and the date
rules (`2026-10-14T00:00:00Z` form; `inclusive_end()` = m3ter's exclusive
midnight − 1 s).

| Step | File | Does | Keyed on |
|---|---|---|---|
| 1 | `read_bill.py` `ReadBill` | Bill header + every line item (`Bill.line_items()`, the paged endpoint) → `ctx.snapshot`, saved to `customers/entrust/snapshots/bills/<accountCode>-<billDate>-<id>.json`; warns if not `APPROVED` | — |
| 2 | `resolve.py` `Resolve` | m3ter Account → Salesforce Account (`ExternalMapping.find_by_m3ter`), Pricing → TUE (the order sync's mapping; `pricing_<TUE Id>` code as fallback), one SOQL for the TUEs (`AssetId, AccountId, EntitlementUomId, GrantBindingTargetId`) and one for their buckets; grant/overage netting as `handlerRC.py`; → `ctx.state['lines']` | child bucket (`Parent.Type = 'UsageEntitlementBucket'`) covering the service period, else the top-level one |
| 3 | `step_usagesummary.py` | `UsageSummary` — the consumption: `DebitedUnits`, `ConsumptionUnits`, `OverageUnits`, UoM, bucket, dates | SOQL on Account + Asset + StartDateTime + EndDateTime + bucket |
| 4 | `step_ratablesummary.py` | `UsageRatableSummary` — the rated view: `NetUnitRate`, tier/overage quantities + UoMs, `TotalAmount`, `RatingDecisionDateTime` | the summary's `RatableSummaryId` (null → create) |
| 5 | `step_ubpi.py` | `UsageBillingPeriodItem` — the billable line: `TotalUsedQuantity`, `CurrencyIsoCode`, `OverageQuantity/Amount` | the summary's `LiableSummaryId` (null → create) |
| 6 | `step_link.py` `LinkUsageSummary` | `RatableSummaryId` + `LiableSummaryId` onto the summary whenever missing or different | — |
| 7 | `step_link.py` `UpdateBucket` | `BucketBalance` + `ConsumedEntitlement` on the bucket, as m3sh did | — |

**Decisions made on the way, and why**

- *`GrantBindingTargetId`.* Required on `UsageRatableSummary` in this org
  ("Select a Grant Binding Target…") — a field newer than the API 65 the m3sh
  workflows used; polymorphic (Account, Asset, Contract, custom binding
  object) and create-only. The TUE carries it (the Asset — a "Self" binding),
  so every record gets the TUE's value, Asset as fallback. The six Acme
  UsageSummaries created before this was known have it null and cannot be
  edited; delete and re-sync if they must agree.
- *Grant/overage netting is a no-op for Entrust.* Across all 14,918 Entrust
  bills in Postgres there is no `USAGE_CREDIT` or `OVERAGE_USAGE` line, so
  `handlerRC.py`'s netting never fired and `ConsumptionUnits = DebitedUnits =
  TotalUsedQuantity = quantity`. That settles the `ConsumptionUnits`
  inconsistency the chart flagged. The netting stays as the faithful port.
- *Two deliberate departures, each one constant:* `TOTAL_AMOUNT = 'subtotal'`
  on the ratable summary (the handler sent overage × rate, i.e. 0 for every
  Entrust line); `END_INCLUSIVE = True` on the UBPI so all three records end
  at 23:59:59 (m3sh passed the UBPI end raw).
- *State bleed fixed by construction.* The workflow's `sfUsageSummary` was
  never refreshed for a new summary, so the null-link checks read the previous
  line's record. Here brick 3 selects `RatableSummaryId, LiableSummaryId` per
  line and brick 6 links whenever missing — a run that dies half way is
  repaired by the next one instead of creating orphans.
- *Bucket fields as m3sh wrote them* (`BucketBalance` = used quantity) — looks
  wrong for an entitlement with a grant; harmless for Entrust. One dict in
  `step_link.py` when the first granted entitlement arrives.
- *Pre-rated, not usage-only (decided 20 Oct 2026).* The asset's
  `AssetRateCardEntry` rows carry the same negotiated rates m3ter bills with,
  and the org has the native rating pipeline (`RatingRequest`,
  `RatingRequestBatchJob`, `RatingFrequencyPolicy`), so for pay-as-you-go
  the sync could stop at the `UsageSummary` and let Salesforce rate and
  create the other two records itself. Rejected: one consistent pattern
  designed for the hardest case — m3ter's balance drawdown and tiered
  pricing, which Salesforce cannot reproduce ("monetary commitments are not
  supported downstream") — beats two modes. m3ter rates; the sync copies the
  answer; the UBPI's `OverageAmount` is what Billing invoices.
- *What Billing invoices.* The UBPI's only money field is `OverageAmount`;
  the invoice line takes `Quantity` from `TotalUsedQuantity` and `LineAmount`
  from `OverageAmount`. "Overage" means billable beyond the entitlement, so
  with no balance everything used is overage (`Resolve.overage()`): the
  m3sh/handlerRC value (m3ter's never-present `OVERAGE_USAGE` line) made
  every invoice zero — unnoticed because Entrust invoiced from m3ter. A
  balance that covers the bill → zero; a balance that runs out mid-bill →
  the sync stops until the per-line split is agreed.
- *Trigger.* The Acme bill is `PENDING`; eventually the sync runs on bill
  approval (`billing.bill.approved` → `sync_bill.run(bill_id)` behind the
  Flask front door, like the order sync). Not built yet; `ReadBill` warns.

**Proof.** `customers/entrust/snapshots/bills/001Ws00005YYRPSIA5-2026-11-01-a080007f-….json`
is the bill as read (one `STANDING_CHARGE` 433.33 for 1–14 Nov, six USAGE
lines 14 Oct → 1 Nov: Flash/Sherlock/Boost × USA/ANY at the negotiated
rates, Boost USA at 0.0). In the `m3ter` org: UsageSummaries
`1UAWs000001VB53OAG…`, ratable summaries `1GuWs000000xg4rKAA…`, UBPIs
`1HGWs00000FxKrhOAF…`, buckets UEB-0000000011…16.

**Parked:** the approval trigger + Flask front door; a granted entitlement
(bucket semantics, the netting for real); multi-currency beyond the bill's
`currency`; `--latest` returns one bill, so an account's earlier bill (the
14 Oct → 1 Nov standing-charge slice) needs `--bill`.

---

