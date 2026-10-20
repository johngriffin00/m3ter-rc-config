"""Both syncs replayed end to end from the saved Entrust snapshots, offline.

The rule in CLAUDE.md: live runs are John's terminal; Claude proves bricks against
the snapshots with stubbed clients. These tests are that proof for the move into
this repo — every step runs in --dry-run with a fake m3ter client (order sync) or a
fake Salesforce client (bill sync) that answers the reads the bricks make and
refuses every write. If a brick ever posts on a dry run, or reads something the
fakes don't know, the test fails.
"""
import json
import re
from pathlib import Path

import pytest

from sync.billsync.context import BillSyncContext
from sync.billsync.resolve import Resolve
from sync.billsync.step_link import LinkUsageSummary, UpdateBucket
from sync.billsync.step_ratablesummary import EnsureUsageRatableSummary
from sync.billsync.step_ubpi import EnsureUsageBillingPeriodItem
from sync.billsync.step_usagesummary import EnsureUsageSummary
from sync.core.customer import load_mapping
from sync.core.step import run_steps
from sync.ordersync.context import SyncContext
from sync.ordersync.step_account import EnsureAccount
from sync.ordersync.step_accountplan import EnsureAccountPlans
from sync.ordersync.step_plan import EnsurePlans
from sync.ordersync.step_pricing import EnsurePricings

SNAPSHOTS = Path(__file__).resolve().parent.parent / 'customers' / 'entrust' / 'snapshots'
ORDER = SNAPSHOTS / 'orders' / '00000102.json'
BILL = next((SNAPSHOTS / 'bills').glob('*.json'))
mapping = load_mapping('entrust')


class NoWrites:
    """Any write on a dry run is a bug."""

    def post(self, path, json=None, **kw):
        raise AssertionError(f'dry run tried to POST {path}: {json}')

    def put(self, path, json=None, **kw):
        raise AssertionError(f'dry run tried to PUT {path}: {json}')

    def delete(self, path):
        raise AssertionError(f'dry run tried to DELETE {path}')


class FakeM3ForOrder(NoWrites):
    """An m3ter org with the catalog the order sync attaches to and nothing of Acme yet."""

    def get(self, path):
        if path.startswith('/externalmappings/externalid/'):
            return {'data': []}                                   # nothing synced yet
        if path == '/accounts' or path == '/plans':
            return {'data': []}
        if path == '/plantemplates':
            return {'data': [{'id': 'tmpl-usd', 'code': 'usd_default_pricing', 'name': 'USD default pricing'}]}
        if path == '/aggregations':
            return {'data': [{'id': f'agg-{code}', 'code': code, 'name': code} for code in mapping.AGGREGATION_BY_FEATURE.values()]}
        raise AssertionError(f'unexpected m3ter read on a dry run: GET {path}')


def test_order_sync_replays_offline(capsys):
    ctx = SyncContext.from_snapshot(ORDER, dry_run=True)
    ctx._m3 = FakeM3ForOrder()                                  # never authenticate
    run_steps(ctx, [EnsureAccount(), EnsurePlans(), EnsurePricings(), EnsureAccountPlans()])

    snap = ctx.snapshot
    assert ctx.state['account'].code == snap['account']['Id']
    assert list(ctx.state['plans']) == [snap['order_items'][0]['Id']]
    assert len(ctx.state['pricings']) == 6 == len(snap['usage_entitlements'])
    assert len(ctx.state['account_plans']) == 1

    # The negotiated List-card rate reaches each pricing's one flat band.
    rates = {(r['OrderItemId'], r['RateCardEntry']['UsageResource']['Code']): r['NegotiatedRate']
             for r in snap['order_item_rates'] if r['RateCardEntry']['RateCard']['Name'] == mapping.RATE_CARD}
    for tue in snap['usage_entitlements']:
        pricing = ctx.state['pricings'][tue['Id']]
        assert pricing.pricingBands[0]['unitPrice'] == rates[(tue['OrderItemId'], tue['UsageResource']['Code'])]

    out = capsys.readouterr().out
    assert out.count('DRY RUN would create Account:') == 1
    assert out.count('DRY RUN would create Plan:') == 1
    assert out.count('DRY RUN would create Pricing:') == 6
    assert out.count('DRY RUN would create AccountPlan:') == 1


# ---- bill sync ---------------------------------------------------------------

def _order_snapshot():
    return json.loads(ORDER.read_text())


class FakeM3ForBill(NoWrites):
    """Acme after the order sync: the account mapping and one pricing per TUE exist."""

    def __init__(self, bill, order):
        self.bill = bill
        # pricing id -> TUE id, matched through the resource name in the line description
        by_name = {t['UsageResource']['Name']: t['Id'] for t in order['usage_entitlements']}
        self.tue_for_pricing = {}
        for li in bill['line_items']:
            if li['lineItemType'] != 'USAGE':
                continue
            name = next(n for n in by_name if n in li['description'])
            self.tue_for_pricing[li['pricingId']] = by_name[name]

    def get(self, path):
        m = re.fullmatch(r'/externalmappings/external/Account/(.+)', path)
        if m and m.group(1) == self.bill['bill']['accountId']:
            return {'data': [{'id': 'map-acct', 'externalSystem': 'Salesforce', 'externalTable': 'Account',
                              'externalId': self.bill['bill']['accountCode'], 'm3terEntity': 'Account',
                              'm3terId': m.group(1)}]}
        m = re.fullmatch(r'/externalmappings/external/Pricing/(.+)', path)
        if m and m.group(1) in self.tue_for_pricing:
            return {'data': [{'id': f'map-{m.group(1)}', 'externalSystem': 'Salesforce',
                              'externalTable': 'TransactionUsageEntitlement',
                              'externalId': self.tue_for_pricing[m.group(1)], 'm3terEntity': 'Pricing',
                              'm3terId': m.group(1)}]}
        raise AssertionError(f'unexpected m3ter read on a dry run: GET {path}')


class FakeSalesforce:
    """Answers the SOQL the bill bricks run, from the order snapshot; refuses writes."""
    order = None
    queries: list = []

    def __init__(self, auth, api_version=None):
        self.object_name = None

    def query_all(self, soql):
        FakeSalesforce.queries.append(soql)
        sobject = re.search(r'FROM\s+(\w+)', soql).group(1)
        if sobject == 'TransactionUsageEntitlement':
            return [dict(t, GrantBindingTargetId=t['AssetId']) for t in self.order['usage_entitlements']]
        if sobject == 'UsageEntitlementBucket':
            return [dict(b, BucketBalanceUoMId=None) for b in self.order['entitlement_buckets']]
        if sobject in ('UsageSummary', 'UsageRatableSummary', 'UsageBillingPeriodItem'):
            return []                                            # first run: nothing to update
        raise AssertionError(f'unexpected SOQL on a dry run: {soql}')

    def create(self, payload):
        raise AssertionError(f'dry run tried to create {self.object_name}: {payload}')

    def update(self, record_id, payload):
        raise AssertionError(f'dry run tried to update {self.object_name} {record_id}: {payload}')


def test_bill_sync_replays_offline(monkeypatch, capsys):
    bill = json.loads(BILL.read_text())
    order = _order_snapshot()
    FakeSalesforce.order = order
    FakeSalesforce.queries = []
    monkeypatch.setattr('sync.billsync.resolve.SalesforceObject', FakeSalesforce)
    monkeypatch.setattr('sync.core.sf_step.SalesforceObject', FakeSalesforce)

    ctx = BillSyncContext.from_snapshot(BILL, dry_run=True)
    ctx._m3 = FakeM3ForBill(bill, order)
    ctx._sf_auth = object()                                     # never run the sf CLI
    run_steps(ctx, [Resolve(), EnsureUsageSummary(), EnsureUsageRatableSummary(),
                    EnsureUsageBillingPeriodItem(), LinkUsageSummary(), UpdateBucket()])

    usage = [li for li in bill['line_items'] if li['lineItemType'] == 'USAGE']
    assert len(ctx.state['lines']) == 6 == len(usage)
    assert ctx.state['sf_account_id'] == bill['bill']['accountCode']
    for line in ctx.state['lines']:                             # pay as you go: all usage is overage
        assert line['OverageQuantity'] == line['ConsumptionUnits']
        assert line['DebitedUnits'] == line['ConsumptionUnits']
        assert line['bucketId']
    assert len(ctx.state['usage_summaries']) == 6
    assert all(s['is_new'] for s in ctx.state['usage_summaries'].values())

    out = capsys.readouterr().out
    assert out.count('DRY RUN would create UsageSummary') == 6
    assert out.count('DRY RUN would create UsageRatableSummary') == 6
    assert out.count('DRY RUN would create UsageBillingPeriodItem') == 6
    assert sum('FROM TransactionUsageEntitlement' in q for q in FakeSalesforce.queries) == 1


@pytest.mark.parametrize('module', ['sync.ordersync.sync_order', 'sync.billsync.sync_bill'])
def test_cli_help(module, capsys):
    import importlib
    with pytest.raises(SystemExit) as e:
        importlib.import_module(module).main(['--help'])
    assert e.value.code == 0
    assert '--from-file' in capsys.readouterr().out
