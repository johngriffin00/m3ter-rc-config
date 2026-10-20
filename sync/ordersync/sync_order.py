"""Order activation -> m3ter sync. The parent script: wires the bricks together.

    set -a; source parameters/m3ter.env; set +a
    uv run python -m sync.ordersync.sync_order --order 00000102
    uv run python -m sync.ordersync.sync_order --from-file customers/entrust/snapshots/orders/00000102.json --dry-run
    uv run python -m sync.ordersync.sync_order --describe OrderItemRateCardEntry

Steps so far:
    1. ReadOrder       Salesforce -> ctx.snapshot (saved to customers/entrust/snapshots/orders/<OrderNumber>.json)
    2. EnsureAccount   m3ter Account for the order's Salesforce Account, + ExternalMapping
    3. EnsurePlans     a bespoke Plan per OrderItem (mapping.py says which template), + ExternalMapping
    4. EnsurePricings  a Pricing per TransactionUsageEntitlement on that plan, negotiated rate from mapping.RATE_CARD
    5. EnsureAccountPlans  an AccountPlan per order line, dates from the Asset lifecycle, + ExternalMapping

--dry-run still reads m3ter (the find-before-create checks are real) but prints
every payload instead of posting it, so run it first and read what it would do.

A Flask handler will later call run(order_ref) with the order from a webhook
payload — same bricks, different front door.
"""
import argparse

from salesforcesdk import SalesforceObject
from sync.core.step import run_steps
from sync.ordersync.context import SF_API_VERSION, SyncContext
from sync.ordersync.sf_order import ReadOrder
from sync.ordersync.step_account import EnsureAccount
from sync.ordersync.step_accountplan import EnsureAccountPlans
from sync.ordersync.step_plan import EnsurePlans
from sync.ordersync.step_pricing import EnsurePricings


def run(order_ref=None, from_file=None, sf_alias='m3ter', dry_run=False, customer=None):
    if from_file:
        ctx = SyncContext.from_snapshot(from_file, sf_alias=sf_alias, dry_run=dry_run, **({'customer': customer} if customer else {}))
        steps = []                                  # snapshot already in hand
    else:
        ctx = SyncContext(order_ref=order_ref, sf_alias=sf_alias, dry_run=dry_run, **({'customer': customer} if customer else {}))
        steps = [ReadOrder()]
    # The m3ter bricks, in m3sh order. Each one finds-or-creates, so re-runs are safe.
    steps += [
        EnsureAccount(),      # 2. Salesforce Account -> m3ter Account (+ external mapping)
        EnsurePlans(),        # 3. one bespoke Plan per OrderItem from the product's template
        EnsurePricings(),     # 4. one Pricing per TransactionUsageEntitlement from the configured rate card
        EnsureAccountPlans(), # 5. attach each plan to the account for the asset's lifecycle
    ]
    return run_steps(ctx, steps)


def describe(sobject, sf_alias='m3ter'):
    """Print the queryable field names of an sObject — for when a query is refused."""
    ctx = SyncContext(order_ref='-', sf_alias=sf_alias)
    obj = SalesforceObject(ctx.sf_auth, api_version=SF_API_VERSION)
    obj.object_name = sobject
    fields = obj.describe().get('fields', [])
    for f in fields:
        ref = f"-> {','.join(f['referenceTo'])}" if f.get('referenceTo') else ''
        print(f"{f['name']:<40} {f['type']:<12} {ref}")
    print(f'{len(fields)} fields on {sobject}')


def inspect_m3ter():
    """Read-only tour of the target m3ter org: the catalog the sync will attach to.

    Object graph, for orientation:
        Product -> Meter (optional: a meter with no product is global)
                -> Aggregation (via meterId) -> priced by Pricing on a PlanTemplate or Plan
        Product -> PlanTemplate -> Plan (optionally bound to one Account via accountId)
        Account -> AccountPlan -> Plan
    """
    from m3sdk import Account, Aggregation, ExternalMapping, Meter, Plan, PlanTemplate, Pricing, Product
    g = getattr
    ctx = SyncContext(order_ref='-')
    m3 = ctx.m3
    products = {p.id: p for p in Product.list(m3)}

    def pcode(pid):
        return products[pid].code if pid in products else (pid or 'global')

    print('\nProducts')
    for p in products.values():
        print(f'  {p.code:<40} {p.name:<40} {p.id}')

    meters = {m.id: m for m in Meter.list(m3)}
    print('\nMeters')
    for m in meters.values():
        print(f'  {m.code:<40} {m.name:<40} product={pcode(g(m, "productId", None))}')

    aggs = {a.id: a for a in Aggregation.list(m3)}
    print('\nAggregations')
    for a in aggs.values():
        meter = meters.get(g(a, 'meterId', None))
        print(f'  {a.code:<40} {a.name:<40} meter={meter.code if meter else g(a, "meterId", None)} '
              f'product={pcode(g(meter, "productId", None)) if meter else "?"} segments={g(a, "segments", None)}')

    templates = {t.id: t for t in PlanTemplate.list(m3)}
    print('\nPlan templates')
    for t in templates.values():
        print(f'  {t.code:<40} {t.name:<40} {g(t, "currency", "?")} product={pcode(g(t, "productId", None))}')

    plans = {p.id: p for p in Plan.list(m3)}
    print('\nPlans')
    for p in plans.values():
        tmpl = templates.get(g(p, 'planTemplateId', None))
        print(f'  {p.code:<40} {p.name:<40} template={tmpl.code if tmpl else g(p, "planTemplateId", None)} '
              f'accountId={g(p, "accountId", None)}')

    print('\nPricings')
    for x in Pricing.list(m3):
        plan = plans.get(g(x, 'planId', None))
        tmpl = templates.get(g(x, 'planTemplateId', None))
        agg = aggs.get(g(x, 'aggregationId', None))
        print(f'  {"plan=" + plan.code if plan else "template=" + (tmpl.code if tmpl else "?"):<50} '
              f'agg={agg.code if agg else g(x, "aggregationId", None):<40} segment={g(x, "segment", None)} '
              f'bands={g(x, "pricingBands", None)} {g(x, "startDate", "")}')

    print('\nAccounts')
    for a in Account.list(m3):
        print(f'  {a.code:<40} {a.name:<40} {a.id}')

    print('\nExternal mappings')
    for e in ExternalMapping.list(m3):
        print(f'  {e.externalSystem}/{e.externalTable}/{e.externalId} -> {e.m3terEntity} {e.m3terId}')


def main(argv=None):
    p = argparse.ArgumentParser(description='Sync an activated Revenue Cloud order to m3ter')
    p.add_argument('--order', help='OrderNumber (00000102) or Order Id')
    p.add_argument('--from-file', help='replay a saved snapshot instead of querying Salesforce')
    p.add_argument('--customer', help='customers/<name>/ whose mapping.py and snapshots to use (default entrust)')
    p.add_argument('--sf-org', default='m3ter', help='sf CLI org alias (default m3ter)')
    p.add_argument('--dry-run', action='store_true', help='print m3ter payloads, create nothing')
    p.add_argument('--describe', metavar='SOBJECT', help='list the fields of an sObject and exit')
    p.add_argument('--inspect', action='store_true', help='list the m3ter org catalog (read-only) and exit')
    args = p.parse_args(argv)

    if args.inspect:
        return inspect_m3ter()
    if args.describe:
        return describe(args.describe, args.sf_org)
    if not (args.order or args.from_file):
        p.error('give --order or --from-file')
    run(order_ref=args.order, from_file=args.from_file, sf_alias=args.sf_org, dry_run=args.dry_run, customer=args.customer)


if __name__ == '__main__':
    main()
