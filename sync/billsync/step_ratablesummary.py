"""Step 4 — a UsageRatableSummary per line: the RATED view of the same usage —
the net unit rate it was charged at, the tiers/overage, and the amount.

Port of the m3sh sub-workflow m3ter_sf_rca_usage_data_usageratablesummary.
It does not search by natural key; it asks the UsageSummary:

    sfUsageSummary.RatableSummaryId == null  -> create (Status 'New')
    else                                     -> update that record, Status stripped

Here the id comes from ctx.state['usage_summaries'] (brick 3 read it for
this line), so a new UsageSummary, or an old one whose link was never
written, both lead to a create — and brick 6 writes the link in either case.

Payload, from the parent's "Set Multiple Fields on UsageRatableSummary":
    AssetId, AccountId, UsageEntitlementBucketId          resolved in step 2
    GrantBindingTargetId   REQUIRED here ("Select a Grant Binding Target..."):
                           the TUE's binding target, the Asset for a Self binding
    StartDateTime / EndDateTime (-1 s) / RatingDecisionDateTime (-1 s)
    NetUnitRate            the line's averageUnitPrice
    NetUnitRateUomId, OverageQuantityUomId, TierQuantityUomId   the entitlement UoM
    OverageQuantity, TierQuantity                          the overage (0 for Entrust)
    TotalAmount            see TOTAL_AMOUNT below
    Status 'New' on create only
"""
from sync.core.sf_step import SalesforceStep, inclusive_end, sf_datetime

# handlerRC.py sent overage_qty * rate here, which is 0 for every Entrust line.
# 'subtotal' is what the line actually charged. Flip to 'OverageAmount' for the
# faithful port.
TOTAL_AMOUNT = 'subtotal'


class EnsureUsageRatableSummary(SalesforceStep):
    name = 'ratable summary'
    sobject = 'UsageRatableSummary'

    def run(self, ctx):
        ctx.state['ratable_summaries'] = {}
        for line in ctx.state['lines']:
            summary = ctx.state['usage_summaries'][line['lineItemId']]
            existing = None if summary['is_new'] else summary.get('RatableSummaryId')
            record_id, is_new = self.create_or_update(ctx, line['resource'], existing, self.build_payload(line))
            ctx.state['ratable_summaries'][line['lineItemId']] = {'id': record_id, 'is_new': is_new}
        return ctx.state['ratable_summaries']

    @staticmethod
    def build_payload(line) -> dict:
        return {
            'AccountId': line['sfAccountId'],
            'AssetId': line['assetId'],
            'GrantBindingTargetId': line['grantBindingTargetId'],
            'UsageEntitlementBucketId': line['bucketId'],
            'StartDateTime': sf_datetime(line['StartDateTime']),
            'EndDateTime': inclusive_end(line['EndDateTime']),
            'RatingDecisionDateTime': inclusive_end(line['RatingDecisionDateTime']),
            'NetUnitRate': line['NetUnitRate'],
            'NetUnitRateUomId': line['uomId'],
            'OverageQuantity': line['OverageQuantity'],
            'OverageQuantityUomId': line['uomId'],
            'TierQuantity': line['TierQuantity'],
            'TierQuantityUomId': line['uomId'],
            'TotalAmount': line[TOTAL_AMOUNT],
            'Status': 'New',
        }
