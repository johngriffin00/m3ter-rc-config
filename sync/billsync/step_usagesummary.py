"""Step 3 — a UsageSummary per bill line: "this asset used N units of this
bucket between these dates".

The first of the three Revenue Cloud usage records and the one the other two
hang off (UsageRatableSummary via RatableSummaryId, UsageBillingPeriodItem via
LiableSummaryId — both written back by a later brick). Port of the m3sh
sub-workflow m3ter_sf_rca_usage_data_usagesummary:

    SOQL UsageSummary WHERE AccountId, AssetId, StartDateTime, EndDateTime,
                            UsageEntitlementBucketId        (the natural key)
    none  -> create with Status 'New'; isUsageSummaryNew = true
    found -> remove Status ("we don't want to reset it to New"), update

Payload, field by field, from the parent's "Set Multiple Fields on UsageSummary":
    AssetId, AccountId, UsageEntitlementBucketId, UomId   resolved in step 2
    StartDateTime      the line's service period start
    EndDateTime        service period end - 1 second (inclusive)
    DebitedUnits       what m3sh called lineItem.ConsumptionUnits = the billed quantity
    ConsumptionUnits   ConsumptionUnits + OverageUnits    (= quantity when there is no overage)
    OverageUnits       the overage quantity
    Status             'New' on create only
"""
from sync.core.sf_step import SalesforceStep, inclusive_end, sf_datetime


class EnsureUsageSummary(SalesforceStep):
    name = 'usage summary'
    sobject = 'UsageSummary'

    def run(self, ctx):
        ctx.state['usage_summaries'] = {}
        for line in ctx.state['lines']:
            payload = self.build_payload(line)
            where = (f"AccountId = '{payload['AccountId']}' AND AssetId = '{payload['AssetId']}' "
                     f"AND StartDateTime = {payload['StartDateTime']} AND EndDateTime = {payload['EndDateTime']} "
                     f"AND UsageEntitlementBucketId = '{payload['UsageEntitlementBucketId']}'")
            record_id, is_new, found = self.find_or_create(ctx, line['resource'], where, payload,
                                                           select=('Id', 'RatableSummaryId', 'LiableSummaryId'))
            # The back-links are what the next two bricks key on (m3sh's
            # sfUsageSummary.RatableSummaryId / LiableSummaryId == null checks),
            # read fresh for THIS line — the workflow reused the previous line's.
            ctx.state['usage_summaries'][line['lineItemId']] = {
                'id': record_id, 'is_new': is_new,
                'RatableSummaryId': found.get('RatableSummaryId'),
                'LiableSummaryId': found.get('LiableSummaryId'),
            }
        return ctx.state['usage_summaries']

    @staticmethod
    def build_payload(line) -> dict:
        return {
            'AccountId': line['sfAccountId'],
            'AssetId': line['assetId'],
            'GrantBindingTargetId': line['grantBindingTargetId'],
            'UsageEntitlementBucketId': line['bucketId'],
            'UomId': line['uomId'],
            'StartDateTime': sf_datetime(line['StartDateTime']),
            'EndDateTime': inclusive_end(line['EndDateTime']),
            'DebitedUnits': line['ConsumptionUnits'],
            'ConsumptionUnits': line['ConsumptionUnits'] + line['OverageUnits'],
            'OverageUnits': line['OverageUnits'],
            'Status': 'New',
        }
