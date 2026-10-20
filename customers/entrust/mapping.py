"""The catalog-specific lookups — the only brick that knows about Document Check.

Everything else in ordersync is generic Revenue Cloud -> m3ter plumbing. When
the catalog grows (a new feature, a new region, a second product) this file
changes and the steps do not. m3sh kept the equivalent in ExternalMappings of
type Product#UsageResource; a Python dict is easier to read and to diff.

Salesforce side                          m3ter side
  Product2.ProductCode  VC-DOC-CHECK  ->  PlanTemplate usd_default_pricing (product verification_check)
  UsageResource.Code    RES-DOC-CHECK-<FEATURE>-<REGION>
      FEATURE  BOOST / FLASH / SHERLOCK  ->  Aggregation document_report_standard_{hybrid,auto,manual}_count
      REGION   USA / ANY                 ->  segment {"country": "USA"} / {} (the catch-all segment)
"""

# Salesforce product code -> m3ter plan template code. One Plan per OrderItem is
# created from this template, so a second product means a second template here.
PLAN_TEMPLATE_BY_PRODUCT = {
    'VC-DOC-CHECK': 'usd_default_pricing',
}

# Feature (middle of the resource code) -> aggregation code.
AGGREGATION_BY_FEATURE = {
    'BOOST': 'document_report_standard_hybrid_count',
    'FLASH': 'document_report_standard_auto_count',
    'SHERLOCK': 'document_report_standard_manual_count',
}

# Region (end of the resource code) -> pricing segment. ANY is m3ter's empty
# segment, which prices every country not matched by a more specific one.
SEGMENT_BY_REGION = {
    'USA': {'country': 'USA'},
    'ANY': {},
}


def plan_template_code(product_code: str) -> str:
    try:
        return PLAN_TEMPLATE_BY_PRODUCT[product_code]
    except KeyError:
        raise KeyError(f'no m3ter plan template mapped for Salesforce product {product_code!r} '
                       f'— add it to ordersync/mapping.py') from None


def aggregation_and_segment(resource_code: str) -> tuple[str, dict]:
    """RES-DOC-CHECK-BOOST-USA -> ('document_report_standard_hybrid_count', {'country': 'USA'})"""
    parts = resource_code.split('-')
    feature, region = parts[-2], parts[-1]
    try:
        return AGGREGATION_BY_FEATURE[feature], SEGMENT_BY_REGION[region]
    except KeyError:
        raise KeyError(f'cannot map usage resource {resource_code!r} (feature {feature!r}, region {region!r}) '
                       f'— add it to ordersync/mapping.py') from None


def plan_code(product_code: str, order_number: str) -> str:
    """VC-DOC-CHECK + 00000102 -> vc_doc_check_00000102 (m3ter codes: no whitespace, keep it readable)."""
    return f"{product_code.lower().replace('-', '_')}_{order_number}"


# Which Salesforce rate card the sync prices from, while Revenue Cloud does not
# choose one itself (order 00000102 carried both cards with IsChosenRate false
# on every row). The Base card carries a single negotiated rate per resource;
# the Commit (Tier) card carries bands, which this pass does not model yet.
RATE_CARD = 'Document Check Rate Card - List (Base)'
