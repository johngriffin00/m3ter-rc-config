#!/usr/bin/env python3
"""Generate the Entrust Document Check catalog (customers/entrust/revenue-cloud) from one table of features.

    python3 customers/entrust/revenue-cloud/build_config.py            # writes the *.json + catalog.toml beside it
    python3 customers/entrust/revenue-cloud/build_config.py --check    # exit 1 if the files on disk differ

Design (14 October 2026 — the Document Check console build). This is the shape John built
by hand in the m3ter-arm-260 org on 13–14 Oct, following the Salesforce team's "Entrust
Product and Pricing Requirements" (`customers/entrust/docs/`), and read back record by record
over SOQL on 14 Oct. The generator reproduces that build exactly — names, codes, dates,
rates and tiers — so that `rc-config verify --config-dir customers/entrust/revenue-cloud` against the
hand-built org is the proof that the tool describes what the console made. The reasoning
is in README § "The Entrust Verification catalog"; the click-by-click is
`customers/entrust/docs/document-check-console-walkthrough.md`.

* ONE sellable product, `Document Check` (`VC-DOC-CHECK`): an `Anchor` on Term Monthly with
  a 0.00 USD price-book entry (the money is on the rate cards, not the line), `Configure
  During Sale` Allowed, based on the classification `Document Check` (`PC-DOC-CHECK`).
* ONE attribute, *Feature Type* (Flash / Boost / Sherlock), required and NOT price
  impacting: the rep picks it on the configuration screen and it selects which usage
  resource the usage lands on. Nothing about it prices anything.
* SIX usage resources, one per feature x region (USA, ANY), counted in the
  `VERIFICATION-CHECK` unit of the `Verification Usage` class, every one defined by the
  product (`UsageDefinitionProductId` — a rate-card entry is refused without it).
* Each resource is bound to the product by a `ProductUsageResource` carrying a 0-quantity
  `Grant` (all usage is overage) and a policy row pointing at John's two policies — *DC
  Usage Overage Policy* (Overage Chargeable Yes) and *DC Monthly Rating Frequency* — plus
  one `UsagePrdGrantBindingPolicy` of type Self on the product (without it *Manage Usage
  Resources* shows empty tables).
* TWO rate cards on the Standard Price Book, both with one Negotiable Term Monthly entry per
  resource: *List (Base)* carries the list rate per check; *Commit (Tier)* carries no rate
  and three `RateAdjustmentByTier` rows per entry (0–10k, 10k–25k, 25k–open, all Override).
  The LOW COMMIT and FULL COMMIT cards of the walkthrough were dropped on 14 Oct: List +
  Commit is enough to see what the quote picks.
* The commitment is NOT catalog data (their design: custom quote-line fields, outside this
  tool). No spend-commitment product.
* The org's pre-seed is looked up, never owned: the Standard Price Book, the Term Monthly
  selling model and the USD unit (the unit a rate is EXPRESSED in). Everything else here,
  the two policies included, is owned — `apply` builds it from an empty org and `destroy`
  removes it.

Values that look odd on purpose, because they are what the org holds (14 Oct 2026):
the effective dates are 1 Sep 2026 20:00 Dublin (`2026-09-01T19:00:00Z`), not 1 Jan 2025;
the unit's Type is `Custom` (the form would not take `Count`); the Flash picklist value is
the default; the Commit tiers for Flash and Sherlock are in the opposite order to the
List rates (Flash lists at 2.00 with tiers from 1.60, Sherlock at 6.50 with tiers from
0.50). Change them in the org first, then here — not the other way round, or `verify`
reports drift that is really a decision.

NOTHING THAT CAN APPEAR ON A QUOTE NAMES AN m3ter IDENTIFIER (decided 7 Oct). Names are the
commercial names; codes come from those names.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]          # m3ter-rc-config
OUT = HERE                      # the generator lives beside what it writes

EFFECTIVE = "2026-09-01T19:00:00Z"      # what John typed into every date field on 13 Oct (1 Sep 2026, 20:00 Dublin)
CURRENCY = "USD"

PRODUCT_KEY = "DocCheck"
PRODUCT_NAME = "Document Check"
PRODUCT_CODE = "VC-DOC-CHECK"

LIST_CARD = "Document Check Rate Card - List (Base)"
COMMIT_CARD = "Document Check Rate Card - Commit (Tier)"
TIER_BOUNDS = [(0, 10000), (10000, 25000), (25000, None)]     # lower, upper; the last is open

FEATURES = [("Flash", "FLASH"), ("Boost", "BOOST"), ("Sherlock", "SHERLOCK")]   # picklist order
REGIONS = ["USA", "ANY"]

# One row per usage resource (feature x region), in the order the org created them. `list_rate`
# is the Base entry's Rate on the List card; `tiers` are the three Override values of the Commit
# card's entry, in bound order. All USD per check.
#   key — @id suffix; code is RES-DOC-CHECK-<FEATURE>-<REGION>
RESOURCES = [
    # key,            feature,    region, list_rate, tiers
    ("BoostUSA",      "Boost",    "USA",  5.75, (0.65, 0.50, 0.40)),
    ("SherlockUSA",   "Sherlock", "USA",  6.50, (0.50, 0.40, 0.30)),
    ("FlashUSA",      "Flash",    "USA",  2.00, (1.60, 1.30, 1.10)),
    ("BoostANY",      "Boost",    "ANY",  6.20, (0.75, 0.65, 0.55)),
    ("SherlockANY",   "Sherlock", "ANY",  6.75, (0.80, 0.70, 0.60)),
    ("FlashANY",      "Flash",    "ANY",  2.25, (1.50, 1.20, 1.00)),
]


def resource_name(feature: str, region: str) -> str:
    return f"{PRODUCT_NAME} - {feature} - {region}"


def resource_code(feature: str, region: str) -> str:
    return f"RES-DOC-CHECK-{feature.upper()}-{region}"


def block(sobject: str, match_fields: list[str], records: list[dict], comment: str | None = None) -> dict:
    b: dict = {"sobject": sobject, "match_fields": match_fields, "records": records}
    if comment:
        b["_comment"] = comment
    return b


def build() -> dict[str, dict]:
    files: dict[str, dict] = {}
    product_ref = f"@ref:P_{PRODUCT_KEY}"

    # 01 — the feature attribute ---------------------------------------------------------
    files["01-attributes.json"] = {
        "_comment": "The Feature Type attribute (Flash / Boost / Sherlock). It is a SELECTOR, not a price: "
                    "the rep picks it on the configuration screen, it lands on the quote line as a "
                    "QuoteLineItemAttribute, and it says which usage resource the usage goes to. All pricing "
                    "lives on the resources' rate-card entries. Flash is the picklist default because that is "
                    "what the org holds (14 Oct); clear IsDefault in the org and here together if a rep must "
                    "choose. A destroyed AttributeDefinition keeps its DeveloperName for 15 days: the org may "
                    "store Document_Check_Feature_Type1 on a rebuild, and the engine accepts the suffix "
                    "(README landmine).",
        "objects": [
            block("AttributePicklist", ["Code"], [{
                "@id": "PL_Feature", "Name": "Document Check Feature Types", "Code": "PL-DOC-CHECK-FEATURE",
                "DataType": "Text", "Status": "Active",
            }]),
            block("AttributePicklistValue", ["Code", "PicklistId"], [{
                "@id": f"PLV_{code.title()}", "Name": name, "Code": code, "Value": name, "Sequence": i + 1,
                "IsDefault": i == 0, "Status": "Active", "PicklistId": "@ref:PL_Feature",
            } for i, (name, code) in enumerate(FEATURES)]),
            block("AttributeDefinition", ["Code"], [{
                "@id": "ATTR_Feature", "Name": "Feature Type", "Label": "Document Check - Feature Type",
                "Code": "ATTR-DOC-CHECK-FEATURE", "DeveloperName": "Document_Check_Feature_Type",
                "DataType": "Picklist", "PicklistId": "@ref:PL_Feature", "IsActive": True,
            }]),
        ],
    }

    # 02 — the classification --------------------------------------------------------------
    files["02-classifications.json"] = {
        "_comment": "One classification carrying the one attribute: required (the rep must pick a feature) and "
                    "NOT price impacting (the feature selects a resource; the resource's rate card prices it). "
                    "The org ignores IsRequired on insert and keeps it on update — the engine re-sends it "
                    "(README landmine). No Sequence: the console build left it blank.",
        "objects": [
            block("ProductClassification", ["Code"], [{
                "@id": "PC_DocCheck", "Name": PRODUCT_NAME, "Code": "PC-DOC-CHECK", "Status": "Active",
            }]),
            block("ProductClassificationAttr", ["ProductClassificationId", "AttributeDefinitionId"], [{
                "@id": "PCA_Feature", "Name": "Feature Type", "ProductClassificationId": "@ref:PC_DocCheck",
                "AttributeDefinitionId": "@ref:ATTR_Feature", "Status": "Active",
                "IsRequired": True, "IsPriceImpacting": False,
            }]),
        ],
    }

    # 03 — units of measure --------------------------------------------------------------
    files["03-units-of-measure.json"] = {
        "_comment": "The Verification Usage class and its VERIFICATION-CHECK unit are OWNED. The class is "
                    "inserted Draft and activated once the unit exists (lifecycle object); "
                    "DefaultUnitOfMeasureId is a forward reference, filled in after the unit is created, and "
                    "destroy blanks it again before deleting the pair (README landmine: neither can be "
                    "deleted while they point at each other). The unit's Type is Custom because the console "
                    "form would not take Count (13 Oct). The USD unit (pre-seeded, Currency class) is only "
                    "looked up: it is what RateCardEntry.RateUnitOfMeasureId points at — the form refuses "
                    "the check unit there ('linked to a Token or Currency unit of measure class').",
        "objects": [
            block("UnitOfMeasureClass", ["Code"], [{
                "@id": "UOMCLASS_Verification", "Code": "UOM-CLASS-VERIFICATION-USAGE", "Name": "Verification Usage",
                "Type": "Usage", "Status": "Active", "DefaultUnitOfMeasureId": "@ref:UOM_Check",
            }]),
            block("UnitOfMeasure", ["UnitCode"], [
                {"@id": "UOM_Check", "UnitCode": "VERIFICATION-CHECK", "Name": "Verification Check",
                 "Type": "Custom", "Status": "Active", "UnitOfMeasureClassId": "@ref:UOMCLASS_Verification"},
                {"@id": "UOM_USD", "@lookup-only": True, "UnitCode": "USD"},
            ]),
        ],
    }

    # 03b — the two policies ----------------------------------------------------------------
    files["03b-policies.json"] = {
        "_comment": "John's two policies (13 Oct), OWNED so that apply builds them in an empty org: the overage "
                    "policy is what 'Charge Overage: Yes' means on the quote (every check is overage on a 0 "
                    "grant), the rating-frequency policy rates monthly, the same as Term Monthly bills. "
                    "The org's own 'Default Usage Overage Policy' would do the same job; these are matched "
                    "on Name. No lifecycle, no Status on either object.",
        "objects": [
            block("UsageOveragePolicy", ["Name"], [{
                "@id": "UOP_DocCheck", "Name": "DC Usage Overage Policy", "OverageChargeable": "Yes",
            }]),
            block("RatingFrequencyPolicy", ["Name"], [{
                "@id": "RFP_DocCheck", "Name": "DC Monthly Rating Frequency", "RatingPeriod": "Monthly",
            }]),
        ],
    }

    # 04 — usage resources ---------------------------------------------------------------
    files["04-usage-resources.json"] = {
        "_comment": "Six Usage-category resources, one per feature x region, all counted in VERIFICATION-CHECK "
                    "and all defined by the one product: every UsageDefinitionProductId points FORWARD at the "
                    "product in 06 and rc-config fills it in once the product exists. It looks optional and "
                    "is not — a rate-card entry for the resource is refused without it ('no usage product "
                    "related to the selected usage resource'). The resource is named feature-first, the "
                    "Salesforce team's way; the region mechanism (which countries fall into which region) is "
                    "theirs, by custom metadata, and the naming leaves room for it (- USA, - ANY, later "
                    "- REGION-B ...).",
        "objects": [
            block("UsageResource", ["Code"], [{
                "@id": f"RES_{key}", "Name": resource_name(feature, region), "Code": resource_code(feature, region),
                "Category": "Usage", "Status": "Active",
                "DefaultUnitOfMeasureId": "@ref:UOM_Check", "UnitOfMeasureClassId": "@ref:UOMCLASS_Verification",
                "UsageDefinitionProductId": product_ref,
            } for key, feature, region, *_ in RESOURCES]),
        ],
    }

    # 05 — selling models ----------------------------------------------------------------
    files["05-selling-models.json"] = {
        "_comment": "Pre-seeded and Active in the org. The product sells on Term Monthly: the selling model's "
                    "term is the BILLING frequency (monthly); the contract term is set on the quote line.",
        "objects": [
            block("ProductSellingModel", ["SellingModelType", "PricingTerm", "PricingTermUnit"], [{
                "@id": "PSM_TermMonthly", "@lookup-only": True,
                "SellingModelType": "TermDefined", "PricingTerm": 1, "PricingTermUnit": "Months",
            }]),
        ],
    }

    # 06 — the product -------------------------------------------------------------------
    files["06-products.json"] = {
        "_comment": "ONE Anchor product in USD, based on the Document Check classification so it inherits the "
                    "Feature Type attribute, with Configure During Sale Allowed so the configuration screen "
                    "opens on the quote. Anchor (not Pack) is what the Salesforce team's Manage Usage "
                    "Resources screenshot shows, and the grant binding policy in 08 attaches to Anchor "
                    "products only. Product Type is left unset: Base would make it a variation parent that "
                    "cannot be sold. The product code is derived from the commercial name.",
        "objects": [block("Product2", ["ProductCode"], [{
            "@id": f"P_{PRODUCT_KEY}", "Name": PRODUCT_NAME, "ProductCode": PRODUCT_CODE,
            "Family": "Services", "UsageModelType": "Anchor", "QuantityUnitOfMeasure": "Each",
            "IsActive": True, "IsAssetizable": True, "CurrencyIsoCode": CURRENCY,
            "ConfigureDuringSale": "Allowed", "BasedOnId": "@ref:PC_DocCheck",
        }])],
    }

    # 06b — catalog --------------------------------------------------------------------------
    files["06b-catalog.json"] = {
        "_comment": "The Entrust Catalog and its Document Checks category are OWNED. Without a placement the "
                    "product is only reachable on a quote through Add Product search — enough, but the "
                    "catalog browser is nicer. The placement is not the primary category (as built).",
        "objects": [
            block("ProductCatalog", ["Code"], [{
                "@id": "CAT_Entrust", "Name": "Entrust Catalog", "Code": "CAT-ENTRUST", "CatalogType": "Sales",
            }]),
            block("ProductCategory", ["Code"], [{
                "@id": "CAT_DocChecks", "CatalogId": "@ref:CAT_Entrust", "Name": "Document Checks",
                "Code": "DOC-CHECKS",
            }]),
            block("ProductCategoryProduct", ["ProductCategoryId", "ProductId"], [{
                "ProductCategoryId": "@ref:CAT_DocChecks", "ProductId": product_ref, "IsPrimaryCategory": False,
            }]),
        ],
    }

    # 07 — product junctions -------------------------------------------------------------------
    files["07-product-junctions.json"] = {
        "_comment": "The product's Term Monthly selling-model option and its six product-to-resource links — "
                    "the junction where one product provides access to many resources. A link needs the "
                    "product's UsageModelType and an EffectiveStartDate (README landmines). The date is the "
                    "one typed in the console, 1 Sep 2026 20:00 Dublin: a quote line that starts before it "
                    "is the open question of 14 Oct (John's quote starts 1 Oct 2026).",
        "objects": [
            block("ProductSellingModelOption", ["Product2Id", "ProductSellingModelId"], [{
                "@id": f"PSMO_{PRODUCT_KEY}", "Product2Id": product_ref,
                "ProductSellingModelId": "@ref:PSM_TermMonthly", "IsDefault": True,
            }]),
            block("ProductUsageResource", ["ProductId", "UsageResourceId"], [{
                "@id": f"PUR_{key}", "ProductId": product_ref, "UsageResourceId": f"@ref:RES_{key}",
                "Status": "Active", "EffectiveStartDate": EFFECTIVE, "IsOptional": False,
            } for key, *_ in RESOURCES]),
        ],
    }

    # 08 — grants, policies, binding -----------------------------------------------------------
    files["08-grants.json"] = {
        "_comment": "Per resource: a 0-quantity Grant (every check is overage, rated from the cards — exactly "
                    "what QB-DB does for Compute Time) with no validity period, and a policy row pointing at "
                    "the overage and rating-frequency policies in 03b. One grant binding policy of type Self "
                    "on the product: without it Manage Usage Resources shows empty resource tables (README "
                    "landmine); with it the header shows Binding Type Self, as in the Salesforce team's "
                    "screenshot. Grants are lifecycle records (Draft -> Active); the policy rows and the "
                    "binding policy have no status.",
        "objects": [
            block("ProductUsageGrant", ["ProductUsageResourceId", "Type"], [{
                "@id": f"PUG_{key}", "Label": f"{resource_name(feature, region)} - Grant",
                "ProductUsageResourceId": f"@ref:PUR_{key}", "UsageDefinitionProductId": product_ref,
                "UnitOfMeasureId": "@ref:UOM_Check", "UnitOfMeasureClassId": "@ref:UOMCLASS_Verification",
                "Type": "Grant", "Status": "Active", "Quantity": 0, "ValidityPeriodUnit": "None",
                "DrawdownOrder": "ExpiringFirst", "EffectiveStartDate": EFFECTIVE,
            } for key, feature, region, *_ in RESOURCES]),
            block("ProductUsageResourcePolicy", ["ProductUsageResourceId"], [{
                "@id": f"PURP_{key}", "ProductUsageResourceId": f"@ref:PUR_{key}",
                "UsageOveragePolicyId": "@ref:UOP_DocCheck", "RatingFrequencyPolicyId": "@ref:RFP_DocCheck",
            } for key, *_ in RESOURCES]),
            block("UsagePrdGrantBindingPolicy", ["Product2Id"], [{
                "@id": f"UPGBP_{PRODUCT_KEY}", "Name": "Document Check Grant Binding",
                "Product2Id": product_ref, "GrantBindingType": "Self",
            }]),
        ],
    }

    # 09a — the price-book entry ---------------------------------------------------------------------
    files["09a-price-book-entries.json"] = {
        "_comment": "The product needs a PricebookEntry to be quotable, carrying ProductSellingModelId (README "
                    "landmine: without it Billing Frequency is blank on the line and the field is create-only). "
                    "It is 0.00 BY DESIGN: a metered product's price is its rate-card entries, rated after "
                    "consumption; the commitment is custom quote-line fields in their design, not a price. "
                    "USD ONLY: the pricing decision table serves rows in the corporate currency and nothing "
                    "else (7 Oct 2026).",
        "objects": [
            block("Pricebook2", ["IsStandard"], [{"@id": "PB_Standard", "@lookup-only": True, "IsStandard": True}]),
            block("PricebookEntry", ["Pricebook2Id", "Product2Id", "ProductSellingModelId", "CurrencyIsoCode"], [{
                "@id": f"PBE_{PRODUCT_KEY}", "Pricebook2Id": "@ref:PB_Standard", "Product2Id": product_ref,
                "ProductSellingModelId": "@ref:PSM_TermMonthly", "CurrencyIsoCode": CURRENCY,
                "UnitPrice": 0.0, "IsActive": True, "UseStandardPrice": False,
            }]),
        ],
    }

    def entry(card_ref: str, prefix: str, key: str, rate: float | None) -> dict:
        rec = {
            "@id": f"{prefix}_{key}", "RateCardId": card_ref, "ProductId": product_ref,
            "UsageResourceId": f"@ref:RES_{key}", "ProductSellingModelId": "@ref:PSM_TermMonthly",
            "RateUnitOfMeasureId": "@ref:UOM_USD", "EffectiveFrom": EFFECTIVE,
            "RateNegotiation": "Negotiable", "Status": "Active",
        }
        if rate is not None:
            rec["Rate"] = rate
        return rec

    # 09b — the List card ---------------------------------------------------------------------------
    files["09b-list-rate-card.json"] = {
        "_comment": f"{LIST_CARD} — Type Base, under the Standard Price Book — is OWNED, with its price-book "
                    "link and one entry per usage resource at the list rate per check. Entries are keyed on "
                    "rate card + product + resource (with one product the product alone identifies nothing) "
                    "and carry the Term Monthly selling model, as the console build does. Every entry is "
                    "Negotiable: a negotiated rate reaches rating through QuoteLineRateCardEntry.NegotiatedRate "
                    "on the quote line, one per resource. RateUnitOfMeasureId is the unit the rate is "
                    "EXPRESSED in (USD). Rate-card entries are a one-way lifecycle (Draft -> Active <-> "
                    "Inactive) and take no edits after Draft: a rate change is a rebuild.",
        "objects": [
            block("RateCard", ["Name"], [{
                "@id": "RC_List", "Name": LIST_CARD, "Type": "Base", "EffectiveFrom": EFFECTIVE,
            }]),
            block("PriceBookRateCard", ["PriceBookId", "RateCardId"], [{
                "@id": "PBRC_List", "PriceBookId": "@ref:PB_Standard", "RateCardId": "@ref:RC_List",
            }]),
            block("RateCardEntry", ["RateCardId", "ProductId", "UsageResourceId"], [
                entry("@ref:RC_List", "RCE_List", key, rate) for key, _f, _r, rate, _t in RESOURCES]),
        ],
    }

    # 09c — the Commit card -------------------------------------------------------------------------
    tiers = []
    for key, _feature, _region, _rate, values in RESOURCES:
        for (low, high), value in zip(TIER_BOUNDS, values):
            rec = {"@id": f"RAT_{key}_{low}", "RateCardEntryId": f"@ref:RCE_Commit_{key}", "LowerBound": low,
                   "AdjustmentType": "Override", "AdjustmentValue": value}
            if high is not None:
                rec["UpperBound"] = high
            tiers.append(rec)
    files["09c-commit-rate-card.json"] = {
        "_comment": f"{COMMIT_CARD} — Type Tier, under the Standard Price Book — is OWNED, with its price-book "
                    "link, one entry per resource (NO Rate: a Tier card entry takes none) and three "
                    "RateAdjustmentByTier rows per entry: 0–10,000, 10,000–25,000 and 25,000–open checks, each "
                    "an Override of the rate for that band. Bounds chain (the upper of one is the lower of "
                    "the next; the last upper is blank) and the tiers must be in before the entry is "
                    "activated: the org refuses a tier on an Active entry, as it does an attribute "
                    "adjustment. The engine loads the tiers first and activates the entry last. Which of "
                    "the two cards a quote line picks for a resource is the experiment of 14 Oct "
                    "(README § Where we left off).",
        "objects": [
            block("RateCard", ["Name"], [{
                "@id": "RC_Commit", "Name": COMMIT_CARD, "Type": "Tier", "EffectiveFrom": EFFECTIVE,
            }]),
            block("PriceBookRateCard", ["PriceBookId", "RateCardId"], [{
                "@id": "PBRC_Commit", "PriceBookId": "@ref:PB_Standard", "RateCardId": "@ref:RC_Commit",
            }]),
            block("RateCardEntry", ["RateCardId", "ProductId", "UsageResourceId"], [
                entry("@ref:RC_Commit", "RCE_Commit", key, None) for key, *_ in RESOURCES]),
            block("RateAdjustmentByTier", ["RateCardEntryId", "LowerBound"], tiers),
        ],
    }
    return files


CATALOG_TOML = """# Settings for the Entrust Document Check catalog (customers/entrust/revenue-cloud). The numbered JSON
# files beside this one hold the records; this file holds what isn't a record.
# GENERATED by build_config.py beside this file — edit the generator, not these files.

[catalog]
name = "Entrust Document Check"

# Same pin as the Claude catalog: ProductUsageGrant.OverageChargeable is exposed at
# v66.0 and gone at newer versions.
api_version = "66.0"

[decision_tables]
# The four pricing tables plus the three tier tables (the Commit card is a Tier card).
# The attribute tables are not needed: the Feature Type attribute is not price impacting
# and there is no attribute-based rate adjustment.
refresh = [
    "Price_Book_Entry_Decision_Table_v2",
    "Pricebook_Rate_Card_Decision_Table",
    "Rate_Card_Entries_2",
    "Rate_Card_Entry_Resolution_Entries_2",
    "Rate_Adjustment_by_Tier_Entries_2",
    "Rate_Adjustment_by_Tier_Resolution_Decision_Table",
    "Tier_based_Rate_Adjustment_by_Rate_Card_Entry_ID",
]
timeout_seconds = 300
"""

GENERATED = "GENERATED by build_config.py beside this file from the 14 Oct console build — edit the generator, not this file. "


def render(files: dict[str, dict]) -> dict[str, str]:
    out = {}
    for name, doc in files.items():
        doc = {"_comment": GENERATED + doc["_comment"], **{k: v for k, v in doc.items() if k != "_comment"}}
        out[name] = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    out["catalog.toml"] = CATALOG_TOML
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="compare with the files on disk; exit 1 on any difference")
    ap.add_argument("--out", type=Path, default=OUT, help=f"target directory (default {OUT.relative_to(REPO)})")
    args = ap.parse_args()

    files = build()
    rendered = render(files)
    records = [r for doc in files.values() for b in doc["objects"] for r in b["records"]]
    owned = sum(1 for r in records if not r.get("@lookup-only"))
    looked_up = len(records) - owned

    if args.check:
        bad = [n for n, text in rendered.items() if not (args.out / n).exists() or (args.out / n).read_text() != text]
        stale = [p.name for p in args.out.glob("*") if p.is_file() and p.suffix != ".py" and p.name not in rendered]
        if bad or stale:
            if bad:
                print("out of date:", ", ".join(bad))
            if stale:
                print("not generated, still on disk (delete them):", ", ".join(stale))
            return 1
        print(f"{OUT.relative_to(REPO)} is up to date ({owned} owned, {looked_up} looked up).")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    stale = [p.name for p in args.out.glob("*") if p.is_file() and p.suffix != ".py" and p.name not in rendered]
    for name, text in rendered.items():
        (args.out / name).write_text(text)
    print(f"wrote {len(rendered)} files to {args.out} ({owned} owned, {looked_up} looked up)")
    if stale:
        print("NOT written, still on disk and NOT generated (delete them):", ", ".join(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
