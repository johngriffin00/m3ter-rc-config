"""Step 6 — close the loop: point the UsageSummary at its ratable summary
and billing period item, then record the usage on the bucket.

The tail of the m3sh parent workflow, after the three sub-workflows:

    If isUsageSummaryNew
      -> Update UsageSummary {RatableSummaryId, LiableSummaryId}
    Get Bucket -> Set {BucketBalance, ConsumedEntitlement} -> Update UEM Bucket

Two deliberate differences from the workflow:
  * The links are written whenever they are missing or different, not only
    when the UsageSummary was new. In m3sh a run that died after creating the
    summary left it unlinked for ever (and every later run created a fresh
    ratable summary and UBPI it never linked either). Here the next run links
    them, and the one after that finds them through the links and updates.
  * Nothing is read back first: the bucket update is a PATCH of two fields.

The bucket fields, as m3sh set them (BUCKET_FIELDS below):
    BucketBalance        lineItem.TotalUsedQuantity   (the billed quantity)
    ConsumedEntitlement  lineItem.ConsumptionUnits    (the same number when
                                                      there is no overage)
Writing the USED quantity into a field called BucketBalance looks wrong for
an entitlement with a grant (the balance should fall as usage is consumed);
Entrust never had grants, so it never mattered. Revisit with the first
granted entitlement — it is one dict here.
"""
from sync.core.sf_step import SalesforceStep

BUCKET_FIELDS = {'BucketBalance': 'TotalUsedQuantity', 'ConsumedEntitlement': 'ConsumptionUnits'}


class LinkUsageSummary(SalesforceStep):
    name = 'link'
    sobject = 'UsageSummary'

    def run(self, ctx):
        for line in ctx.state['lines']:
            key = line['lineItemId']
            summary = ctx.state['usage_summaries'][key]
            links = {'RatableSummaryId': ctx.state['ratable_summaries'][key]['id'],
                     'LiableSummaryId': ctx.state['billing_period_items'][key]['id']}
            if all(summary.get(k) == v for k, v in links.items()):
                self.say(ctx, f"{line['resource']:<28} UsageSummary {summary['id']} already linked")
                continue
            if ctx.dry_run:
                self.say(ctx, f"{line['resource']:<28} DRY RUN would link UsageSummary {summary['id']}: {links}")
            else:
                self.sf(ctx).update(summary['id'], links)
                self.say(ctx, f"{line['resource']:<28} linked UsageSummary {summary['id']} -> {links}")
            summary.update(links)


class UpdateBucket(SalesforceStep):
    name = 'bucket'
    sobject = 'UsageEntitlementBucket'

    def run(self, ctx):
        for line in ctx.state['lines']:
            payload = {field: line[source] for field, source in BUCKET_FIELDS.items()}
            if ctx.dry_run:
                self.say(ctx, f"{line['resource']:<28} DRY RUN would update bucket {line['bucketName']} ({line['bucketId']}): {payload}")
            else:
                self.sf(ctx).update(line['bucketId'], payload)
                self.say(ctx, f"{line['resource']:<28} updated bucket {line['bucketName']}: {payload}")
