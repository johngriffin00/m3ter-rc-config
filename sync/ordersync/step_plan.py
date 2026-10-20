"""Step 3 — a Plan per order line, bespoke to the account.

Where this departs from m3sh. The Entrust Order Handler attaches a PRE-EXISTING
plan ("Load available plans for a m3 Product", pick the one in the right
currency). That works when every customer pays list price. Order 00000102 does
not: every resource arrived with a negotiated rate, and in m3ter a negotiated
rate is a Pricing on a Plan that overrides the PlanTemplate's. So each order
line gets its own Plan, created from the product's template, and step 4 hangs
the negotiated Pricings off it. (This is also the Entrust production pattern:
their plans are coded checks_<opportunityId>.)

Why bespoke (accountId set)? A plan carrying one customer's negotiated rates
must never be attachable to another customer. m3ter enforces that for a plan
created with accountId: it can only ever be attached to that account, and the
console lists it under the account rather than in the shared catalog.

The order line's price is the plan's standing charge. OrderItem.UnitPrice x
Quantity (1,000 USD on 00000102, the stand-in for the commitment) becomes
Plan.standingCharge: a fixed amount per billing cycle, prorated, billed in
advance or in arrears as the PlanTemplate says. Usage is priced on top of it
by the step 4 Pricings. (When the real commitment arrives it will replace
this with a Commitment / Balance; the standing charge is the first-pass shape.)

Keys and idempotency:
    code      <product code>_<OrderNumber>      e.g. vc_doc_check_00000102 — readable in the console
    mapping   Salesforce/OrderItem/<OrderItem Id> -> Plan — the durable, unique key
    custom    sfOrderId / sfOrderNumber / sfOrderItemId / sfQuoteId / sfProductCode for traceability
"""
from m3sdk import ExternalMapping, Plan, PlanTemplate

from sync.core.step import Step

from .mapping import plan_code, plan_template_code
from .step_account import EXTERNAL_SYSTEM


class EnsurePlans(Step):
    name = 'plan'

    def run(self, ctx):
        account = ctx.state['account']
        order = ctx.snapshot['order']
        templates = {t.code: t for t in PlanTemplate.list(ctx.m3)}
        plans_by_code = {p.code: p for p in Plan.list(ctx.m3)}
        ctx.state['plans'] = {}

        for item in ctx.snapshot['order_items']:
            product_code = item['Product2']['ProductCode']
            code = plan_code(product_code, order['OrderNumber'])

            # 1. Look before you create.
            mappings = ExternalMapping.find(ctx.m3, EXTERNAL_SYSTEM, 'OrderItem', item['Id'])
            if mappings:
                plan = Plan.get(ctx.m3, mappings[0].m3terId)
                self.say(ctx, f'found via external mapping: {plan.code} ({plan.id})')
                ctx.state['plans'][item['Id']] = plan
                continue

            # 1b. Code already taken (earlier run died before the mapping)? Adopt it.
            plan = plans_by_code.get(code)
            if plan:
                self.say(ctx, f'found by code without a mapping: {plan.code} ({plan.id}) — adding mapping')
            else:
                template_code = plan_template_code(product_code)
                template = templates.get(template_code)
                if template is None:
                    raise RuntimeError(f'plan template {template_code!r} is not in the m3ter org — '
                                       f'load the product config before syncing orders')
                plan = self.create_or_pretend(ctx, Plan, **self.build_payload(ctx, item, template, account, code))

            self.create_or_pretend(ctx, ExternalMapping,
                                   externalSystem=EXTERNAL_SYSTEM, externalTable='OrderItem', externalId=item['Id'],
                                   m3terEntity='Plan', m3terId=plan.id)
            ctx.state['plans'][item['Id']] = plan
        return ctx.state['plans']

    @staticmethod
    def build_payload(ctx, item, template, account, code) -> dict:
        order = ctx.snapshot['order']
        line_total = (item.get('UnitPrice') or 0) * (item.get('Quantity') or 0)
        return {
            'planTemplateId': template.id,
            'code': code,
            'name': f"{item['Product2']['Name']} Plan {order['OrderNumber']} ({account.name})",
            'accountId': account.id,          # bespoke: attachable to this account only
            'bespoke': True,
            'standingCharge': line_total,     # OrderItem.UnitPrice x Quantity, per billing cycle
            'standingChargeDescription': f"{item['Product2']['Name']} commitment, order {order['OrderNumber']}",
            'customFields': {
                'sfOrderId': order['Id'],
                'sfOrderNumber': order['OrderNumber'],
                'sfOrderItemId': item['Id'],
                'sfQuoteId': order.get('QuoteId') or '',
                'sfProductCode': item['Product2']['ProductCode'],
            },
        }
