# m3sh workflow exports — usage data to Revenue Cloud

The m3sh workflow set that replaced the original Python `on_bill_change`
handler: it took the bill payload that handler posted (account, bill dates,
one entry per USAGE line item with the grant/commitment netting already
applied) and created the Revenue Cloud usage chain
UsageSummary -> UsageRatableSummary -> UsageBillingPeriodItem.

Structure chart of the set, read from these exports: `json/entrust/documents/entrust-usage-data-structure.html` (same format as the Order
Handler chart beside it).

Source for the Python port `demoscripts/billsync/` (built 20 Oct 2026, see the
main README § "Bill → Revenue Cloud usage sync"), in the same way the Order
Handler exports in Google Drive (Entrust / m3sh Workflows) are the source for
`demoscripts/ordersync/`.

| File | Workflow | Version | Role |
|---|---|---|---|
| `m3ter-sf-rca-usage-data.json` | `m3ter_sf_rca_usage_data` | 56 | Entry point. Account via External Mapping, loop over line items, child-bucket SOQL, builds the three payloads and calls the sub-workflows; writes the back-links and the bucket balance. |
| `m3ter-sf-rca-usage-data-usagesummary.json` | `m3ter_sf_rca_usage_data_usagesummary` | 20 | Sub-workflow (destination `cea4fafe-…`). Find-or-create UsageSummary on Account + Asset + StartDateTime + EndDateTime + bucket; sets `isUsageSummaryNew`; strips Status on update. |
| `m3ter-sf-rca-usage-data-ubpi.json` | `m3ter_sf_rca_usage_data_ubpi` | 12 | Sub-workflow (destination `b5a34167-…`). Create UBPI if `UsageSummary.LiableSummaryId` is null, else read and update it without Status. |
| `m3ter-sf-rca-usage-data-usageratablesummary.json` | `m3ter_sf_rca_usage_data_usageratablesummary` | 5 | Sub-workflow (destination `f3a0cccf-…`), called between the two above. Create UsageRatableSummary if `UsageSummary.RatableSummaryId` is null, else update it without Status. |

Exported 15 Oct 2026 from org `9a3a717e-40a0-4b92-9163-70db1110f21c`.
