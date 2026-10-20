"""Generate verification-quoting.recommendation.yaml (beside this script) (v2) from the quote

    cd customers/entrust/analysis && python3 build_quoting_recommendation.py "Entrust quote reconstruction - Signicat and Wolt.xlsx" models/verification-quoting.recommendation.yaml

reconstruction workbook. Prose sections are written here; numbers come from
the xlsx so the fixtures match the bills to the cent."""
import sys
import openpyxl

XLSX = sys.argv[1]
OUT = sys.argv[2]
wb = openpyxl.load_workbook(XLSX, data_only=True)

# ---- product catalogue in scope: union of quote lines, keyed by m3ter meter
PRODUCTS = [
    # code, name, meter, category, country_priced
    ("VC-DOCUMENT-REPORT-STANDARD-HYBRID", "Document Check - Boost", "document_report_standard_hybrid", "Document Checks", True),
    ("VC-DOCUMENT-REPORT-STANDARD-AUTO", "Document Check - Flash", "document_report_standard_auto", "Document Checks", False),
    ("VC-DOCUMENT-REPORT-STANDARD-MANUAL", "Document Check - Sherlock", "document_report_standard_manual", "Document Checks", False),
    ("VC-DOCUMENT-REPORT-DRIVER-VERIFICATION", "Document Check - Driver Verification", "document_report_driver_verification", "Document Checks", True),
    ("VC-AUTOFILL", "OCR Autofill", "autofill", "Document Checks", False),
    ("VC-FACIAL-SIMILARITY-REPORT-STANDARD", "Facial Similarity Check - Selfie Hybrid", "facial_similarity_report_standard", "Biometrics", False),
    ("VC-FACIAL-SIMILARITY-REPORT-VIDEO", "Facial Similarity Check - Video", "facial_similarity_report_video", "Biometrics", False),
    ("VC-FACIAL-SIMILARITY-REPORT-MOTION", "Facial Similarity Check - Motion", "facial_similarity_report_motion", "Biometrics", False),
    ("VC-KNOWN-FACES-REPORT-STANDARD", "Facial Similarity Check Upgrade - Known Faces", "known_faces_report_standard", "Biometrics", False),
    ("VC-REPEAT-ATTEMPTS-REPORT-STANDARD", "Repeat Attempts", "repeat_attempts_report_standard", "Biometrics", False),
    ("VC-APPLICANT-FRAUD-REPORT-STANDARD", "Device Intelligence - Standard", "applicant_fraud_report_standard", "Biometrics", False),
    ("VC-PROOF-OF-ADDRESS-REPORT-STANDARD", "Proof of Address", "proof_of_address_report_standard", "Identity Data", False),
]
by_meter = {m: (c, n) for c, n, m, _, _ in PRODUCTS}

LIST = {}       # meter -> EUR list price (from column F of any quote tab)
quotes = []
for title, key in (("Signicat quote", "SIGNICAT-2025"), ("Wolt quote 2025", "WOLT-2025"), ("Wolt quote 2026", "WOLT-2026")):
    ws = wb[title]
    rows = [r for r in ws.iter_rows(values_only=True)]
    hdr = {r[0]: r[1] for r in rows[3:16] if r[0]}
    lines = []
    in_lines = False
    for r in rows:
        if r[0] == "Line":
            in_lines = True
            continue
        if in_lines and r[0] and str(r[0]).startswith(("S-", "W2")):
            lid, acct, prod, meter, country, lp, disc, net, jv, jval, iv, ival = r
            LIST[meter] = float(lp)
            code = by_meter[meter][0]
            country_val = {"All": None, "ANY (all other)": "ANY", "JPN": "JPN", "KAZ; SRB": "KAZ,SRB"}[country]
            lines.append({
                "line": lid, "product": code, "country": country_val,
                "m3ter_accounting_product": acct, "m3ter_line_name": prod,
                "list_price": float(lp), "discount_pct": round(float(disc) * 100, 2), "net_price": float(net),
                "jan_2026_volume": int(jv), "jan_2026_value": float(jval),
                "illustrative_annual_volume": round(float(iv)), "illustrative_annual_value": round(float(ival), 2),
            })
        elif in_lines and r[0] == "Total":
            in_lines = False
    quotes.append({
        "code": key, "customer": hdr["Customer"], "m3ter_account": hdr["m3ter account code"],
        "opportunity": hdr["Salesforce opportunity"], "type": hdr["Quote type"],
        "term_start": hdr["Term start"].date().isoformat(), "term_end": hdr["Term end"].date().isoformat(),
        "term_months": int(hdr["Term (months)"]), "currency": hdr["Currency"], "rate_card": hdr["Rate card"],
        "bill_frequency": hdr["Bill frequency"],
        "spend_commitment": float(hdr["Minimum prepayment (EUR)"]), "csm_fee": float(hdr["CSM fee commitment (EUR)"]),
        "quote_total": float(hdr["Quote total (EUR)"]), "lines": lines,
    })

bills = wb["January 2026 bills"]
BILLS = []
for r in bills.iter_rows(min_row=6, max_row=7, values_only=True):
    BILLS.append({"customer": r[0], "m3ter_bill": r[1], "usage_at_quote_prices": float(r[2]), "drawn_from_commitment": float(r[4]), "bill_total": float(r[6])})


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


o = []
w = o.append
w("""# Revenue Cloud recommendation v2: the Verification Check catalog, shaped by the quotes
#
# Generated 2026-10-06 from "Entrust quote reconstruction - Signicat and Wolt.xlsx"
# (three renewal quotes rebuilt from m3ter plans, pricings and the January 2026
# bills). v1 (verification-catalog.recommendation.yaml) started from the m3ter
# catalog and asked "what products exist?"; this file starts from the quotes
# and asks "what must the catalog contain so that a seller can produce THESE
# quotes, and rating then produces THESE bills?" It is deliberately narrower:
# 12 metered products, one attribute, one rate card, and the two commercial
# products the quotes need that v1 did not have at all (a spend commitment
# with drawdown, and a customer-success fee).
#
# How to read this file
#   * `quoting_experience:` is the target — the quote a seller builds and the
#     customer signs. Everything under `catalog:` exists to make it possible.
#   * `quotes:` are the three real quotes as acceptance fixtures: build the
#     catalog, raise these quotes, and the lines, net prices and totals must
#     match. The January 2026 bills are the rating fixtures.
#   * `verify_in_org:` lists what must be confirmed by describe or by a trial
#     quote before the JSON is written, in the order that unblocks the most.
#   * Keys prefixed `m3ter_` are copied from the exports/workbook verbatim.
#   * Rationale: m3ter-to-revenue-cloud.md (v1) still applies to the
#     meter -> product mapping; the new decisions are D8-D12 below.

meta:
  version: 2
  generated: 2026-10-06
  supersedes: verification-catalog.recommendation.yaml   # kept; this is the subset that quoting needs, plus commercial products
  sources:
    - Entrust quote reconstruction - Signicat and Wolt.xlsx   # m3ter Postgres (customerdb.entrust), queried 2026-10-06
    - 0010800002pezwdAAA-config.json, 00108000031Xp6xAAC-config.json   # v1 inputs, for meter/aggregation codes
  org: m3ter-arm-260
  status: recommendation, not applied. The v1 worked example in the org (ids in v1 meta.status) will be cleaned down first.

# ==============================================================================
# The quote a seller should be able to build. This is the spec.
# ==============================================================================
quoting_experience:
  header:
    - 12-month term with explicit start and end (renewal quotes are dated contracts, not evergreen)
    - one currency per quote (EUR here), chosen by picking the EUR rate card at quote time
    - monthly billing in arrears for usage; commitment and fees billed up front
  usage_lines:
    - one line per product, taken from the price book at the rate card's list price
    - a seller-entered percentage discount per line giving a net unit price; the net price is what rating uses
    - document checks can be split by Country, so the same product appears on several lines with different net prices (ANY / JPN / KAZ,SRB); usage carries the country and is rated at that line's price
    - free add-ons (0.00 list) are on the quote so the customer sees them and usage is reported
    - an illustrative annual volume per line, so the quote shows an annual value even though usage is not committed per line
  commercial_lines:
    - a spend commitment (m3ter "minimum prepayment", NetSuite usage ACV) billed up front; rated usage draws the balance down and overage is billed when it runs out
    - an optional customer-success fee, flat, billed up front
  totals:
    - quote total = spend commitment + CSM fee; usage lines carry no committed value of their own
  outputs:
    - a contract with the net rates and the commitment balance, so usage rating and drawdown reproduce the m3ter bills in `bills_jan_2026`

# ==============================================================================
# What each section becomes in Revenue Cloud (seq = load order in the data model).
# ==============================================================================
rc_mapping:
  catalog.attributes:        [AttributePicklist(1), AttributePicklistValue(2), AttributeDefinition(3)]
  catalog.classifications:   [ProductClassification(4), ProductClassificationAttr(5)]
  catalog.units:             [UnitOfMeasureClass(7), UnitOfMeasure(6)]        # lookup-only where the org has them
  catalog.products[].resource: [UsageResource(8), ProductUsageResource(15)]
  catalog.products:          [Product2(10), ProductSellingModelOption(14)]
  catalog.commercial_products: [Product2(10), ProductSellingModelOption(14), UsageResource(8), ProductUsageResource(15), ProductUsageGrant(16), UsagePrdGrantBindingPolicy(17)]   # the commitment only
  catalog.categories:        [ProductCatalog(11), ProductCategory(12), ProductCategoryProduct(13)]
  price_book:                [PricebookEntry(19), RateCard(20), PriceBookRateCard(21), RateCardEntry(22)]   # Standard Price Book is lookup-only
  quotes:                    "nothing: acceptance fixtures for the quote UI, not catalog"

# ==============================================================================
catalog:
  selling_models:
    usage: {use: PSM_TermMonthly, verify_in_org: "exists in org (config/claude/05); TermDefined, 1-month pricing term; the 12-month term is set on the quote line"}
    one_time: {code: PSM-ONE-TIME, name: One-Time, selling_model_type: OneTime, verify_in_org: "does a OneTime ProductSellingModel exist? create if not"}
    decision: D8

  units:
    class: {code: VERIFICATION-UOM-CLASS, name: Verification Usage, existing: 1BQWs0000006wfdOAA}
    members:
      - {code: CHECK, name: Check, existing: 0hEWs0000018yEXMAY}
    rate_units:
      - {code: EUR, existing: 0hEWs0000018yHlMAI, class: Currency}
    note: USD and BLOCK are not needed by these quotes; they stay in the org from v1 and do no harm.

  attributes:
    - code: COUNTRY
      name: Country
      m3ter_field: country                # WHAT field on the document-check meters; m3ter segments its aggregations on it
      picklist:
        code: PL-VC-COUNTRY
        values:
          - {code: ANY, value: ANY, default: true, note: "every country without its own line"}
          - {code: JPN, value: JPN}
          - {code: KAZ, value: KAZ}
          - {code: SRB, value: SRB}
      price_impacting: true
      list_price_varies: false            # list is 2.28 for every country; only the NEGOTIATED price varies
      decision: D9
    # IS-RETRY from v1 is dropped: no line on these quotes uses it.

  classifications:
    - {code: PC-VERIFICATION-CHECK, name: Verification Check, attributes: []}
    - {code: PC-VERIFICATION-CHECK-COUNTRY, name: Verification Check (country-priced), attributes: [COUNTRY], used_by: [VC-DOCUMENT-REPORT-STANDARD-HYBRID, VC-DOCUMENT-REPORT-DRIVER-VERIFICATION]}

  product_catalog: {code: CAT-VERIFICATION, name: Verification Catalog, existing: 0ZSWs000001B5OnOAK}
  categories:
    - {code: CAT-DOCUMENT-CHECKS, name: Document Checks}
    - {code: CAT-BIOMETRICS, name: Biometrics}
    - {code: CAT-IDENTITY-DATA, name: Identity Data}
    - {code: CAT-COMMERCIAL, name: Commitments & Fees}

  # One Product2 per m3ter meter on the quotes. Each implies Product2 (UsageModelType
  # Pack) + PSMO (Term Monthly) + UsageResource + ProductUsageResource + PricebookEntry 0.00
  # + RateCardEntry on the EUR card. Rates are under price_book.rates.
  products:""")
for code, name, meter, cat, cp in PRODUCTS:
    w(f"""    - code: {code}
      name: {q(name)}
      category: {q(cat)}
      m3ter_meter: {meter}
      m3ter_aggregation: {meter}_count
      resource: {{code: RES-{code[3:]}, name: {q(name + ' Checks')}, unit: CHECK, category: Usage}}
      classification: {'PC-VERIFICATION-CHECK-COUNTRY' if cp else 'PC-VERIFICATION-CHECK'}""")
    if cp:
        w(f"      country_priced: true          # quote lines split by COUNTRY; usage carries country")
    if LIST.get(meter, 0) == 0:
        w(f"      free_add_on: true             # 0.00 list, on the quote so usage is visible (v1 D7)")

w("""
  # Products the quotes need that are not metered checks. See D10, D11.
  commercial_products:
    - code: VC-SPEND-COMMITMENT-EUR
      name: Verification Spend Commitment (EUR)
      category: Commitments & Fees
      m3ter_equivalent: minimum_prepayment balance (BALANCE_CONSUMED bill lines); contract customFields_nsUsageACV
      usage_model_type: CommitmentSpend   # picklist value seen in describe (README); never used by this repo yet
      selling_model: PSM-ONE-TIME          # billed up front, once per term
      pricing: {list_price: 1.00, unit: EUR, quantity_is_amount: true}   # quote quantity = committed EUR; 201262.83 -> qty 201262.83 at 1.00
      resource: {code: RES-VC-SPEND-BALANCE-EUR, name: Verification Spend Balance (EUR), unit: EUR, category: Currency}
      drawdown:
        from: all usage_lines on the same quote, at their net price
        order: "commitment first, then overage billed monthly at net price (Wolt 2025: balance exhausted before January, so January usage billed in full)"
        policy: "UsageCommitmentPolicy / UsagePrdGrantBindingPolicy: which one applies to CommitmentSpend is verify_in_org item 1"
      decision: D10
    - code: VC-CSM-FEE
      name: Customer Success Fee
      category: Commitments & Fees
      m3ter_equivalent: contract customFields_CSMFeeCommitment
      usage_model_type: null              # not metered
      selling_model: PSM-ONE-TIME
      pricing: {list_price: 0.00, unit: EUR, negotiated: true, note: "no list price exists in m3ter; 9,600 on Wolt 2026, 0 elsewhere"}
      decision: D11

# ==============================================================================
# One rate card, EUR, under the Standard Price Book (v1 D1, verified in org).
# ==============================================================================
price_book:
  use: Standard Price Book                # lookup-only; the only price book in the org
  rate_card:
    code: RC-B-EUR
    name: Verification Rate Card B (EUR)
    existing: 1CIWs0000006kbFOAQ          # built 2026-10-06 (v1); reuse
    type: Base
    currency: EUR
    rate_unit: EUR
    negotiable: true                      # REQUIRED: per-line discounts must reach rating (D12)
    effective_from: 2025-01-27
    m3ter_plan_template: rate_card_b_eur_default_pricing
  rates:                                  # list price per check, EUR, one flat band; from the workbook column F""")
for code, name, meter, cat, cp in PRODUCTS:
    w(f"    {code}: {LIST[meter]:.2f}")
w("""  pricebook_entries: "0.00 for every product above and the CSM fee; the commitment's entry is 1.00 (see commercial_products)"

# ==============================================================================
# Acceptance fixtures: the three quotes, as the seller should build them.
# Net prices and totals are from m3ter; illustrative volumes are the workbook's
# allocation of the commitment across lines by January 2026 value.
# ==============================================================================
quotes:""")
for qt in quotes:
    w(f"""  - code: {qt['code']}
    customer: {q(qt['customer'])}
    m3ter_account: {qt['m3ter_account']}
    opportunity: {qt['opportunity']}
    type: {qt['type']}
    term: {{start: {qt['term_start']}, end: {qt['term_end']}, months: {qt['term_months']}}}
    currency: {qt['currency']}
    rate_card: RC-B-EUR
    bill_frequency: {qt['bill_frequency']}
    commercial_lines:
      - {{product: VC-SPEND-COMMITMENT-EUR, quantity: {qt['spend_commitment']:.2f}, unit_price: 1.00, amount: {qt['spend_commitment']:.2f}}}
      - {{product: VC-CSM-FEE, quantity: 1, unit_price: {qt['csm_fee']:.2f}, amount: {qt['csm_fee']:.2f}}}
    expected_total: {qt['quote_total']:.2f}
    usage_lines:""")
    for ln in qt["lines"]:
        country = f", country: {ln['country']}" if ln["country"] else ""
        w(f"      - {{line: {ln['line']}, product: {ln['product']}{country}, list: {ln['list_price']:.2f}, discount_pct: {ln['discount_pct']}, net: {ln['net_price']:.2f}, illustrative_annual_volume: {ln['illustrative_annual_volume']}, illustrative_annual_value: {ln['illustrative_annual_value']:.2f}, m3ter_accounting_product: {ln['m3ter_accounting_product']}}}")
w("""
quote_notes:
    - WOLT-2025 line W25-03 is one quote line for two countries (KAZ, SRB) at one price. With a single-select COUNTRY attribute that is two lines at the same net price; see open_questions.
    - WOLT-2026 line W26-02 is the JPN segment although its m3ter accounting product is named "Document Check - USA". The quote line is JPN.
    - Lines with 0.00 list and 0 discount are the free add-ons; they stay on the quote.

# Rating fixtures: January 2026 bills recomputed from the quote net prices matched
# m3ter to the cent. After the catalog is built and a trial quote contracted, rating
# the same quantities must give the same numbers.
bills_jan_2026:""")
for b in BILLS:
    w(f"  - {{customer: {q(b['customer'])}, m3ter_bill: {b['m3ter_bill']}, usage_at_net_prices: {b['usage_at_quote_prices']:.2f}, drawn_from_commitment: {b['drawn_from_commitment']:.2f}, billed: {b['bill_total']:.2f}}}")

w("""
# ==============================================================================
decisions:
  D8:
    title: Term Monthly selling model, not Evergreen
    because: >-
      All three quotes are dated renewals (start, end, 12 months). v1 chose Evergreen
      Monthly because m3ter bills monthly with no term; the quotes show the term is the
      contract, and renewal quoting in Revenue Cloud needs a TermDefined selling model
      so the asset has an end date to renew from. PSM_TermMonthly already exists.
  D9:
    title: Country is a price-impacting attribute on two products, with no catalog adjustment
    because: >-
      m3ter prices document checks by country segment, but the LIST price is the same
      for every country (2.28); only the negotiated price differs per customer. So the
      catalog defines COUNTRY (price impacting, so it appears on the quote line and on
      usage) and sets no AttributeBasedAdjRule. Each country becomes its own quote line
      of the same product with its own discount. This is the Claude catalog's
      model-tier pattern minus the adjustment rules.
    rejected:
      - One Product2 per country ("Document Check - JPN"): 4x the products, and new countries mean new products instead of a picklist value.
      - Catalog-level country adjustments: there is nothing to adjust at list; the differences are contract terms.
  D10:
    title: The minimum prepayment is a CommitmentSpend product with a currency usage resource
    because: >-
      The quotes' largest number is a spend commitment that usage draws down
      (BALANCE_CONSUMED lines on the bills) with overage billed once exhausted.
      Product2.UsageModelType has a CommitmentSpend value (describe, README) and
      UsageResource.Category has Currency (seen in the UI build) — this is the shape
      Revenue Cloud provides for exactly this. Quantity = committed amount at 1.00/unit
      so one product serves every customer. v1 had no equivalent; it was the biggest gap.
    rejected:
      - Grants (ProductUsageGrant) of a fixed EUR quantity per product: the amount differs per customer, and grants are quantities, not money.
      - A plain one-time product with no resource: bills the prepayment but nothing draws it down; rating would double-charge.
  D11:
    title: CSM fee is a one-time product at 0.00 list, negotiated
    because: >-
      m3ter holds only the amount (9,600 on one contract, empty elsewhere); there is no
      list. A one-time product the seller prices on the line is the simplest honest shape.
  D12:
    title: Discounts live on the quote line; the rate card must be Negotiable
    because: >-
      Every usage line is list minus a percentage. That is standard quote-line discounting,
      but for USAGE the net price must reach rating, which Revenue Cloud does through
      negotiable rate card entries captured on the contract/asset. The rate card is
      already Negotiable in the org. Whether the captured negotiated rate is what the
      rating engine uses is verify_in_org item 2 — it is the single assumption this whole
      design rests on.

# ==============================================================================
# Things to confirm in m3ter-arm-260 before writing config/entrust/*.json, in the
# order that unblocks the most. Items 1-2 decide the design; 3-5 decide field values.
# ==============================================================================
verify_in_org:
  - "1. Describe Product2.UsageModelType (confirm CommitmentSpend is createable at the pinned API version) and UsageCommitmentPolicy / UsagePrdGrantBindingPolicy: which policy binds a CommitmentSpend product's balance to the Pack products' usage, and whether it needs an Anchor."
  - "2. Trial quote: one Pack product on the EUR card, discount 50% on the line, contract it, rate a usage record — does rating use the net price? Describe objects whose name contains RateCardEntry to find where the negotiated rate is stored."
  - "3. Describe ProductSellingModel: does a OneTime model exist? (config/claude/05 has TermMonthly and EvergreenMonthly only)."
  - "4. Trial quote with COUNTRY on two lines of the same product: does the quote UI allow two lines of one product differing only by attribute value, and does usage with country=JPN rate at the JPN line's price?"
  - "5. ProductClassificationAttr.IsRequired would not save true from the UI (v1). COUNTRY must be required on its two products, so set it by API and check."
  - "6. Decision tables: after building, refresh the four pricing tables (config/catalog.toml) before any quote test; the empty product browser on 6 Oct was a stale table, not missing data."

open_questions:
  - KAZ,SRB as one line: single-select COUNTRY makes it two lines at the same price. Acceptable, or does the seller need a multi-country line (then COUNTRY is a multi-select picklist, which changes how usage matches)?
  - CSM fee: one-time at term start, or an annual recurring fee that renews with the contract? The quote total treats it as charged on top of the commitment, once.
  - Overage policy: when the commitment is exhausted mid-term (Wolt 2025), is overage billed monthly at the net price (what m3ter did) — confirm this is the UsageOveragePolicy default.
  - Illustrative annual volume: show it on the quote line as quantity (then the line value is quantity x net) or leave quantity 1 and present the allocation in the quote document only? Rating does not care; the customer's document does.
  - The 21 products in v1 that are not on these quotes: add them back after the quoting flow is proven, same shape, no new decisions.
""")

open(OUT, "w").write("\n".join(o) + "\n")
import yaml
d = yaml.safe_load(open(OUT))
print("yaml ok:", len(d["catalog"]["products"]), "products;", len(d["quotes"]), "quotes;", sum(len(q["usage_lines"]) for q in d["quotes"]), "usage lines;", len(d["price_book"]["rates"]), "rates")
