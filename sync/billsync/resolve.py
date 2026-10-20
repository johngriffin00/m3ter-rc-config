"""Step 2 — find everything the Salesforce writes will need, and net the lines.

The m3sh parent workflow did this inside its loop, one SOQL at a time:
ExternalMapping for the account, GetM3terEntity for the AccountPlan (whose
custom fields carried the TUE and UoM ids), a SOQL for the bucket. The old
handlerRC.py did the netting before it posted. This brick does all of it up
front, from the frozen snapshot, and writes one resolved entry per USAGE line
to ctx.state['lines'] so the three ensure-bricks that follow (UsageSummary,
UsageRatableSummary, UsageBillingPeriodItem) only build payloads and post.

How a bill line finds its way back to Revenue Cloud:

  bill.accountId  --ExternalMapping Salesforce/Account-->  Salesforce Account Id
                    (the order sync wrote it; the account code is the same Id)
  line.pricingId  --ExternalMapping Salesforce/TransactionUsageEntitlement-->  TUE Id
                    (one Pricing per TUE, so this is exact; the Pricing code
                    pricing_<TUE Id> is the fallback and the cross-check)
  TUE             --SOQL-->  AssetId, AccountId, EntitlementUomId, GrantBindingTargetId
                    (the grant binding target — Account, Asset, Contract or a
                    custom binding object; for a "Self" binding it is the
                    Asset. UsageRatableSummary REQUIRES it, a field newer
                    than the m3sh workflows; AssetId is the fallback.)
  UsageEntitlementBucket under the TUE  --SOQL-->  the bucket the usage
                    objects attach to. m3sh wanted the CHILD bucket
                    (Parent.Type = 'UsageEntitlementBucket', the period
                    bucket Revenue Cloud makes for recurring entitlements);
                    a non-recurring entitlement only has the top-level bucket
                    (Parent.Type = 'UsageEntitlementAccount'), so we take the
                    child bucket covering the line's service period when
                    there is one and fall back to the top-level bucket.

Netting, as handlerRC.py did it (keyed per plan + pricing):
  USAGE_CREDIT on the same plan     = the grant  -> DebitedUnits = quantity - grant
  OVERAGE_USAGE on the same pricing = m3ter's own overage line (never seen)
Entrust never produced either line type (0 of ~126k lines in the Postgres
copy), so these are always zero; the code stays because the port is faithful.

What Revenue Cloud Billing invoices (found 20 Oct 2026): the UBPI's ONLY money
field is OverageAmount, and the invoice line takes Quantity from
TotalUsedQuantity and LineAmount from OverageAmount. "Overage" there means
"billable beyond the entitlement" — usage inside a prepaid grant or balance is
already paid for. So the m3sh/handlerRC value (m3ter's OVERAGE_USAGE line,
always absent) produced zero-value invoices. The rule here, see overage():
  no balance on the bill       pay as you go: everything used is overage —
                               OverageQuantity = DebitedUnits, OverageAmount =
                               the line's subtotal (what m3ter charged)
  balance covers the bill      nothing is billable: both zero
  balance runs out mid-bill    the drawdown is a bill-level BALANCE_CONSUMED
                               line, not per resource, so the split across
                               lines needs a rule we have not agreed — stop.

Every Salesforce field name here is one the order sync already queried, or one
the m3sh "Query for UEB" used in production (BucketBalanceUoMId, Parent.Type).
"""
from datetime import UTC, datetime

from m3sdk import ExternalMapping, Pricing

from salesforcesdk import SalesforceObject
from sync.core.context import SF_API_VERSION
from sync.core.soql import clean, in_list
from sync.core.step import Step
from sync.ordersync.step_account import EXTERNAL_SYSTEM

CHILD_BUCKET = 'UsageEntitlementBucket'      # Parent.Type of a period bucket
TOP_BUCKET = 'UsageEntitlementAccount'       # Parent.Type of the entitlement's own bucket


def _dt(value):
    """Either platform's date-time string -> aware datetime; None stays None (open-ended)."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00').replace('+0000', '+00:00')).astimezone(UTC)


def _overlaps(bucket, start, end):
    b_start, b_end = _dt(bucket.get('EffectiveStartDateTime')), _dt(bucket.get('EffectiveEndDateTime'))
    return (b_start is None or b_start < end) and (b_end is None or b_end > start)


class Resolve(Step):
    name = 'resolve'

    def soql(self, ctx, soql):
        sf = SalesforceObject(ctx.sf_auth, api_version=SF_API_VERSION)
        return [clean(r) for r in sf.query_all(soql)]

    def run(self, ctx):
        snap = ctx.snapshot
        bill = snap['bill']
        lines = snap['line_items']

        # 1. The Salesforce Account — m3sh's first function; no mapping, no sync.
        mappings = [m for m in ExternalMapping.find_by_m3ter(ctx.m3, 'Account', bill['accountId'])
                    if m.externalSystem == EXTERNAL_SYSTEM and m.externalTable == 'Account']
        if not mappings:
            raise RuntimeError(f"m3ter account {bill['accountId']} ({bill['accountCode']}) has no "
                               f"{EXTERNAL_SYSTEM}/Account external mapping — was the order synced?")
        sf_account_id = mappings[0].externalId
        if sf_account_id != bill['accountCode']:
            self.say(ctx, f"WARNING account code {bill['accountCode']} != mapped Salesforce Account {sf_account_id}")
        ctx.state['sf_account_id'] = sf_account_id
        self.say(ctx, f"m3ter account {bill['accountCode']} -> Salesforce Account {sf_account_id}")

        # 2. Index the netting lines (handlerRC.py's overages/grants dicts).
        overages = {(li['planId'], li['pricingId']): li for li in lines if li['lineItemType'] == 'OVERAGE_USAGE'}
        grants = {li['planId']: li for li in lines if li['lineItemType'] == 'USAGE_CREDIT'}
        usage = [li for li in lines if li['lineItemType'] == 'USAGE' and (li.get('quantity') or 0) > 0]
        self.say(ctx, f'{len(usage)} USAGE line(s) to sync, {len(grants)} grant(s), {len(overages)} overage(s)')
        billable = self.overage(ctx, usage, lines)

        # 3. Pricing -> TUE, via the mapping the order sync wrote (code as fallback).
        tue_for_pricing = {}
        for li in usage:
            pid = li['pricingId']
            if pid in tue_for_pricing:
                continue
            found = [m for m in ExternalMapping.find_by_m3ter(ctx.m3, 'Pricing', pid)
                     if m.externalSystem == EXTERNAL_SYSTEM and m.externalTable == 'TransactionUsageEntitlement']
            if found:
                tue_for_pricing[pid] = found[0].externalId
                continue
            code = getattr(Pricing.get(ctx.m3, pid), 'code', '') or ''
            if code.startswith('pricing_'):
                tue_for_pricing[pid] = code[len('pricing_'):]
                self.say(ctx, f'WARNING pricing {pid} has no external mapping; using its code {code}')
            else:
                raise RuntimeError(f"pricing {pid} ({li.get('description')}) maps to no TransactionUsageEntitlement")

        # 4. The TUEs and their buckets, one SOQL each.
        tue_ids = sorted(set(tue_for_pricing.values()))
        tues = {t['Id']: t for t in self.soql(ctx, f"""
            SELECT Id, AssetId, AccountId, EntitlementUomId, GrantBindingTargetId, UsageResource.Code,
                   EffectiveStartDateTime, EffectiveEndDateTime
            FROM TransactionUsageEntitlement WHERE Id IN ({in_list(tue_ids)})""")}
        missing = [t for t in tue_ids if t not in tues]
        if missing:
            raise RuntimeError(f'TransactionUsageEntitlement(s) not found in Salesforce: {missing}')
        buckets = self.soql(ctx, f"""
            SELECT Id, Name, TransactionUsageEntitlementId, ParentId, Parent.Type, BucketBalanceUoMId,
                   BucketBalance, EffectiveStartDateTime, EffectiveEndDateTime
            FROM UsageEntitlementBucket WHERE TransactionUsageEntitlementId IN ({in_list(tue_ids)})
            ORDER BY EffectiveStartDateTime""")
        by_tue = {}
        for b in buckets:
            by_tue.setdefault(b['TransactionUsageEntitlementId'], []).append(b)
        for t in tues.values():
            if t['AccountId'] != sf_account_id:
                self.say(ctx, f"WARNING TUE {t['Id']} belongs to Account {t['AccountId']}, not {sf_account_id}")

        # 5. One resolved entry per USAGE line — the fields the m3sh payload carried,
        #    plus the Salesforce ids the sub-workflows looked up.
        ctx.state['lines'] = []
        for li in usage:
            tue = tues[tue_for_pricing[li['pricingId']]]
            bucket, level = self.pick_bucket(by_tue.get(tue['Id'], []), tue, li)
            if bucket is None:
                raise RuntimeError(f"no UsageEntitlementBucket under TUE {tue['Id']} ({tue['UsageResource']['Code']})")
            overage = overages.get((li['planId'], li['pricingId']), {})
            grant = grants.get(li['planId'], {})
            qty = li.get('quantity') or 0
            grant_qty = grant.get('quantity') or 0
            rate = li.get('averageUnitPrice') or 0
            debited = max(qty - grant_qty, 0)
            overage_qty, overage_amount = (debited, li.get('subtotal') or 0) if billable else (0, 0)
            if overage.get('quantity'):
                self.say(ctx, f"WARNING m3ter has an OVERAGE_USAGE line for {li.get('description')} "
                              f"({overage['quantity']}); not used — see overage()")
            entry = {
                # where it came from
                'lineItemId': li['id'], 'description': li.get('description', ''),
                'planId': li['planId'], 'pricingId': li['pricingId'], 'subtotal': li.get('subtotal'),
                # where it goes
                'sfAccountId': sf_account_id, 'tueId': tue['Id'], 'resource': tue['UsageResource']['Code'],
                'assetId': tue['AssetId'], 'uomId': tue['EntitlementUomId'],
                'grantBindingTargetId': tue.get('GrantBindingTargetId') or tue['AssetId'],
                'bucketId': bucket['Id'], 'bucketName': bucket.get('Name'), 'bucketLevel': level,
                # the m3sh payload fields (handlerRC.build_salesforce_payload), netted
                'StartDateTime': li['servicePeriodStartDate'],
                'EndDateTime': li['servicePeriodEndDate'],
                'RatingDecisionDateTime': li['servicePeriodEndDate'],
                'Unit': li.get('unit', ''),
                'ConsumptionUnits': qty,
                'DebitedUnits': debited,
                'OverageUnits': overage_qty,
                'OverageQuantity': overage_qty,
                'TierQuantity': overage_qty,
                'NetUnitRate': rate,
                'TotalAmount': overage_amount,
                'OverageAmount': overage_amount,
                'TotalUsedQuantity': qty,
                'CurrencyIsoCode': bill.get('currency') or li.get('currency'),   # handlerRC hardcoded USD
            }
            ctx.state['lines'].append(entry)
            if not tue.get('GrantBindingTargetId'):
                self.say(ctx, f"WARNING TUE {tue['Id']} has no GrantBindingTargetId; using its Asset")
            self.say(ctx, f"{entry['resource']:<28} qty {qty:>8} @ {rate:<6} -> TUE {tue['Id']} asset {tue['AssetId']} "
                          f"bucket {bucket.get('Name')} ({level}) {(bucket.get('EffectiveStartDateTime') or '')[:10]}..{(bucket.get('EffectiveEndDateTime') or 'open')[:10]}")
        return ctx.state['lines']

    def overage(self, ctx, usage, lines) -> bool:
        """Is this bill's usage billable by Revenue Cloud (True: all of it is
        overage) or covered by a prepaid balance (False: none of it is)?

        m3ter shows a balance drawdown as BALANCE_CONSUMED lines with a negative
        subtotal. usage + drawdown <= 0 means the balance absorbed everything.
        A positive remainder means the balance ran out part way through the
        bill: Revenue Cloud needs that remainder split across the resource
        lines and we have not agreed how, so stop rather than invoice a guess.
        """
        drawdown = sum(li.get('subtotal') or 0 for li in lines if li['lineItemType'] == 'BALANCE_CONSUMED')
        charged = sum(li.get('subtotal') or 0 for li in usage)
        if not drawdown:
            self.say(ctx, f'no balance on this bill: pay as you go, all {charged} is overage')
            return True
        remainder = charged + drawdown
        if remainder <= 0:
            self.say(ctx, f'balance covers the bill (usage {charged}, drawdown {drawdown}): nothing is overage')
            return False
        raise RuntimeError(f'balance ran out mid-bill: usage {charged}, drawdown {drawdown}, {remainder} left to '
                           f'invoice — the split across lines is not implemented yet (see Resolve.overage)')

    @staticmethod
    def pick_bucket(candidates, tue, line):
        """The child (period) bucket covering the line's service period, matching the
        entitlement's UoM — m3sh's query — else the entitlement's top-level bucket."""
        start, end = _dt(line['servicePeriodStartDate']), _dt(line['servicePeriodEndDate'])
        uom = tue['EntitlementUomId']
        children = [b for b in candidates
                    if (b.get('Parent') or {}).get('Type') == CHILD_BUCKET
                    and (b.get('BucketBalanceUoMId') in (None, uom))
                    and _overlaps(b, start, end)]
        if children:
            return children[0], 'child'
        tops = [b for b in candidates if (b.get('Parent') or {}).get('Type') == TOP_BUCKET]
        if tops:
            return tops[0], 'top'
        return (candidates[0], 'only') if candidates else (None, None)
