# Verification Catalog Build Steps

7 October 2026 · John Griffin

Twelve steps rebuild the Entrust Verification catalog in a Revenue Cloud org: 11 metered check products rated per check on one USD rate card, a Country attribute on Document Check - Boost, and a 12-line quote whose negotiated rates are stored on the quote lines. Create the records in this order; each step lists exactly what to create.

## Before you start

The org must already hold these; the steps look them up by the key shown and never create them.

| What | How to find it | Used by |
| --- | --- | --- |
| Revenue Cloud enabled, with the quote line editor and pricing decision tables | Setup → Revenue Settings | Everything |
| Corporate currency USD | `SELECT IsoCode FROM CurrencyType WHERE IsCorporate = true` | Step 9: entries must be in this currency |
| Standard Price Book, active | `Pricebook2.IsStandard = true` | Steps 9 and 10 |
| Selling model Term Monthly | `ProductSellingModel` where SellingModelType = TermDefined, PricingTerm = 1, PricingTermUnit = Months | Steps 8 and 9 |
| Unit of measure USD in the CURRENCY class | `UnitOfMeasure.UnitCode = 'USD'` | Step 10: the unit a rate is expressed in |
| REST API v66.0 | Pin it in whatever loads the records | Step 8 needs v64+ |

Before creating any object, describe it twice: once for fields required on insert (`createable, not nillable, not defaulted`), once for all createable fields. Describe output is not the whole truth; the notes under each step list the fields that behave differently from what describe says.

## Step 1: Create the attributes

One picklist attribute, Country, with two values. Boost is priced per country; the attribute goes on the quote line so the seller picks the country and gets one line per country. Three objects, in this order.

**AttributePicklist** (1)

| Name | Code | DataType | Status |
| --- | --- | --- | --- |
| Country Values | PL-VC-COUNTRY | Text | Active |

**AttributePicklistValue** (2) — PicklistId = the picklist above

| Name | Code | Value | Sequence | IsDefault | Status |
| --- | --- | --- | --- | --- | --- |
| USA | USA | USA | 1 | false | Active |
| ANY | ANY | ANY | 2 | true | Active |

**AttributeDefinition** (1) — PicklistId = the picklist above

| Name | Label | Code | DeveloperName | DataType | IsActive |
| --- | --- | --- | --- | --- | --- |
| Country | Country | ATTR-VC-COUNTRY | Country | Picklist | true |

Notes: the definition's status field is `IsActive` (boolean), not `Status`. `DeveloperName` is required, and the org changes it to `Country1`, `Country2` if a deleted definition still holds the name (deleted definitions keep it for 15 days and cannot be purged). Accept the suffix; nothing reads it.

## Step 2: Create the classifications

Products inherit attributes from a classification. Plain checks share one with no attributes; Boost is based on a second one that carries Country.

**ProductClassification** (2)

| Name | Code | Status |
| --- | --- | --- |
| Verification Check | PC-VERIFICATION-CHECK | Active |
| Verification Check (country-priced) | PC-VERIFICATION-CHECK-COUNTRY | Active |

**ProductClassificationAttr** (1) — ProductClassificationId = the country-priced classification, AttributeDefinitionId = Country

| Name | Sequence | Status | IsPriceImpacting | IsRequired |
| --- | --- | --- | --- | --- |
| Verification Check (country-priced) / Country | 1 | Active | true | true |

Notes: `IsPriceImpacting` lives on this junction, not on the attribute definition. The org ignores `IsRequired` on insert and keeps it on update, so insert the row, then update it with the same values. Required + price-impacting is what makes the quote line editor demand a country and write the value to the line.

## Step 3: Create the unit of measure class and the CHECK unit

Usage is counted in a unit, and a unit belongs to a class. Create the class first (it can only be inserted Draft), then the unit, then set the class's default unit and activate the class.

**UnitOfMeasureClass** (1)

| Name | Code | Type | Status | DefaultUnitOfMeasureId |
| --- | --- | --- | --- | --- |
| Verification Usage | VERIFICATION-UOM-CLASS | Usage | Draft, then Active | CHECK (set after the unit exists) |

**UnitOfMeasure** (1 to create, 1 to look up)

| Name | UnitCode | Type | Status | UnitOfMeasureClassId | Create? |
| --- | --- | --- | --- | --- | --- |
| Check | CHECK | Count | Active | Verification Usage | Yes |
| USD | USD | Cost | Active | CURRENCY | No, pre-seeded |

Notes: `UnitOfMeasureClass.Type` is the billing category (Usage / Token / Currency); `UnitOfMeasure.Type` is the physical measure (Count / Data / Time / Custom / Cost). The class and its unit point at each other, so to delete them later, blank the class's default unit first. No `Scale` is set because every quote quantity is a whole number; a decimal quantity is refused unless the product's unit has one.

## Step 4: Create the usage resources

One Usage-category resource per product, counted in CHECK. Every row has Category = Usage, DefaultUnitOfMeasureId = CHECK, UnitOfMeasureClassId = Verification Usage, Status = Active (inserted Draft, activated after step 8).

**UsageResource** (11)

| Name | Code | UsageDefinitionProductId (set in step 6) |
| --- | --- | --- |
| Document Check - Boost Checks | RES-VC-DOC-BOOST | VC-DOC-BOOST |
| Document Check - Flash Checks | RES-VC-DOC-FLASH | VC-DOC-FLASH |
| Document Check - Sherlock Checks | RES-VC-DOC-SHERLOCK | VC-DOC-SHERLOCK |
| Facial Similarity Check - Selfie Hybrid Checks | RES-VC-SELFIE-HYBRID | VC-SELFIE-HYBRID |
| Facial Similarity Check - Selfie Auto Checks | RES-VC-SELFIE-AUTO | VC-SELFIE-AUTO |
| Motion PLG Checks | RES-VC-MOTION-PLG | VC-MOTION-PLG |
| Facial Similarity Check Upgrade - Known Faces Checks | RES-VC-KNOWN-FACES | VC-KNOWN-FACES |
| Proof of Address Checks | RES-VC-PROOF-OF-ADDRESS | VC-PROOF-OF-ADDRESS |
| Repeat Attempts Checks | RES-VC-REPEAT-ATTEMPTS | VC-REPEAT-ATTEMPTS |
| Device Intelligence - Standard Checks | RES-VC-DEVICE-INTEL | VC-DEVICE-INTEL |
| OCR Autofill Checks | RES-VC-OCR-AUTOFILL | VC-OCR-AUTOFILL |

Notes: both `DefaultUnitOfMeasureId` and `UnitOfMeasureClassId` are required; the class is not derived from the unit. `UsageDefinitionProductId` is marked optional by describe but rate-card entries fail without it ("no usage product related to the selected usage resource"); the product does not exist yet, so create the resource without it and update it after step 6.

## Step 5: Find the selling model

Nothing to create. Usage lines sell on the pre-seeded Term Monthly model; its term is the billing frequency (monthly), and the 12-month contract term is set on the quote line.

**ProductSellingModel** (look up 1)

| Name | SellingModelType | PricingTerm | PricingTermUnit | Status |
| --- | --- | --- | --- | --- |
| Term Monthly | TermDefined | 1 | Months | Active |

Notes: match on the three fields together; there is no Code and Name is not unique.

## Step 6: Create the products

Eleven metered Pack products. Every row has Family = Services, ProductPurpose = Sell, UsageModelType = Pack, IsActive = true, IsAssetizable = true, CurrencyIsoCode = USD. Then go back to step 4 and set each resource's UsageDefinitionProductId.

**Product2** (11)

| Name | ProductCode | BasedOnId (classification) | ConfigureDuringSale |
| --- | --- | --- | --- |
| Document Check - Boost | VC-DOC-BOOST | Verification Check (country-priced) | Allowed |
| Document Check - Flash | VC-DOC-FLASH | Verification Check | NotAllowed |
| Document Check - Sherlock | VC-DOC-SHERLOCK | Verification Check | NotAllowed |
| Facial Similarity Check - Selfie Hybrid | VC-SELFIE-HYBRID | Verification Check | NotAllowed |
| Facial Similarity Check - Selfie Auto | VC-SELFIE-AUTO | Verification Check | NotAllowed |
| Motion PLG | VC-MOTION-PLG | Verification Check | NotAllowed |
| Facial Similarity Check Upgrade - Known Faces | VC-KNOWN-FACES | Verification Check | NotAllowed |
| Proof of Address | VC-PROOF-OF-ADDRESS | Verification Check | NotAllowed |
| Repeat Attempts | VC-REPEAT-ATTEMPTS | Verification Check | NotAllowed |
| Device Intelligence - Standard | VC-DEVICE-INTEL | Verification Check | NotAllowed |
| OCR Autofill | VC-OCR-AUTOFILL | Verification Check | NotAllowed |

Notes: the classification field is `BasedOnId`. Do not set `Type = Base`: it makes the product a variation parent that cannot be sold directly. `UsageModelType = Pack` is what allows the usage-resource link in step 8. `ProductCode` appears on quote lines, so use commercial names, never a billing system's identifiers.

## Step 7: Create the catalog, categories and placements

The catalog browser on a quote reads these. One catalog, three categories, every product placed once as its primary category.

**ProductCatalog** (1)

| Name | Code | CatalogType |
| --- | --- | --- |
| Verification Catalog | CAT-VERIFICATION | Sales |

**ProductCategory** (3) — CatalogId = Verification Catalog

| Name | Code | SortOrder |
| --- | --- | --- |
| Document Checks | CAT-VC-DOCUMENT-CHECKS | 1 |
| Biometrics | CAT-VC-BIOMETRICS | 2 |
| Identity and Fraud Signals | CAT-VC-IDENTITY-SIGNALS | 3 |

**ProductCategoryProduct** (11) — IsPrimaryCategory = true on every row

| Category | Products |
| --- | --- |
| Document Checks | Boost, Flash, Sherlock |
| Biometrics | Selfie Hybrid, Selfie Auto, Motion PLG, Known Faces |
| Identity and Fraud Signals | Proof of Address, Repeat Attempts, Device Intelligence, OCR Autofill |

Notes: ProductCatalog has no Status field.

## Step 8: Link products to selling models and usage resources

Two junction rows per product: 11 selling-model options and 11 product-usage-resource links. Then activate the lifecycle records in this order: the unit class, the 11 usage resources, the 11 links.

**ProductSellingModelOption** (11) — one per product

| Product2Id | ProductSellingModelId | IsDefault |
| --- | --- | --- |
| each of the 11 products | Term Monthly | true |

**ProductUsageResource** (11) — one per product

| ProductId | UsageResourceId | Status | EffectiveStartDate |
| --- | --- | --- | --- |
| each product | its resource from step 4 | Draft, then Active | 2025-01-01T00:00:00Z |

Notes: the option uses `Product2Id`, the link uses `ProductId`. `EffectiveStartDate` is required on insert and is a datetime, which the standard required-field filter hides. The link is refused unless the product's `UsageModelType` is Pack, Anchor or Commit. Querying ProductUsageResource needs API v64 or later.

## Step 9: Create the price-book entries

A product cannot be added to a quote without a price-book entry, even when its price is on the rate card. One entry per product, all alike.

**PricebookEntry** (11)

| Pricebook2Id | Product2Id | ProductSellingModelId | CurrencyIsoCode | UnitPrice | IsActive | UseStandardPrice |
| --- | --- | --- | --- | --- | --- | --- |
| Standard Price Book | each of the 11 products | Term Monthly | USD | 0.00 | true | false |

Notes: `ProductSellingModelId` is required in a Revenue Cloud org and cannot be changed after insert; an entry without it prices the line but leaves Billing Frequency blank and must be deleted and recreated. Uniqueness is per price book + product + selling model + currency. Entries must be in the corporate currency: the pricing decision table silently ignores any other currency and the product never appears on a quote.

## Step 10: Create the rate card and its entries

One Base rate card linked to the Standard Price Book, with one Negotiable entry per product at the list price. The negotiated price for a customer is entered on the quote line (step 12), not here.

**RateCard** (1)

| Name | Type | EffectiveFrom |
| --- | --- | --- |
| Rate Card D USD Default Pricing | Base | 2025-01-01T00:00:00Z |

**PriceBookRateCard** (1)

| PriceBookId | RateCardId |
| --- | --- |
| Standard Price Book | Rate Card D USD Default Pricing |

**RateCardEntry** (11) — RateCardId = the card, RateUnitOfMeasureId = USD, EffectiveFrom = 2025-01-01T00:00:00Z, RateNegotiation = Negotiable, Status = Draft then Active

| ProductId | UsageResourceId | Rate (USD per check) |
| --- | --- | --- |
| Document Check - Boost | RES-VC-DOC-BOOST | 1.59 |
| Document Check - Flash | RES-VC-DOC-FLASH | 0.54 |
| Document Check - Sherlock | RES-VC-DOC-SHERLOCK | 2.78 |
| Facial Similarity Check - Selfie Hybrid | RES-VC-SELFIE-HYBRID | 0.95 |
| Facial Similarity Check - Selfie Auto | RES-VC-SELFIE-AUTO | 0.77 |
| Motion PLG | RES-VC-MOTION-PLG | 1.21 |
| Facial Similarity Check Upgrade - Known Faces | RES-VC-KNOWN-FACES | 0.00 |
| Proof of Address | RES-VC-PROOF-OF-ADDRESS | 2.36 |
| Repeat Attempts | RES-VC-REPEAT-ATTEMPTS | 0.00 |
| Device Intelligence - Standard | RES-VC-DEVICE-INTEL | 0.00 |
| OCR Autofill | RES-VC-OCR-AUTOFILL | 0.00 |

Notes: RateCard has no Code (match on Name); the link's field is `PriceBookId`, not Pricebook2Id. `RateUnitOfMeasureId` is the unit the rate is expressed in (USD), not the unit being rated. Entries go Draft → Active → Inactive and never back to Draft: to change a rate, delete and recreate the entry. Activate the 11 entries after creating them.

## Step 11: Refresh decision tables and rebuild the product index

Quoting and rating read snapshots, not the records. Nothing from steps 9 and 10 reaches a quote until these run.

| Action | How | When |
| --- | --- | --- |
| Refresh the four pricing decision tables | REST `actions/standard/refreshDecisionTable` with the table's DeveloperName, or the Home page's refresh button | After any change to price-book entries or rate cards |
| Rebuild the product search index | REST `POST connect/pcm/index/deploy` (INCREMENTAL, FULL if refused), or the Home page's Build Catalog Index | After creating or changing products, categories or classifications |

The four tables: `Price_Book_Entry_Decision_Table_v2`, `Pricebook_Rate_Card_Decision_Table`, `Rate_Card_Entries_2`, `Rate_Card_Entry_Resolution_Entries_2`. Check them with `SELECT DeveloperName, RefreshStatus, LastSyncDate, LastIncrementalSyncDate FROM DecisionTable`; a refresh may move only `LastIncrementalSyncDate`. The org allows about 20 refreshes an hour. A quote that shows "No products to show" means one of these two has not run.

## Step 12: Build the quote

Create an Account and an Opportunity (Standard Price Book), then a Quote from the New Quote form: name, opportunity, start date, term months, currency USD. In the quote line editor:

1. Add Product on an empty row, type the product name, press Return, pick it. Chain rows with the row's + and save once.
2. Configure (row action) on each Boost line and pick the Country. The warning triangle on the row disappears when the required attribute is set.
3. Manage Usage Resources (row action), click the resource, then the pencil beside Current Rate; enter the negotiated rate and save. Lines sold at list price need nothing.
4. Select all rows and edit one Start Date cell to set every line. The End Date cannot be typed and the term is not a column: set `SubscriptionTerm` and `EndDate` on the lines through the API, then Reprice All.

The Alloy quote, as built:

| Line | Product | Country | List (USD) | Negotiated (USD) |
| --- | --- | --- | --- | --- |
| 1 | Document Check - Boost | USA | 1.59 | 0.40 |
| 2 | Document Check - Boost | ANY | 1.59 | 0.68 |
| 3 | Document Check - Flash | | 0.54 | at list |
| 4 | Document Check - Sherlock | | 2.78 | at list |
| 5 | Facial Similarity Check - Selfie Hybrid | | 0.95 | 0.25 |
| 6 | Facial Similarity Check - Selfie Auto | | 0.77 | 0.25 |
| 7 | Motion PLG | | 1.21 | 0.30 |
| 8 | Proof of Address | | 2.36 | 1.60 |
| 9 | Facial Similarity Check Upgrade - Known Faces | | 0.00 | 0.12 |
| 10 | Repeat Attempts | | 0.00 | at list |
| 11 | Device Intelligence - Standard | | 0.00 | at list |
| 12 | OCR Autofill | | 0.00 | at list |

Every line: quantity 1, Term Monthly, 2025-05-26 to 2026-05-25, 12-month term. The negotiated rate is stored on `QuoteLineRateCardEntry.NegotiatedRate`; the country on `QuoteLineItemAttribute`. Still to do: Create Contract and read `AssetRateCardEntry` to see the rates on the asset.

## Checks

Run in the Developer Console after the step named. All counts are for this catalog.

| After step | Query | Expect |
| --- | --- | --- |
| 3 | `SELECT Code, Status, DefaultUnitOfMeasure.UnitCode FROM UnitOfMeasureClass WHERE Code = 'VERIFICATION-UOM-CLASS'` | Active, CHECK (after activation in step 8) |
| 6 | `SELECT COUNT() FROM Product2 WHERE ProductCode LIKE 'VC-%'` | 11 |
| 8 | `SELECT Status, COUNT(Id) FROM UsageResource WHERE Code LIKE 'RES-VC-%' GROUP BY Status` | Active 11 |
| 8 | `SELECT COUNT() FROM ProductUsageResource WHERE Product.ProductCode LIKE 'VC-%'` | 11 |
| 9 | `SELECT COUNT() FROM PricebookEntry WHERE Product2.ProductCode LIKE 'VC-%' AND ProductSellingModelId != null` | 11 |
| 10 | `SELECT Status, COUNT(Id) FROM RateCardEntry WHERE RateCard.Name = 'Rate Card D USD Default Pricing' GROUP BY Status` | Active 11 |
| 11 | `SELECT DeveloperName, RefreshStatus, LastSyncDate, LastIncrementalSyncDate FROM DecisionTable` | Completed on the four tables, synced after your changes |
| 12 | `SELECT COUNT() FROM QuoteLineRateCardEntry WHERE QuoteLineItem.QuoteId = '<quote id>'` | 7 |
| 12 | `SELECT AttributeName, AttributeValue, IsPriceImpacting FROM QuoteLineItemAttribute WHERE QuoteLineItem.QuoteId = '<quote id>'` | Country USA true, Country ANY true |

The full write-up, with the object map and every record as applied, is `documents/verification-catalog-setup-guide.html`; the records themselves are generated by `models/build_entrust_config.py` in this repo. The shared, editable copy of this document is the Claude doc "Verification Catalog Build Steps".
