"""Step 5 — attach the plan to the account for the life of the asset.

The m3sh "Order Step: AccountPlan creation", with one difference: m3sh makes an
AccountPlan per TUE (per resource) against a shared plan; here the plan is
already per order line, so there is one AccountPlan per order line, and the
per-resource detail lives in the Pricings (step 4).

Dates come from the Asset, Revenue Cloud's record of what was sold and for how
long:
    LifecycleStartDate 2026-10-14T00:00:00Z      -> startDate 2026-10-14T00:00:00.000Z
    LifecycleEndDate   2026-11-13T23:59:59Z      -> endDate   2026-11-14T00:00:00.000Z
Salesforce ends on the last second of the last day (inclusive); m3ter ends at
the first instant NOT covered (exclusive), hence the one-second shift.

m3ter's rule: one active AccountPlan per Product per Account, unless the org
setting "Allow overlapping attached plans" is on. A renewal must therefore
start after this one ends, or the API refuses the attach — which is the right
failure.

Key: ExternalMapping Salesforce/Asset/<Asset Id> -> AccountPlan. The asset is
the Revenue Cloud object that owns the lifecycle, so it is the natural twin.
"""
from m3sdk import AccountPlan, ExternalMapping

from sync.core.dates import exclusive_end, to_m3ter
from sync.core.step import Step

from .step_account import EXTERNAL_SYSTEM


class EnsureAccountPlans(Step):
    name = 'account plan'

    def run(self, ctx):
        snap = ctx.snapshot
        account = ctx.state['account']
        assets = {a['Id']: a for a in snap['assets']}
        ctx.state['account_plans'] = {}

        for item in snap['order_items']:
            # The asset for this line: via its entitlements (TUE.AssetId).
            asset_ids = {t['AssetId'] for t in snap['usage_entitlements'] if t['OrderItemId'] == item['Id']}
            if len(asset_ids) != 1:
                raise RuntimeError(f"order item {item['Id']}: expected one asset, found {sorted(asset_ids)}")
            asset = assets[asset_ids.pop()]
            plan = ctx.state['plans'][item['Id']]

            # 1. Look before you create.
            mappings = ExternalMapping.find(ctx.m3, EXTERNAL_SYSTEM, 'Asset', asset['Id'])
            if mappings:
                account_plan = AccountPlan.get(ctx.m3, mappings[0].m3terId)
                self.say(ctx, f'found via external mapping ({account_plan.id}) '
                              f'{account_plan.startDate} -> {getattr(account_plan, "endDate", None)}')
                ctx.state['account_plans'][item['Id']] = account_plan
                continue

            account_plan = self.create_or_pretend(ctx, AccountPlan, **self.build_payload(ctx, item, asset, plan, account))
            self.create_or_pretend(ctx, ExternalMapping,
                                   externalSystem=EXTERNAL_SYSTEM, externalTable='Asset', externalId=asset['Id'],
                                   m3terEntity='AccountPlan', m3terId=account_plan.id)
            ctx.state['account_plans'][item['Id']] = account_plan
        return ctx.state['account_plans']

    @staticmethod
    def build_payload(ctx, item, asset, plan, account) -> dict:
        order = ctx.snapshot['order']
        payload = {
            'accountId': account.id,
            'planId': plan.id,
            'startDate': to_m3ter(asset['LifecycleStartDate']),
            'code': f"accountplan_{asset['Id']}",
            'customFields': {
                'sfAssetId': asset['Id'],
                'sfOrderItemId': item['Id'],
                'sfOrderNumber': order['OrderNumber'],
            },
        }
        if asset.get('LifecycleEndDate'):
            payload['endDate'] = exclusive_end(asset['LifecycleEndDate'])
        return payload
