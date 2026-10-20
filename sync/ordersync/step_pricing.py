"""Step 4 — the negotiated rates become Pricings on the order line's plan.

One Pricing per TransactionUsageEntitlement: the TUE says WHICH resource the
customer may use and FROM WHEN; the matching OrderItemRateCardEntry on the
configured card (mapping.RATE_CARD) says AT WHAT RATE. mapping.py turns the
resource code into the m3ter aggregation + segment.

    TUE RES-DOC-CHECK-BOOST-USA, from 2026-10-14
      + rate row  Base card / RES-DOC-CHECK-BOOST-USA / NegotiatedRate 0.0
      -> Pricing on plan vc_doc_check_00000102:
             aggregation document_report_standard_hybrid_count, segment {country: USA}
             startDate 2026-10-14T00:00:00.000Z, one band: unitPrice 0.0

A plan-level Pricing beats the PlanTemplate's Pricing for the same aggregation
and segment — that is how a negotiated rate overrides list price in m3ter
without touching the shared template. A negotiated 0.0 is a real price (free
checks for this customer) and is written as unitPrice 0; only a MISSING rate
(null, as on the Tier card) is an error.

No endDate on the Pricing: the plan is bespoke to this account and the
AccountPlan (step 5) carries the term, so the rate simply applies for as long
as the plan is attached. Re-pricing an amendment would end-date these and add
new ones — not this pass.

Key: ExternalMapping Salesforce/TransactionUsageEntitlement/<TUE Id> -> Pricing,
the same per-TUE key m3sh uses for the objects it derives from a TUE.
"""
from m3sdk import Aggregation, ExternalMapping, Pricing

from sync.core.dates import to_m3ter
from sync.core.step import Step

from .step_account import EXTERNAL_SYSTEM


class EnsurePricings(Step):
    name = 'pricing'

    def run(self, ctx):
        RATE_CARD = ctx.mapping.RATE_CARD
        snap = ctx.snapshot
        aggregations = {a.code: a for a in Aggregation.list(ctx.m3)}
        ctx.state['pricings'] = {}

        # Rates on the configured card, keyed by (order item, resource code).
        rates = {}
        for row in snap['order_item_rates']:
            card = row['RateCardEntry']['RateCard']['Name']
            resource = row['RateCardEntry']['UsageResource']['Code']
            if row.get('IsChosenRate') and card != RATE_CARD:
                self.say(ctx, f'WARNING Salesforce chose the {card!r} card for {resource} '
                              f'but mapping.RATE_CARD is {RATE_CARD!r}')
            if card == RATE_CARD:
                rates[(row['OrderItemId'], resource)] = row
        if not rates:
            raise RuntimeError(f'no rate rows on card {RATE_CARD!r} for this order — check mapping.RATE_CARD')

        for tue in snap['usage_entitlements']:
            resource = tue['UsageResource']['Code']
            plan = ctx.state['plans'][tue['OrderItemId']]

            # 1. Look before you create.
            mappings = ExternalMapping.find(ctx.m3, EXTERNAL_SYSTEM, 'TransactionUsageEntitlement', tue['Id'])
            if mappings:
                pricing = Pricing.get(ctx.m3, mappings[0].m3terId)
                self.say(ctx, f'{resource:<28} found via external mapping ({pricing.id})')
                ctx.state['pricings'][tue['Id']] = pricing
                continue

            # 2. The rate for this resource on the configured card.
            row = rates.get((tue['OrderItemId'], resource))
            if row is None:
                raise RuntimeError(f'{resource}: no entry on card {RATE_CARD!r} for order item {tue["OrderItemId"]}')
            rate = row.get('NegotiatedRate')
            if rate is None:
                raise RuntimeError(f'{resource}: entry on {RATE_CARD!r} has no NegotiatedRate '
                                   f'(a tiered card? tiered pricing is not modelled yet)')

            # 3. Resource -> aggregation + segment, then the payload.
            agg_code, segment = ctx.mapping.aggregation_and_segment(resource)
            aggregation = aggregations.get(agg_code)
            if aggregation is None:
                raise RuntimeError(f'aggregation {agg_code!r} is not in the m3ter org')

            pricing = self.create_or_pretend(ctx, Pricing, **self.build_payload(ctx, tue, plan, aggregation, segment, rate))
            self.create_or_pretend(ctx, ExternalMapping,
                                   externalSystem=EXTERNAL_SYSTEM, externalTable='TransactionUsageEntitlement',
                                   externalId=tue['Id'], m3terEntity='Pricing', m3terId=pricing.id)
            ctx.state['pricings'][tue['Id']] = pricing
        return ctx.state['pricings']

    @staticmethod
    def build_payload(ctx, tue, plan, aggregation, segment, rate) -> dict:
        order = ctx.snapshot['order']
        return {
            'planId': plan.id,
            'aggregationId': aggregation.id,
            'segment': segment,
            'startDate': to_m3ter(tue['EffectiveStartDateTime']),
            'type': 'DEBIT',
            'pricingBands': [{'lowerLimit': 0, 'fixedPrice': 0, 'unitPrice': rate}],
            'description': f"{tue['UsageResource']['Name']} negotiated rate, order {order['OrderNumber']}",
            'code': f"pricing_{tue['Id']}",
        }
