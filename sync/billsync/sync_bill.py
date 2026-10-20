"""m3ter bill -> Revenue Cloud usage sync. The parent script: wires the bricks together.

    set -a; source parameters/m3ter.env; set +a
    uv run python -m sync.billsync.sync_bill --bill <bill uuid>
    uv run python -m sync.billsync.sync_bill --latest --account 001Ws00005YYRPSIA5
    uv run python -m sync.billsync.sync_bill --from-file customers/entrust/snapshots/bills/<file>.json --dry-run

Steps so far:
    1. ReadBill        m3ter -> ctx.snapshot (saved to customers/entrust/snapshots/bills/<accountCode>-<billDate>-<id>.json)
    2. Resolve         account -> Salesforce Account, pricing -> TUE / Asset / bucket, grant + overage netting
                       -> ctx.state['lines'], one entry per USAGE line (reads m3ter and Salesforce, writes nothing)
    3. EnsureUsageSummary  a UsageSummary per line on Account + Asset + dates + bucket; Status New on create only
    4. EnsureUsageRatableSummary   the rated view, keyed on the UsageSummary's RatableSummaryId
    5. EnsureUsageBillingPeriodItem  the billable view, keyed on the UsageSummary's LiableSummaryId
    6. LinkUsageSummary  RatableSummaryId + LiableSummaryId onto the UsageSummary whenever missing or different
    7. UpdateBucket      BucketBalance + ConsumedEntitlement on the entitlement bucket

The Python port of the m3sh "m3ter -> SF RCA Usage Data" workflow set
(customers/entrust/m3sh/, chart in customers/entrust/docs/entrust-usage-data-structure.html).
The remaining bricks, in m3sh order: resolve + net (account -> Salesforce
Account, pricing -> entitlement / asset / bucket, grant and overage netting),
then UsageSummary, UsageRatableSummary, UsageBillingPeriodItem, and the
bucket balance update.
"""
import argparse

from sync.billsync.context import BillSyncContext
from sync.billsync.read_bill import ReadBill
from sync.billsync.resolve import Resolve
from sync.billsync.step_link import LinkUsageSummary, UpdateBucket
from sync.billsync.step_ratablesummary import EnsureUsageRatableSummary
from sync.billsync.step_ubpi import EnsureUsageBillingPeriodItem
from sync.billsync.step_usagesummary import EnsureUsageSummary
from sync.core.step import run_steps


def run(bill_ref=None, latest=False, from_file=None, sf_alias='m3ter', dry_run=False, customer=None):
    if from_file:
        ctx = BillSyncContext.from_snapshot(from_file, sf_alias=sf_alias, dry_run=dry_run, **({'customer': customer} if customer else {}))
        steps = []                                  # snapshot already in hand
    else:
        ctx = BillSyncContext(bill_ref=bill_ref, latest=latest, sf_alias=sf_alias, dry_run=dry_run, **({'customer': customer} if customer else {}))
        steps = [ReadBill()]
    steps += [
        Resolve(),            # 2. everything the Salesforce writes will need, netted
        EnsureUsageSummary(), # 3. the usage record the other two hang off
        EnsureUsageRatableSummary(),     # 4. the rated view
        EnsureUsageBillingPeriodItem(),  # 5. the billable view
        LinkUsageSummary(),   # 6. the summary points at the other two
        UpdateBucket(),       # 7. the bucket records the usage
    ]
    return run_steps(ctx, steps)


def main(argv=None):
    p = argparse.ArgumentParser(description='Sync an m3ter bill to Revenue Cloud usage objects')
    p.add_argument('--bill', help='m3ter Bill id')
    p.add_argument('--account', help='m3ter Account code (the SF Account Id) or id, used with --latest')
    p.add_argument('--latest', action='store_true', help='take the latest bill for --account')
    p.add_argument('--from-file', help='replay a saved snapshot instead of querying m3ter')
    p.add_argument('--customer', help='customers/<name>/ whose mapping.py and snapshots to use (default entrust)')
    p.add_argument('--sf-org', default='m3ter', help='sf CLI org alias (default m3ter)')
    p.add_argument('--dry-run', action='store_true', help='do the lookups, print Salesforce payloads, write nothing')
    args = p.parse_args(argv)

    if args.from_file:
        return run(from_file=args.from_file, sf_alias=args.sf_org, dry_run=args.dry_run, customer=args.customer)
    if args.latest:
        if not args.account:
            p.error('--latest needs --account <code or id>')
        return run(bill_ref=args.account, latest=True, sf_alias=args.sf_org, dry_run=args.dry_run, customer=args.customer)
    if not args.bill:
        p.error('give --bill, --latest --account, or --from-file')
    run(bill_ref=args.bill, sf_alias=args.sf_org, dry_run=args.dry_run, customer=args.customer)


if __name__ == '__main__':
    main()
