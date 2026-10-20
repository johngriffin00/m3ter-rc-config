"""Step 1 — read the whole order graph out of Salesforce, once.

m3sh queries Salesforce piecemeal as it goes (a SOQL here, a ReadObject
there, inside loops). We read everything up front into ctx.snapshot and the
m3ter steps work from that. Fewer API calls, and the snapshot can be saved
and replayed.

What an activated Revenue Cloud order leaves behind, and why each piece matters
to m3ter:

  Order                       the trigger. Status 'Activated', dates, the Account.
  Account, Contact            -> m3ter Account (step 2); the email m3ter insists on
                              comes from the first Contact.
  OrderItem                   one per product line. Carries the commitment stand-in
                              (UnitPrice) and the service dates.
  TransactionUsageEntitlement one per usage resource on the line — the row that
  (TUE)                       says "this customer is entitled to use resource X
                              from date A to date B". m3sh loops THESE to create
                              AccountPlans. Six for Document Check (3 features x 2 regions).
  Asset                       the lifecycle record of what was sold; its
                              LifecycleStart/EndDate are the AccountPlan dates.
  UsageEntitlementBucket      the consumption pots under the entitlement (a tree:
  (UEB)                       ParentId is a bucket or the UsageEntitlementAccount).
                              m3sh stores the Id on the AccountPlan as a custom field.
  OrderItemRateCardEntry      the NEGOTIATED RATE per resource per rate card, as
                              agreed on the quote — this is the price m3ter must
                              bill at (step 4). Document Check has two cards per
                              resource (List with a rate, Commit/Tier without).
  AssetRateCardEntry          the same rates copied onto the asset. Read for
                              cross-checking; the order-item copy is the source.

Every field name below is either standard or was proven by a query in the
revenue-cloud-config README or an m3sh workflow. Nothing is guessed; if the org
rejects one, fix the list here (and only here).
"""
from salesforcesdk import SalesforceObject
from sync.core.context import SF_API_VERSION
from sync.core.soql import clean, in_list
from sync.core.step import Step


class ReadOrder(Step):
    name = 'read order'

    def __init__(self, save=True):
        self.save = save

    def soql(self, ctx, soql):
        sf = SalesforceObject(ctx.sf_auth, api_version=SF_API_VERSION)
        records = [clean(r) for r in sf.query_all(soql)]
        return records

    def run(self, ctx):
        snap = ctx.snapshot

        # 1. The order. OrderNumber is the 8-digit human number; an 18-char Id also works.
        ref = ctx.order_ref
        where = f"OrderNumber = '{ref}'" if len(ref) == 8 and ref.isdigit() else f"Id = '{ref}'"
        orders = self.soql(ctx, f"""
            SELECT Id, OrderNumber, Status, AccountId, Account.Name, EffectiveDate, EndDate,
                   ActivatedDate, QuoteId
            FROM Order WHERE {where}""")
        if len(orders) != 1:
            raise RuntimeError(f'expected one order for {ref!r}, got {len(orders)}')
        order = snap['order'] = orders[0]
        self.say(ctx, f"order {order['OrderNumber']} ({order['Id']}) status {order['Status']}, "
                      f"account {order['Account']['Name']}")
        if order['Status'] != 'Activated':
            self.say(ctx, f"WARNING: order is {order['Status']}, not Activated — "
                          f"the usage entitlements below will not exist")

        # 2. The account (the bits an m3ter Account wants).
        snap['account'] = self.soql(ctx, f"""
            SELECT Id, Name, BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry
            FROM Account WHERE Id = '{order['AccountId']}'""")[0]

        # 2b. Contacts — an m3ter Account requires an emailAddress and a Salesforce
        #     Account has none of its own; the first contact's email stands in.
        snap['contacts'] = self.soql(ctx, f"""
            SELECT Id, Name, Email, Title FROM Contact WHERE AccountId = '{order['AccountId']}' ORDER BY CreatedDate""")
        self.say(ctx, f"{len(snap['contacts'])} contact(s): " + ', '.join(f"{c['Name']} <{c['Email']}>" for c in snap['contacts']))

        # 3. Order lines.
        items = snap['order_items'] = self.soql(ctx, f"""
            SELECT Id, OrderId, Product2Id, Product2.Name, Product2.ProductCode, Quantity, UnitPrice,
                   TotalPrice, ServiceDate, EndDate
            FROM OrderItem WHERE OrderId = '{order['Id']}'""")
        item_ids = [i['Id'] for i in items]
        self.say(ctx, f"{len(items)} order item(s): "
                      + ', '.join(f"{i['Product2']['ProductCode']} x{i['Quantity']} @ {i['UnitPrice']}" for i in items))

        # 4. Transaction usage entitlements — the m3sh loop variable.
        tues = snap['usage_entitlements'] = self.soql(ctx, f"""
            SELECT Id, AssetId, OrderItemId, UsageResourceId, UsageResource.Code, UsageResource.Name,
                   AccountId, EffectiveStartDateTime, EffectiveEndDateTime, ProductId, TransactionQuantity,
                   EntitlementQuantity, UsageModelType, EntitlementUomId, EntitlementUomClassId
            FROM TransactionUsageEntitlement WHERE OrderItemId IN ({in_list(item_ids)})""")
        self.say(ctx, f"{len(tues)} usage entitlement(s): "
                      + ', '.join(t['UsageResource']['Code'] for t in tues))

        # 5. Assets the entitlements hang off.
        asset_ids = sorted({t['AssetId'] for t in tues if t.get('AssetId')})
        snap['assets'] = self.soql(ctx, f"""
            SELECT Id, Name, AccountId, Product2Id, Product2.ProductCode, Status,
                   LifecycleStartDate, LifecycleEndDate
            FROM Asset WHERE Id IN ({in_list(asset_ids)})""") if asset_ids else []
        for a in snap['assets']:
            self.say(ctx, f"asset {a['Name']} ({a['Id']}) {a['LifecycleStartDate']} -> {a['LifecycleEndDate']}")

        # 6. Entitlement buckets under those entitlements.
        tue_ids = [t['Id'] for t in tues]
        snap['entitlement_buckets'] = self.soql(ctx, f"""
            SELECT Id, Name, TransactionUsageEntitlementId, EffectiveStartDateTime, EffectiveEndDateTime,
                   UsageResourceId, UsageResource.Code, BucketBalance, ParentId, Parent.Type
            FROM UsageEntitlementBucket
            WHERE TransactionUsageEntitlementId IN ({in_list(tue_ids)})""") if tue_ids else []
        self.say(ctx, f"{len(snap['entitlement_buckets'])} entitlement bucket(s)")

        # 7. Negotiated rates on the order lines — the prices m3ter will bill at.
        snap['order_item_rates'] = self.soql(ctx, f"""
            SELECT Id, Name, OrderItemId, RateCardEntryId, RateCardEntry.Name, RateCardEntry.RateCard.Name,
                   RateCardEntry.UsageResource.Code, NegotiatedRate, IsChosenRate, RateUnitOfMeasure.UnitCode
            FROM OrderItemRateCardEntry WHERE OrderItemId IN ({in_list(item_ids)})""")
        for r in snap['order_item_rates']:
            self.say(ctx, f"rate  {r['RateCardEntry']['UsageResource']['Code']:<28} "
                          f"{r['RateCardEntry']['RateCard']['Name']:<40} "
                          f"negotiated={r['NegotiatedRate']} chosen={r['IsChosenRate']}")

        # 8. The same rates as copied onto the asset (cross-check only).
        snap['asset_rates'] = self.soql(ctx, f"""
            SELECT Id, Name, AssetId, RateCardEntryId, RateCardEntry.Name, RateCardEntry.RateCard.Name,
                   RateCardEntry.UsageResource.Code, NegotiatedRate
            FROM AssetRateCardEntry WHERE AssetId IN ({in_list(asset_ids)})""") if asset_ids else []

        if self.save:
            ctx.save_snapshot()
        return snap
