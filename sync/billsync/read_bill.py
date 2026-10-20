"""Step 1 — read the bill and every line on it out of m3ter, once.

The old handlerRC.py did this inside the webhook handler: Bill.get() on a
billing.bill.created/updated event, then worked from the embedded lineItems.
Here it is a brick of its own, so the rest of the sync can be replayed from
the saved snapshot and so the reading can be checked before anything is
derived from it.

What a Bill carries, and why each piece matters to Revenue Cloud:

  Bill header      accountId / accountCode -> which Salesforce Account (via
                   the Salesforce/Account external mapping the order sync
                   wrote); startDate / endDate -> the usage period; currency;
                   status (PENDING | APPROVED) and locked -> whether this bill
                   is final enough to sync.
  USAGE lines      one per Pricing that saw usage: quantity, averageUnitPrice,
                   subtotal, servicePeriod*, and pricingId — the key that leads
                   back to the TransactionUsageEntitlement (the order sync
                   mapped Salesforce/TransactionUsageEntitlement/<Id> -> that
                   Pricing). These become UsageSummary -> UsageRatableSummary
                   -> UsageBillingPeriodItem.
  USAGE_CREDIT     the grant (included units) netted off a USAGE line's
                   quantity to give DebitedUnits.
  OVERAGE_USAGE    units above the grant -> OverageUnits / OverageAmount.
  BALANCE_CONSUMED the prepayment drawdown — not synced, kept for the record.
  STANDING_CHARGE  the plan's standing charge (the 1,000 USD order line) —
                   not synced; the order already is.

Nothing is derived here. The netting and the Salesforce lookups are the
next brick; this one only reads, reports and saves.
"""
from collections import Counter

from m3sdk import Account, Bill

from sync.core.step import Step

SYNCED_TYPES = {'USAGE'}


class ReadBill(Step):
    name = 'read bill'

    def __init__(self, save=True):
        self.save = save

    def run(self, ctx):
        snap = ctx.snapshot

        # 1. The bill header — by id, or the account's latest. An account can be
        #    given by code (the Salesforce Account Id, as the order sync set it)
        #    or by m3ter id; the latest-bill endpoint wants the id.
        if ctx.latest:
            account = Account.get_by_code(ctx.m3, ctx.bill_ref)
            account_id = account.id if account else ctx.bill_ref
            self.say(ctx, f"account {ctx.bill_ref} -> {account.name + ' ' if account else ''}{account_id}")
            bill = Bill.latest_for_account(ctx.m3, account_id)
        else:
            bill = Bill.get(ctx.m3, ctx.bill_ref)
        header = {k: v for k, v in bill.__dict__.items() if k != 'lineItems'}
        snap['bill'] = header
        self.say(ctx, f"bill {bill.id} for {header.get('accountCode')} ({header.get('accountId')}) "
                      f"{header.get('startDate')} -> {header.get('endDate')} billDate {header.get('billDate')} "
                      f"{header.get('currency')} total {header.get('billTotal')} "
                      f"status {header.get('status')} locked {header.get('locked')}")
        if header.get('status') != 'APPROVED':
            self.say(ctx, f"WARNING: bill is {header.get('status')}, not APPROVED — figures may still change")

        # 2. Every line item, from the documented endpoint (paged).
        items = bill.line_items(ctx.m3)
        snap['line_items'] = [li.to_dict() for li in items]
        by_type = Counter(li.lineItemType for li in items)
        self.say(ctx, f"{len(items)} line item(s): " + ', '.join(f'{t} x{n}' for t, n in sorted(by_type.items())))

        # 3. Show the lines that will be synced, in a form that can be checked
        #    against the m3ter Console bill.
        for li in items:
            if li.lineItemType not in SYNCED_TYPES:
                continue
            self.say(ctx, f"USAGE {getattr(li, 'description', ''):<60} qty {getattr(li, 'quantity', None):>10} "
                          f"@ {getattr(li, 'averageUnitPrice', None)} = {getattr(li, 'subtotal', None)} "
                          f"{getattr(li, 'servicePeriodStartDate', '')[:10]}..{getattr(li, 'servicePeriodEndDate', '')[:10]} "
                          f"pricing {getattr(li, 'pricingId', None)} plan {getattr(li, 'planId', None)}")
        embedded = len(getattr(bill, 'lineItems', None) or [])
        if embedded and embedded != len(items):
            self.say(ctx, f'WARNING: the bill embeds {embedded} line items but the endpoint returned {len(items)}')

        if self.save:
            ctx.save_snapshot()
        return snap
