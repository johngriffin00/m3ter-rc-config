# Entrust — decisions and open questions

One place for the questions that the walkthrough, the setup guide, the sync designs and
the end-to-end flow each used to restate. Collected 20 Oct 2026 from those documents;
the pages link here rather than repeating them. Decided items keep their date and
reason; open items say what would settle them.

## Decided

| Date | Decision | Reason / evidence |
| --- | --- | --- |
| 13 Oct | One Anchor product (`VC-DOC-CHECK`), not one product per check | The SI's design: one product serves all three selling models; attribute + resources do the distinguishing |
| 13 Oct | *Feature Type* is a selector, not price-impacting | All pricing lives on the resource / rate card entries |
| 13 Oct | Usage resource per feature × region, 0-quantity grant on each, Charge Overage yes | Every check is overage; the asset carries a default rate for unquoted usage |
| 13 Oct | The commitment is custom quote-line fields, not a platform Commit grant | "Monetary commitments are not supported downstream" (SI) |
| 14 Oct | Card selection is not the catalog's job | Both cards reach the line, order and asset; `IsChosenRate` false on all 12 rows; Salesforce picks neither |
| 15 Oct | `ordersync`: bespoke plan per order line, plan-level pricings from the List (Base) card | A negotiated rate is a Pricing on a Plan; bespoke keeps one customer's rates from reaching another |
| 20 Oct | `billsync` writes the liable summary (plus summary + ratable), bypassing Revenue Cloud's own usage pipeline | m3ter has already aggregated and rated; the invoice run reads only `UsageBillingPeriodItem` |
| 20 Oct | One definition of quantities: total = quantity, overage = priced bands, debited = total − overage | The two m3sh halves disagreed about `ConsumptionUnits` |
| 20 Oct | The join from a bill line to Revenue Cloud is the Pricing (`pricing_<TUE Id>`), not AccountPlan custom fields | Six TUEs on one AccountPlan |

## Open

| Question | Where it shows up | What settles it |
| --- | --- | --- |
| Which rate card a committed customer's line uses, and how the line says so (price book per commitment model vs. a *Willingness to Commit* attribute with a rate adjustment) | `ordersync/mapping.RATE_CARD`; the warning in `step_pricing.py`; the generator's price-book layout | Decision with the SI; then the Revenue Cloud build and the sync both change |
| Rates per country: region bands A–G with a country-to-band mapping outside the rate card (custom metadata), catch-all band | Resource naming (`-USA`, `-ANY`); the generator gains a region column | SI owns the band list; the generator regenerates feature × band |
| The commitment itself: a m3ter Balance (Commitment) fed from `OrderItem.UnitPrice`, replacing the standing-charge stand-in | `ordersync` parked table; `billsync` NetLines pass-through | Build the Balance brick; then debited ≠ 0 in NetLines |
| Parent or child bucket on the liable summary | `billsync/step_resolve`; one constant | Run the platform's own pipeline once and read which bucket its liable summary references |
| Status on create: `ReadyForInvoicing` directly, or `New → InProgress → ReadyForInvoicing` | `billsync/policy.status_for` | Test on the first bill |
| Does a liable summary with no usage summary behind it invoice? | Whether a UBPI-only first pass is legitimate | Test on the first bill |
| Billing-frequency alignment: Revenue Cloud's schedule bills from the 14th; m3ter's AccountPlan on its own cycle | Invoice-line dates vs. `NextBillingDate` | Decide which cycle is the truth, or align the AccountPlan start |
| `GrantBindingTargetId` left null on the six first UsageSummaries | `billsync` 20 Oct run | Backfill or accept; the invoice-run match wants it set |
| Bundle PLG (`VC-BUNDLE-PLG`, EUR): the m3ter formula names three components, the plan zeroes two | Older catalog shape; may be moot | Confirm with the m3ter owner before it is ever built |
