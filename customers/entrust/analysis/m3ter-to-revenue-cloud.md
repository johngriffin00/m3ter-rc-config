# m3ter → Revenue Cloud: how the Verification Check catalog maps

Companion to `verification-catalog.recommendation.yaml`. The YAML is the
recommendation; this file is the reasoning, so the YAML stays readable.
Written October 6, 2026 from two m3ter account exports (State of Delaware,
USD; Finrate AG, EUR). Updated the same day after the worked example was
built by hand in m3ter-arm-260 (one product, one bundle, both rate cards,
three rate card entries, all Active); what that build settled is marked
**verified in org** below, and the click-by-click record with screenshots
is the Claude Docs manual "Revenue Cloud Verification Catalog — Setup
Manual".

## The pipeline

```
m3ter export (per account)        what the customer actually has
        │
        ▼
recommendation.yaml               one shared catalog + account overlays,
        │                         in business terms, reviewed by people
        ▼
config/*.json (rc-config)         sObject-level, load-ordered, @ref'd;
        │                         generated from the YAML (by hand first)
        ▼
rc-config apply --org …
```

The middle layer exists because the two ends speak different languages.
m3ter is organised by *what is measured* (meter → aggregation → plan);
rc-config's JSON is organised by *what Salesforce needs inserted in what
order*. Neither is the right place to argue about whether a bundle is a
product. The YAML is.

The YAML is deliberately **not** a mirror of the 25 sObjects in the data
model. One `products[]` entry implies six records (Product2,
ProductSellingModelOption, UsageResource, ProductUsageResource,
PricebookEntry, RateCardEntry) and the `rc_mapping` block at the top says
which. If the YAML ever grows a key per sObject field, it has become the
JSON with different brackets and should be deleted.

## What the m3ter exports contain

Both accounts share one catalog — the `Meters` and `Aggregations` arrays
are byte-identical across the two exports.

| m3ter object | Count | What it is here |
|---|---|---|
| Product | 2 | `verification_check` (the catalog) and `product_bundles` (a container m3ter needs for compound aggregations; billed DAILY, which is an artefact, not a requirement) |
| Meter | 33 | One per check type. `check_count` (MEASURE) plus `sf_opportunity_id` (METADATA) and, on some, WHAT fields: `rejected`, `country`, `is_retry` |
| Aggregation | 33 | 1:1 with meters: `SUM(check_count)`, `quantityPerUnit 1`. Two are segmented on `is_retry` |
| CompoundAggregation | 1 per account | `Math.max(a, b[, c])` — a bundle: bill the larger of the component counts at one price |
| PlanTemplate | 1 per currency | "Rate Card D USD Default Pricing", "Rate Card B EUR Default Pricing": the list price per aggregation, monthly billing, no standing charge, no minimum spend |
| Plan | 1–2 per opportunity | Bespoke per-contract plan off the template; overrides a few aggregations (mostly to 0) |
| Pricing | 35 or 140 on the template, 7 on plans | Always one band, `lowerLimit 0`, `fixedPrice 0`, `DEBIT`, cumulative. **Flat per-unit, no tiers anywhere.** The EUR template carries four dated versions of every rate |
| AccountPlan | 2–4 | Which plan the account was on, with start/end dates |

## The mapping, object by object

| m3ter | Revenue Cloud | Notes |
|---|---|---|
| Meter + its Aggregation | `Product2` (UsageModelType `Pack`) + `UsageResource` + `ProductUsageResource` + `ProductSellingModelOption` (Evergreen monthly) | Same cluster as `P_ClaudeAPIUsage` / `RES_AITokens`. 1:1 because every aggregation is `SUM(check_count)`; if m3ter ever had two aggregations on one meter (e.g. SUM and MAX) that would be two products on one resource |
| Meter unit (`check`, `checks`, `sum`, `blocks`) | `UnitOfMeasure` CHECK, BLOCK under one `UnitOfMeasureClass` | m3ter's units are free text and inconsistent; RC's are records. `sum` on the EMEA Mastercard meter is a typo for `check` |
| `is_retry` WHAT field + segmented aggregation | `AttributePicklist` / `AttributePicklistValue` / `AttributeDefinition`, attached via a second `ProductClassification` | The token rate card's model-tier / token-direction pattern, exactly. No adjustment rules yet — see D2 |
| `rejected`, `country` WHAT fields | Nothing | m3ter captures them but never prices on them. Modelling them would be speculation; add the attribute the day a price depends on it |
| PlanTemplate | `Pricebook2` + `RateCard` + `PriceBookRateCard` | One per template. The template's `billFrequency: MONTHLY` is the selling model's term, not a catalog record |
| Template Pricing (current version) | `RateCardEntry` with `EffectiveFrom`; plus a 0.00 `PricebookEntry` so the product is in the price book | See D1 |
| Template Pricing (older versions) | Not loaded | See D5 |
| CompoundAggregation | A bundle `Product2` with its own `UsageResource` | See D3 — the only mapping that isn't mechanical |
| Plan-level Pricing (overrides) | Not catalog. Quote-line / contract negotiated price | See D4. Recorded under `accounts[]` so the numbers aren't lost |
| AccountPlan dates | Not catalog. Contract / asset start and end | Recorded under `accounts[].contracts[]` |
| `product_bundles` m3ter Product, DAILY | Nothing | Billing-cadence scaffolding for compound aggregations in m3ter |
| `sf_opportunity_id` METADATA | Nothing in PCM | It's how m3ter ties usage to the Salesforce opportunity; the usage ingestion side needs it, the catalog doesn't |

Nothing maps to `ProductUsageGrant` or `UsagePrdGrantBindingPolicy`:
neither account has prepaid, included or committed quantities. Minimum
spend (`minimumSpendDescription`) is present on the template as an empty
string, i.e. unused.

## Decisions (long form)

**D1 — rate cards carry the price.** Usage rating in Revenue Cloud runs
off `RateCardEntry`; it has dated effectivity and attribute adjustments,
`PricebookEntry.UnitPrice` has neither. The Claude catalog already sets
`PBE_ClaudeAPIUsage` to 0 and prices on `RCE_ClaudeAPITokens`.
**Verified in org:** m3ter-arm-260 has only the Standard Price Book and
every pre-seeded rate card hangs off it through `PriceBookRateCard`, with
Type `Base`, a currency unit as `RateUnitOfMeasure` and the resource unit
as `DefaultUnitOfMeasure`. "Rate Card D (USD)" and "Rate Card B (EUR)"
were built the same way: two `RateCard`s, one price book, no second
`Pricebook2`. The YAML's `price_books[]` entries are rate cards; the
`PB-` codes are kept for traceability only.

**D2 — define `IS-RETRY`, price nothing on it.** Both templates charge
`is_retry:true` and `is_retry:false` identically (3.72/3.72 USD,
3.57/3.57 EUR, and the same on the QES+OTP variant). An
`AttributeBasedAdjRule` with a zero adjustment is noise. The attribute
itself costs three records and makes the catalog match m3ter's shape,
so a retry discount later is one rule, not a product change.

**D3 — bundles are products with their own resource.** m3ter's
`Math.max(doc_check, selfie)` at $1.54 has no native equivalent: RC rates
one resource at a time. Three ways to fake it were considered:

1. *Decision tables or Apex that compute the max at rating time.* Rating
   logic in two systems, and the project has already retired one Apex
   workaround.
2. *A configured sales bundle (ProductRelatedComponent) of the two
   products.* Changes what is sold, not what is rated — the components
   would still rate separately.
3. *Grants to absorb component usage.* Grants are prepaid quantities,
   not a max() function.

The recommendation: the metering side already computes the max (that is
what a CompoundAggregation *is*), so it sends one usage record against a
bundle resource (`RES-BUNDLE-AE`) and RC rates that at one price. The
components are rated at 0 under the contract, which is what m3ter does
today anyway (the plan-level overrides). Cost: two more products and two
more resources. Open: the PLG formula names three components but the
plan only zeroes one of them — see `bundles[].anomaly` in the YAML.

**D4 — account overlays are recorded, not built.** Plan-level overrides
(Delaware's Motion at 0.77 against a list of 1.21; everything else at 0
because the bundle absorbs it) and the bundle prices themselves are
contract terms. In Revenue Cloud they live on the quote line or the
contract as negotiated prices, which rc-config doesn't touch. They're in
the YAML so the quote side has exact numbers and so a reviewer can see
the catalog is complete for these two customers.

**D5 — current EUR price version only.** rc-config matches
`RateCardEntry` on `(RateCardId, ProductId)`, so one entry per product
per card. The three older EUR versions (→2022-02, →2023-02, →2025-01-27)
are listed under `history_not_loaded` for the record. Loading them would
mean either `EffectiveFrom` in the match key or one rate card per
version; nothing in RC needs to re-rate 2022 usage, so neither is worth
doing now.

**D6 — names from m3ter, de-duplicated.** `Product2.Name` is
customer-facing and should be unique. Three meters are all named
"Mastercard Identity" (AMER/EMEA/ROW only in the code); "Motion PLG"
names a go-to-market motion; "Document Check Video" sits ambiguously next
to "Document Check Video - Boost". The m3ter meter and aggregation codes
are kept verbatim on every product as the traceable key. `ProductCode`
is `VC-<meter code, upper, hyphenated>` so the two can be joined by eye.

**D7 — free add-ons stay in at 0.** Five items (OCR Autofill, Device
Intelligence, Known Faces, Repeat Attempts, Ongoing Monitoring top-up)
are 0.00 in every list. Keeping them costs one product each; dropping
them leaves their usage unrated and invisible.

## What this catalog does NOT exercise

Worth knowing before assuming the rc-config engine covers it:

- No tiers, no fixed+variable bands, no overage bands (all
  `overagePricingBands: []`), no minimum spend, no standing charge.
  Every rate is a single `unitPrice`.
- No grants, no drawdown, no binding policies.
- No multi-level categories.
- Two currencies, which the Claude catalog never had. **Verified in
  org:** EUR did not exist and was created as a `UnitOfMeasure` in the
  pre-seeded Currency class (Type Custom, the only UI option; USD's is
  Cost); the EUR rate card and entries accepted it.
- Dated price versions, which the Claude catalog never had.

## What the org build taught us (6 October 2026)

- `UnitOfMeasureClass` is Draft-only on create, like `UsageResource`,
  `ProductUsageResource`, `RateCardEntry` and `ProductUsageGrant`; it
  activates only once its default unit exists. rc-config's
  `create_status` override and the activation pass must include it.
- `UsageResource` category values are Usage / Token / Currency; the
  YAML's `Verification` was wrong and is now `Usage`.
- `UnitOfMeasure.Type` offers only `Custom` in the UI.
- `ProductClassificationAttr.IsRequired` saved as false although ticked.
- `EffectiveFrom` is a datetime; the UI pre-fills noon, and a date-only
  value sent by API needs explicit local midnight.
- The REST API refuses the UI session cookie (`INVALID_SESSION_ID`);
  SOQL through the Developer Console was the way to count before creating.

## Next steps, in order

1. Review the YAML's `open_questions` and `bundles[].anomaly` with the
   m3ter owner (PLG bundle two-way or three-way; `IsRequired` on Is Retry).
2. Hand-translate the shared catalog (not the overlays) into
   `config/entrust/`, reusing the lookup-only selling model, the Currency
   class units and the records already in m3ter-arm-260 (ids in the
   manual and the YAML's `meta.status`). Expect ~33×6 + bundles +
   attributes ≈ 230 records.
3. Extend `tests/fake_org.py` for the lessons above (Draft-only
   `UnitOfMeasureClass`, category picklist on `UsageResource`), then
   `rc-config check`, `pytest`, and `plan` against the org. Only then
   consider writing the YAML→JSON compiler; two hand translations are
   enough to know what it has to do.
