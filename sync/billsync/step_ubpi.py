"""Step 5 — a UsageBillingPeriodItem per line: the BILLABLE view — what was
used in the billing period, in what currency, and the overage charge.

Port of the m3sh sub-workflow m3ter_sf_rca_usage_data_ubpi, keyed like the
ratable summary but on the other back-link:

    sfUsageSummary.LiableSummaryId == null  -> create (Status 'New')
    else                                    -> read it, update it, Status stripped

Payload, from the parent's "Set Fields for UsageBillingPeriodItem":
    AssetId, AccountId, UsageEntitlementBucketId, UoMId     resolved in step 2
    StartDateTime / EndDateTime                             see END_INCLUSIVE
    CurrencyIsoCode        the bill's currency (handlerRC hardcoded USD)
    TotalUsedQuantity      the billed quantity
    OverageQuantity, OverageAmount                          the overage (0 for Entrust)
    Status 'New' on create only
"""
from sync.core.sf_step import SalesforceStep, inclusive_end, sf_datetime

# m3sh passed the UBPI's EndDateTime raw (midnight exclusive, 2026-11-01T00:00:00Z)
# while the other two records got the -1 s treatment. True makes all three agree
# on 23:59:59; False is the faithful port.
END_INCLUSIVE = True


class EnsureUsageBillingPeriodItem(SalesforceStep):
    name = 'billing period item'
    sobject = 'UsageBillingPeriodItem'

    def run(self, ctx):
        ctx.state['billing_period_items'] = {}
        for line in ctx.state['lines']:
            summary = ctx.state['usage_summaries'][line['lineItemId']]
            existing = None if summary['is_new'] else summary.get('LiableSummaryId')
            record_id, is_new = self.create_or_update(ctx, line['resource'], existing, self.build_payload(line))
            ctx.state['billing_period_items'][line['lineItemId']] = {'id': record_id, 'is_new': is_new}
        return ctx.state['billing_period_items']

    @staticmethod
    def build_payload(line) -> dict:
        end = inclusive_end if END_INCLUSIVE else sf_datetime
        return {
            'AccountId': line['sfAccountId'],
            'AssetId': line['assetId'],
            'GrantBindingTargetId': line['grantBindingTargetId'],
            'UsageEntitlementBucketId': line['bucketId'],
            'UoMId': line['uomId'],
            'StartDateTime': sf_datetime(line['StartDateTime']),
            'EndDateTime': end(line['EndDateTime']),
            'CurrencyIsoCode': line['CurrencyIsoCode'],
            'TotalUsedQuantity': line['TotalUsedQuantity'],
            'OverageQuantity': line['OverageQuantity'],
            'OverageAmount': line['OverageAmount'],
            'Status': 'New',
        }
