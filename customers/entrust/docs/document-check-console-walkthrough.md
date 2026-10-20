# Document Check Console Walkthrough

13 October 2026 (v2, evening) · John Griffin · shared editable copy: the Claude doc "Document Check Console Walkthrough" · source of the design: `documents/entrust/Entrust Product and Pricing Requirements.pdf` (the Salesforce team's solution notes)

A click-by-click build, in the m3ter-arm-260 org's own UI, of the Entrust Document Check product the way the Salesforce team has designed it: one Anchor product with a Feature Type attribute, one usage resource per feature and region, three rate cards (one per commitment model), the commitment as custom quote-line fields, and a quote → order → asset that carries the rates m3ter will read.

## Before you start

**The design we are matching** (from the requirements notes and their five screenshots, 13 Oct):

| Element | Their build | What it means for this walkthrough |
| --- | --- | --- |
| Product | One **Anchor**, Term **Monthly**, quantity 1, **list price 0.00**, Binding Type *Self* | One product serves all three selling models (confirmed by John); the list price stays 0 by design |
| Feature choice | A product attribute on the configuration screen, *Document Check – Feature Type*: Flash / Boost / Sherlock | A classification with a picklist attribute; it is a **selector for the usage resource**, not price-impacting — all pricing lives on the resource (confirmed) |
| Usage resources | One per **feature × country/region**: *Document Check – Boost – USA*, *Document Check – Sherlock – USA* … (regions A–G later, by custom metadata) | Four to start: Boost / Sherlock / Flash × USA, plus Boost × ANY as the second region; the pattern repeats |
| Grants | Each resource bound to the product with a grant of **0 checks**, Charge Overage *Yes* | All usage is overage, rated from the cards — exactly what `QB-DB` does for Compute Time |
| Rate cards | Named by commitment model: *Document Check – NO COMMIT* is a **Tier** card (Override 0.65 / 0.50 / 0.40 over 0–10k / 10k–25k / 25k+), with a Base entry supplying the *Current Rate* (5.75) | Three cards: LIST (Base), NO COMMIT (Tier), LOW COMMIT (Tier); FULL COMMIT is a flat Base rate. Which card applies per *Willingness to Commit* is **theirs to design later** — this build proves the cards exist and reach the line |
| The money | **Not** a platform Commit grant ("monetary commitments are not supported downstream"): custom fields *Estimated Usage Amount*, *Willingness to Commit* (default 100%), *Commitment Amount* | Step 5 creates the fields; the formula that fills *Commitment Amount* is their open question and out of scope here |
| Downstream | Order Product → *Order Product Rate Card Entries*; Asset → *Asset Rate Card Entries* go to m3ter; subscription/one-time products excluded | Step 7 reads both objects back; it also answers their "Negotiated Rate shows 0" question |
| Unquoted usage | Bind every resource to the product, so the asset carries a default rate for all of them | Confirmed as the intended answer; Step 3 binds all four |

**What changed from the morning's version**: no annual list price on the Anchor, no Commit grant on a USD resource (kept as an appendix), Term Monthly instead of Term Annual, the feature attribute is back, resources are named feature-first their way, and there are three rate cards instead of two.

**Values used throughout** (consistent with their naming; codes are ours — nothing a quote shows carries an m3ter identifier):

| Thing | Value |
| --- | --- |
| Product | Document Check, code `VC-DOC-CHECK`, Family Services, Usage Model Type Anchor, Configure During Sale Allowed |
| Classification / attribute | Classification `Document Check` (`PC-DOC-CHECK`); picklist `Document Check Feature Types` (`PL-DOC-CHECK-FEATURE`) with values Flash / Boost / Sherlock; attribute `Feature Type` (`ATTR-DOC-CHECK-FEATURE`) |
| Selling model | Term Monthly (pre-seeded) |
| List price | 0.00 USD on the Standard Price Book |
| Unit of measure | Class `Verification Usage` (`UOM-CLASS-VERIFICATION-USAGE`), unit `Verification Check` (`VERIFICATION-CHECK`) |
| Usage resources | `Document Check - Boost - USA` (`RES-DOC-CHECK-BOOST-USA`), `Document Check - Sherlock - USA` (`RES-DOC-CHECK-SHERLOCK-USA`), `Document Check - Flash - USA` (`RES-DOC-CHECK-FLASH-USA`), `Document Check - Boost - ANY` (`RES-DOC-CHECK-BOOST-ANY`) |
| Rate cards | `Document Check - LIST` (Base), `Document Check - NO COMMIT` (Tier), `Document Check - LOW COMMIT` (Tier), `Document Check - FULL COMMIT` (Base, flat); all Effective From 1/1/2025 12:00 PM, all on the Standard Price Book |
| Custom fields (Quote Line Item and Order Product) | `Estimated_Usage_Amount__c` Number(16,2), `Willingness_To_Commit__c` Picklist (100% default, 75%, 50%, 25%, 10%, 0%), `Commitment_Amount__c` Currency(16,2) |
| Dates | Effective Start Date 1/1/2025 12:00 PM on every record that asks for one |

**Already in the org, never create again:** the Standard Price Book, the nine selling models, the *Currency* class with the USD unit, the *Default Usage Overage Policy*, the rating-frequency policies. **Still in the org from 7 Oct and worth clearing first** (README § "Where we left off" has the Apex): 11 `RES-VC-*` resources with orphaned product-usage-resource rows and *Rate Card D* with 11 Active entries. They do not collide with the codes above, but they clutter every list.

**Order matters.** Unit class → unit → attribute picklist → attribute → classification → product → resources → bindings, grants, policies → rate cards → entries → tiers → custom fields → decision-table refresh + catalog index → quote. Lifecycle records are created Draft and activated afterwards; an activated rate-card entry never returns to Draft.

**Watching it in SOQL.** Each step ends with a *See what you made* block: paste the queries into Workbench (queries → SOQL Query, tick *Bulk* off) or the Developer Console Query Editor. They select the descriptive fields, not counts, so you can read the record back the way the form showed it. Two habits: `WHERE CreatedDate = TODAY` finds everything you made today on any object, and a `Name` that a form shows (`PUR-000000012`) is not always queryable at the console's API version — the queries below avoid the ones that are refused.

## Step 0 — The unit of measure

The usage resources need a class and a unit. Order and fields matter — learned on 13 Oct when a unit saved on its own could not be activated from the UI.

1. App Launcher → **Unit of Measure Classes** → **New**: Name `Verification Usage`, Code `UOM-CLASS-VERIFICATION-USAGE`, Type **Usage**, Status **Draft** (the only status it accepts on insert), Default Unit Of Measure blank → Save.
2. App Launcher → **Units of Measure** → **New**: Name `Verification Check`, Unit Code `VERIFICATION-CHECK`, Type **Count**, **Unit of Measure Class = Verification Usage**, Status **Active** → Save. The class must be on the unit at creation; a unit saved without one has no status and *Activate* does nothing to it.
3. Back on the class: Default Unit Of Measure = Verification Check, Status **Active** → Save.

If a unit is already stuck without a class, repair it by Apex (Developer Console → Debug → Open Execute Anonymous Window): set `UnitOfMeasureClassId` and `Status = 'Active'` on the unit, `update`, then `Status = 'Active'` on the class, `update`. Two rules for later steps: a rate-card entry's **Rate Unit Of Measure is USD**, never this unit (the form refuses: *"Select a rate unit of measure that's linked to a Token or Currency unit of measure class"*), and the class and unit point at each other, so a teardown blanks the class's default unit before deleting either.

**See what you made (Step 0)**

```sql
SELECT Id, Name, Code, Type, Status, DefaultUnitOfMeasure.UnitCode FROM UnitOfMeasureClass WHERE Code = 'UOM-CLASS-VERIFICATION-USAGE'
SELECT Id, Name, UnitCode, Type, Status, Scale, UnitOfMeasureClass.Code, UnitOfMeasureClass.Status FROM UnitOfMeasure WHERE UnitCode = 'VERIFICATION-CHECK'
```

Expect the class Active with default unit `VERIFICATION-CHECK`, and the unit Active, Type Count, class `UOM-CLASS-VERIFICATION-USAGE` — a unit with a blank class here is the one the UI cannot activate.

## Step 1 — The feature attribute and the product

The product is an Anchor based on a classification that carries one required picklist attribute, *Feature Type*. The rep picks Flash / Boost / Sherlock on the configuration screen; the value is written to the quote line as a `QuoteLineItemAttribute` and selects which usage resource the usage lands on. It does not price anything itself. This is the 7 Oct recipe with the attribute re-keyed from country to feature.

**1a. The picklist and the attribute** (App Launcher → the object name → New):

| Object | Field | Value |
| --- | --- | --- |
| Attribute Picklist | Name / Code / Data Type / Status | `Document Check Feature Types` / `PL-DOC-CHECK-FEATURE` / Text / Active |
| Attribute Picklist Value (×3, from the picklist's Related tab) | Name / Code / Value / Sequence / Status | `Flash` / `FLASH` / `Flash` / 1 / Active; `Boost` / `BOOST` / `Boost` / 2 / Active; `Sherlock` / `SHERLOCK` / `Sherlock` / 3 / Active (no default — the rep must choose) |
| Attribute Definition | Name / Label / Code / Developer Name / Data Type / Picklist / Active | `Feature Type` / `Document Check - Feature Type` / `ATTR-DOC-CHECK-FEATURE` / `Document_Check_Feature_Type` / Picklist / Document Check Feature Types / ticked |

A destroyed attribute definition keeps its Developer Name for 15 days; if the org stores `Document_Check_Feature_Type1`, accept it — nothing reads it (project landmine).

**1b. The classification**: App Launcher → **Product Classifications** → **New**: Name `Document Check`, Code `PC-DOC-CHECK`, Status Active → Save. On its Related tab → **Product Classification Attributes → New**: Attribute Definition *Feature Type*, Sequence 1, Status Active, **Required ticked, Price Impacting unticked** → Save, then open the row and save it once more (the org ignores *Required* on insert and keeps it on update — 7 Oct landmine).

**1c. The product**: App Launcher → **Products** → **New**:

| Field | Value | Why |
| --- | --- | --- |
| Product Name | `Document Check` | Appears on the quote line and the configuration screen |
| Product Code | `VC-DOC-CHECK` | Commercial name only |
| Product Type | blank | `Base` would make it a variation parent that cannot be sold |
| Quantity Unit Of Measure | Each | As `QB-DB` |
| Product Currency | USD - U.S. Dollar | |
| Product Family | Services | |
| Active | ticked | |
| Configure During Sale | **Allowed** | Opens the configuration screen where the attribute is chosen |
| Based On | **Document Check** (the classification) | Inherits the Feature Type attribute |
| Is Assetizable | ticked | |
| Usage Model Type | **Anchor** | Their Product Type on *Manage Usage Resources* is Anchor |

Save, then on the product: **Related List Quick Links → Product Selling Model Option → New**: Product Selling Model **Term Monthly**, Default ticked → Save. Then **Price Books → Add Standard Price**: Active ticked, Product Selling Model **Term Monthly**, List Price `0`, Currency USD → Save. The *Inherited Attributes* quick link should now show *Feature Type*. A price-book entry without a selling model leaves Billing Frequency blank on the quote and cannot be fixed afterwards, so check the row.

Optional: **Categories → New**, a *Document Checks* category in an *Entrust Catalog* (App Launcher → Product Catalogs → New, then Product Categories → New). Without it the product is only reachable on a quote through *Add Product* search, which is enough.

**See what you made (Step 1)**

```sql
-- 1a the picklist, its values, the attribute
SELECT Id, Name, Code, DataType, Status FROM AttributePicklist WHERE Code = 'PL-DOC-CHECK-FEATURE'
SELECT Id, Name, Code, Value, Sequence, IsDefault, Status FROM AttributePicklistValue WHERE Picklist.Code = 'PL-DOC-CHECK-FEATURE' ORDER BY Sequence
SELECT Id, Name, Label, Code, DeveloperName, DataType, IsActive, Picklist.Code FROM AttributeDefinition WHERE Code = 'ATTR-DOC-CHECK-FEATURE'

-- 1b the classification and its attribute row
SELECT Id, Name, Code, Status FROM ProductClassification WHERE Code = 'PC-DOC-CHECK'
SELECT Id, Name, AttributeDefinition.Code, Sequence, Status, IsRequired, IsPriceImpacting FROM ProductClassificationAttr WHERE ProductClassification.Code = 'PC-DOC-CHECK'

-- 1c the product, its selling model, its price-book entry, its catalog placement
SELECT Id, Name, ProductCode, Family, IsActive, IsAssetizable, UsageModelType, ConfigureDuringSale, BasedOn.Code, QuantityUnitOfMeasure FROM Product2 WHERE ProductCode = 'VC-DOC-CHECK'
SELECT Id, Name, ProductSellingModel.Name, ProductSellingModel.SellingModelType, IsDefault, Status FROM ProductSellingModelOption WHERE Product2.ProductCode = 'VC-DOC-CHECK'
SELECT Id, Pricebook2.Name, ProductSellingModel.Name, UnitPrice, CurrencyIsoCode, IsActive, UseStandardPrice FROM PricebookEntry WHERE Product2.ProductCode = 'VC-DOC-CHECK'
SELECT Id, Product.ProductCode, ProductCategory.Name, ProductCategory.Catalog.Name, IsPrimaryCategory FROM ProductCategoryProduct WHERE Product.ProductCode = 'VC-DOC-CHECK'
```

The `DeveloperName` may come back suffixed (`Document_Check_Feature_Type1`) if an earlier attribute with that name was destroyed in the last 15 days; `IsRequired` must read `true` — if it is `false`, re-save the classification-attribute row once more. On the price-book entry, `ProductSellingModel.Name` must not be blank.

## Step 2 — Usage resources, one per feature and region

Their rule: a usage resource for every combination of attributes that prices differently — feature (Flash / Boost / Sherlock) and country or region. Four to start. App Launcher → **Usage Resources** → **New**, same form each time:

| Name | Code | Status | Unit of Measure Class | Default Unit Of Measure | Category | Usage Definition Product |
| --- | --- | --- | --- | --- | --- | --- |
| `Document Check - Boost - USA` | `RES-DOC-CHECK-BOOST-USA` | Draft | Verification Usage | Verification Check | Usage | Document Check |
| `Document Check - Sherlock - USA` | `RES-DOC-CHECK-SHERLOCK-USA` | Draft | Verification Usage | Verification Check | Usage | Document Check |
| `Document Check - Flash - USA` | `RES-DOC-CHECK-FLASH-USA` | Draft | Verification Usage | Verification Check | Usage | Document Check |
| `Document Check - Boost - ANY` | `RES-DOC-CHECK-BOOST-ANY` | Draft | Verification Usage | Verification Check | Usage | Document Check |

Token Resource blank. Save & New between them; then open each and set **Status = Active**. *Usage Definition Product* looks optional and is not: a rate-card entry for the resource is refused without it ("no usage product related to the selected usage resource").

The region mechanism (which countries fall into A–G, and which resource a quote's country selects) is theirs to build with custom metadata; the resource naming above leaves room for it (`- USA`, `- ANY`, later `- REGION-B` …).

**See what you made (Step 2)**

```sql
SELECT Id, Name, Code, Category, Status, UnitOfMeasureClass.Code, DefaultUnitOfMeasure.UnitCode, UsageDefinitionProduct.ProductCode FROM UsageResource WHERE Code LIKE 'RES-DOC-CHECK-%' ORDER BY Code
```

Four rows, all Active, class and unit from Step 0, `UsageDefinitionProduct.ProductCode = VC-DOC-CHECK` on every one — a blank there is what makes the rate-card entry fail in Step 4.

## Step 3 — Bind the resources: product usage resources, 0-quantity grants, policies, binding policy

Four *Product Usage Resource* rows, each with a **Grant of 0 checks** and a policy that charges overage — that is what makes *Manage Usage Resources* show "0 Checks" and an *Applicable Rate* for every resource, as in their screenshot, and what makes the asset carry a default rate for unquoted usage.

1. On the product, **Related List Quick Links → Show All → Product Usage Resources → New**, four times: Status **Active**, Product *Document Check*, Usage Resource = each of the four, Effective Start Date 1/1/2025 12:00 PM, Optional unticked → Save. Note each `PUR-…` number.
2. Open each PUR → Related → **Product Usage Grants → New**:

| Field | Value |
| --- | --- |
| Label | `Document Check - <feature> - <region> grant` |
| Status | Draft, then Active |
| Drawdown Order | Expiring First |
| Product Usage Resource | the PUR |
| Quantity | `0` |
| Unit Of Measure Class | Verification Usage |
| Unit Of Measure | Verification Check |
| Usage Definition Products | Document Check |
| Type | **Grant** |
| Validity Period Term / Unit | blank / **None** (their screenshot shows *Validity Period Unit: None*) |
| Effective Start Date | 1/1/2025, 12:00 PM |

Save, re-open, Status **Active**.

3. Still on each PUR → Related → **Product Usage Resource Policies → New**: Usage Overage Policy **Default Usage Overage Policy** (this is *Charge Overage: Yes* on the quote), Rating Frequency Policy blank (as theirs), the rest blank → Save.
4. App Launcher → **Usage Product Grant Binding Policies** → **New**: Name `Document Check Grant Binding`, Product *Document Check*, Grant Binding Type **Self** → Save. Without it *Manage Usage Resources* shows empty resource tables (project landmine); with it the header shows *Binding Type: Self*, as in their screenshot.
5. Product → **More → Usage Product Validator → Validate**. Expect *"Validation complete! Your product is configured and ready to use."*

**See what you made (Step 3)**

```sql
-- the four bindings (no Name column on this object at the console's API version)
SELECT Id, Product.ProductCode, UsageResource.Code, Status, EffectiveStartDate, IsOptional FROM ProductUsageResource WHERE Product.ProductCode = 'VC-DOC-CHECK' ORDER BY UsageResource.Code

-- the four 0-quantity grants
SELECT Id, Label, Type, Quantity, UnitOfMeasure.UnitCode, UnitOfMeasureClass.Code, ValidityPeriodTerm, ValidityPeriodUnit, DrawdownOrder, Status, ProductUsageResource.UsageResource.Code, UsageDefinitionProduct.ProductCode FROM ProductUsageGrant WHERE ProductUsageResource.Product.ProductCode = 'VC-DOC-CHECK' ORDER BY ProductUsageResource.UsageResource.Code

-- the four policies
SELECT Id, ProductUsageResource.UsageResource.Code, UsageOveragePolicy.Name, RatingFrequencyPolicy.Name, UsageCommitmentPolicy.Name FROM ProductUsageResourcePolicy WHERE ProductUsageResource.Product.ProductCode = 'VC-DOC-CHECK'

-- the binding policy
SELECT Id, Name, Product2.ProductCode, GrantBindingType FROM UsagePrdGrantBindingPolicy WHERE Product2.ProductCode = 'VC-DOC-CHECK'
```

Grants: `Type = Grant`, `Quantity = 0`, `ValidityPeriodUnit = None`, Active. Policies: `Default Usage Overage Policy`, the other two blank. Binding: one row, `Self`. If `IsOptional` is refused at your API version, drop it from the first query.

## Step 4 — Rate cards: LIST, NO COMMIT, LOW COMMIT, FULL COMMIT

Their screenshot of *Manage Usage Resources* shows two things on one resource: a *Current Rate* of 5.75 USD (from a Base entry) and *Tiered Rates* 0.65 / 0.50 / 0.40 (from the *Document Check – NO COMMIT* Tier entry). Build those two cards first and get the quote to show exactly that; then add the other two cards and watch what the quote picks — that is the experiment behind their open question (one product, three selling models).

Do this in the **Rate Management** app (App Launcher → Rate Management): a rate card there has a **Rate Card Entries** tab, and *New* on a Tier card is a two-page wizard — page 1 the entry (no Rate field; Rate Negotiation defaults to Negotiable), **Next** the tiers (Lower Bound, Upper Bound, Adjustment Type, Adjustment Value, **Add Tier**). In the Revenue Cloud app the plain form appears instead and the tiers are added from the entry's Related tab → *Rate Adjustments By Tier → New*. Same records either way.

**4a. `Document Check - LIST` (Base)** — Rate Cards → New: Name, Rate Card Type **Base**, Effective From 1/1/2025 12:00 PM → Save. Then one entry per resource:

| Field | Boost – USA | Sherlock – USA | Flash – USA | Boost – ANY |
| --- | --- | --- | --- | --- |
| Usage Resource | the resource | the resource | the resource | the resource |
| Product | Document Check | Document Check | Document Check | Document Check |
| Product Selling Model | Term Monthly | Term Monthly | Term Monthly | Term Monthly |
| Status | Draft | Draft | Draft | Draft |
| Rate Unit Of Measure | **USD** | USD | USD | USD |
| Rate (USD per check) | `5.75` | `6.50` | `2.00` | `6.25` |
| Rate Negotiation | Negotiable | Negotiable | Negotiable | Negotiable |
| Effective From | 1/1/2025, 12:00 PM | same | same | same |

**4b. `Document Check - NO COMMIT` (Tier)** — Rate Cards → New, Rate Card Type **Tier**. One entry per resource exactly as above but **no Rate**, then the tiers (their numbers for Boost – USA; scale the others):

| Resource | Tier | Lower Bound | Upper Bound | Adjustment Type | Adjustment Value |
| --- | --- | --- | --- | --- | --- |
| Boost – USA | 1 | 0 | 10000 | Override | 0.65 |
| Boost – USA | 2 | 10000 | 25000 | Override | 0.50 |
| Boost – USA | 3 | 25000 | blank | Override | 0.40 |
| Sherlock – USA | 1 / 2 / 3 | 0 / 10000 / 25000 | 10000 / 25000 / blank | Override | 1.60 / 1.30 / 1.10 |
| Flash – USA | 1 / 2 / 3 | 0 / 10000 / 25000 | 10000 / 25000 / blank | Override | 0.45 / 0.35 / 0.30 |
| Boost – ANY | 1 / 2 / 3 | 0 / 10000 / 25000 | 10000 / 25000 / blank | Override | 0.75 / 0.60 / 0.50 |

**4c. Activate and link, then check the quote (Step 6 + 7) before going further.** Open each entry → Status **Active** (LIST first, then NO COMMIT). App Launcher → **Price Book Rate Cards** → New: Standard Price Book + *Document Check - LIST*; again for *Document Check - NO COMMIT*.

**4d. The other two commitment models** — after the quote shows 5.75 with the three tiers:

- `Document Check - LOW COMMIT` (Tier): same entries, steeper graduated tiers (Boost – USA: 0.55 / 0.45 / 0.38).
- `Document Check - FULL COMMIT` (Base): same entries with the flat, most-discounted rate (Boost – USA `0.40`).

Link both to the Standard Price Book, refresh the tables, re-open the quote and record in the README which Base rate and which tier set the line shows. Two Base cards and two Tier cards on one price book for the same product and resource is the situation their *Willingness to Commit* mechanism will have to resolve; today the org's own rule decides, and knowing that rule is the point of 4d.

Rules that held all day: *Rate Unit Of Measure* is the unit the rate is expressed in (USD); a Tier card entry takes no Rate; bounds chain (upper of one = lower of the next, last upper blank); *Override* replaces the base rate for the band, *Percentage 0* keeps it; entries never return to Draft.

**See what you made (Step 4)**

```sql
-- the cards
SELECT Id, Name, Type, EffectiveFrom, EffectiveTo FROM RateCard WHERE Name LIKE 'Document Check - %' ORDER BY Type, Name

-- every entry, with the card it sits on
SELECT Id, Name, RateCard.Name, RateCard.Type, UsageResource.Code, ProductSellingModel.Name, Rate, RateUnitOfMeasure.UnitCode, RateNegotiation, Status, EffectiveFrom FROM RateCardEntry WHERE Product.ProductCode = 'VC-DOC-CHECK' ORDER BY RateCard.Name, UsageResource.Code

-- the tiers, grouped by resource
SELECT Id, Name, RateCardEntry.RateCard.Name, RateCardEntry.UsageResource.Code, LowerBound, UpperBound, AdjustmentType, AdjustmentValue, RateCardEntryStatus FROM RateAdjustmentByTier WHERE RateCardEntry.Product.ProductCode = 'VC-DOC-CHECK' ORDER BY RateCardEntry.RateCard.Name, RateCardEntry.UsageResource.Code, LowerBound

-- the price-book links
SELECT Id, Name, PriceBook.Name, RateCard.Name, RateCard.Type FROM PriceBookRateCard WHERE RateCard.Name LIKE 'Document Check - %'
```

Base entries carry a `Rate`; Tier entries show it blank and their tiers underneath; `RateUnitOfMeasure.UnitCode` is `USD` everywhere; `RateCardEntryStatus` on a tier mirrors its entry. After 4d, the second query is where you watch the four cards side by side.

## Step 5 — The commitment: three custom fields

Their design keeps the money off the platform's commitment objects and in three custom fields on the line, shown on the configuration screen and as line-editor columns: *Estimated Usage Amount* where quantity normally sits, *Commitment Amount* in the summary total, *Willingness to Commit* as a percentage picklist. The formula that fills *Commitment Amount* (estimated usage × the flat rate × willingness) is their open question — the fields are built here, the calculation is not.

**5a. Fields** — Setup → Object Manager → **Quote Line Item** → Fields & Relationships → **New**, three times; then the same three on **Order Product** (`OrderItem`) so the values travel with *Create Order*:

| Label | API Name | Type | Details |
| --- | --- | --- | --- |
| Estimated Usage Amount | `Estimated_Usage_Amount__c` | Number | Length 16, Decimal Places 2 |
| Willingness to Commit | `Willingness_To_Commit__c` | Picklist | Values `100%`, `75%`, `50%`, `25%`, `10%`, `0%`; default `100%`; restrict to values |
| Commitment Amount | `Commitment_Amount__c` | Currency | Length 16, Decimal Places 2 |

Field-level security: visible to System Administrator at least; add to the page layouts when the wizard offers it. The org has no custom fields on Quote Line Item today beyond the `RLM_*` ones Salesforce ships, so there is nothing to collide with.

**5b. Columns in the quote line editor** — the editor's columns are set in **Lightning App Builder on the Quote record page: select the Quote Line Editor component and add the three fields to its column list** (verify the exact property name in the org when you get there; this is the one step of the guide not yet clicked through). Their mockup shows *Estimated Usage Amount* and *Commitment Amount* as columns beside Start Date and List Price. Showing them on the **product configuration screen** (their first mockup) is a configurator customization and stays with their team.

**See what you made (Step 5)** — custom fields are metadata, so the query is against the schema, not a record:

```sql
SELECT EntityDefinition.QualifiedApiName, QualifiedApiName, Label, DataType FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName IN ('QuoteLineItem', 'OrderItem') AND QualifiedApiName LIKE '%__c' ORDER BY EntityDefinition.QualifiedApiName, QualifiedApiName
```

Six rows of yours among the `RLM_*` fields Salesforce ships. (`FieldDefinition` queries need the console's *Use Tooling API* box unticked — it is a standard object here.)

## Step 6 — Refresh the decision tables and the catalog index

Nothing from steps 1–5 reaches a quote until these run.

1. **Revenue Cloud app → Home** → **Click here to Build Catalog Index** (new product + classification + attribute); wait for it to finish.
2. **Refresh Pricing Decision Tables** (Incremental Refresh on) — covers `Price_Book_Entry_Decision_Table_v2`, `Pricebook_Rate_Card_Decision_Table` and the attribute tables.
3. **Setup → Decision Tables**, one at a time: `Rate_Card_Entries_2`, `Rate_Card_Entry_Resolution_Entries_2`, `Rate_Adjustment_by_Tier_Entries_2`, `Rate_Adjustment_by_Tier_Resolution_Decision_Table`, `Tier_based_Rate_Adjustment_by_Rate_Card_Entry_ID`.
4. Check: `SELECT DeveloperName, RefreshStatus, LastSyncDate FROM DecisionTable WHERE DeveloperName LIKE 'Rate_%' OR DeveloperName LIKE 'Price%' OR DeveloperName LIKE 'Tier%'` — all *Completed*, synced after your edits. About 100 refreshes an hour; a refresh with nothing changed moves no timestamp.

**See what happened (Step 6)**

```sql
SELECT DeveloperName, RefreshStatus, LastSyncDate, LastIncrementalSyncDate, RefreshFailureReason FROM DecisionTable WHERE DeveloperName LIKE 'Rate_%' OR DeveloperName LIKE 'Price%' OR DeveloperName LIKE 'Tier%' OR DeveloperName LIKE 'Attribute%' ORDER BY DeveloperName
```

A refresh may move only `LastIncrementalSyncDate`; `RefreshFailureReason` blank is what you want.

## Step 7 — Quote, order, asset: what m3ter will read

1. **Quotes → New**: Quote Name `DOCCHECK-2026`, Opportunity *Alloy - auto-renewal May 2025* (Account `001Ws000066vHLnIAM`), Start Date 1/1/2026, `RLM_TermMonths__c` 12, Currency USD → Save.
2. **Add Product** → `Document Check` → Return → pick it. Because the product is *Configure During Sale: Allowed* with a required attribute, the **configuration screen** opens (or use *Configure* on the row): choose **Feature Type = Boost**, quantity 1 → Save & Exit. Expect on the line: Product Selling Model *Term Monthly*, List Price *0.00*, the warning triangle gone once the attribute is set.
3. Row action → **Manage Usage Resources**. Expect the header *Product Type Anchor · PSM Term Monthly · Quantity 1 · List Price USD 0.00 · Binding Type Self* and four resources, each *0 Checks* with an *Applicable Rate* — Boost – USA **5.75 USD** with a tiers icon. Click it → **Rates**: *Current Rate 5.75 USD*, *Tiered Rates* Tier 1–3 Override 0.65 / 0.50 / 0.40, *Charge Overage Yes*. That is their screenshot, reproduced.
4. Negotiate one: pencil beside *Current Rate*, enter `0.60`, save. Now read back: `SELECT UsageResource.Code, RateCard.Name, NegotiatedRate, IsChosenRate FROM QuoteLineRateCardEntry WHERE QuoteLineItem.Quote.Name = 'DOCCHECK-2026'`. **This answers their "Negotiated Rate shows 0" question**: `NegotiatedRate` is populated only on the resource whose *Current Rate* the rep edited; every other row carries no negotiated rate and the price is the linked `RateCardEntry.Rate` plus its `RateAdjustmentByTier` rows. An integration must read both (7 Oct proved the same on the Alloy quote: seven negotiated, five blank).
5. **Create Order** (quote header action → Create Single Order → Finish), open the order → **Activate**. Then read the handoff objects: `SELECT RateCardEntry.Name, NegotiatedRate, RateUnitOfMeasure.UnitCode FROM OrderItemRateCardEntry WHERE OrderItem.Order.OrderNumber = '<n>'` and, on the asset the activation creates, `SELECT RateCardEntry.Name, NegotiatedRate FROM AssetRateCardEntry WHERE Asset.Product2.ProductCode = 'VC-DOC-CHECK'` plus `SELECT LowerBound, UpperBound, AdjustmentType, AdjustmentValue FROM AssetRateAdjustment` — the tier copies on the asset. Those four rows per resource are what goes to m3ter.
6. ~~Record what 4d showed once LOW COMMIT and FULL COMMIT exist.~~ **Answered on 14 Oct with the two cards that exist (List Base + Commit Tier), order 00000102:** the line carries one `QuoteLineRateCardEntry` per resource *per card* — 12 rows for 6 resources — `IsChosenRate` false on all of them; all 12 reach `OrderItemRateCardEntry` and `AssetRateCardEntry`, the Tier entries with their three `AssetRateAdjustment` bands each. Salesforce picks neither card. `NegotiatedRate` is populated on the List rows (John negotiated all six, one of them to 0) and blank on the Tier rows. Card selection by *Willingness to Commit* is therefore the reader's decision (or one card per price book), not the catalog's. LOW COMMIT and FULL COMMIT were never built — this result makes them moot.

**Why this matches the three issues of the morning.** One product, resources for every combination (issue 1); the money is *Commitment Amount* on the line and the rates on the cards — the 0.00 list price is by design, not a defect (issue 2, re-answered); two lines for two countries are told apart by the attribute on the line and the resource under it (issue 3).

**See what you made (Step 7)**

```sql
-- the quote and its one line
SELECT Id, Name, Status, Account.Name, Opportunity.Name, StartDate, RLM_TermMonths__c, CurrencyIsoCode FROM Quote WHERE Name = 'DOCCHECK-2026'
SELECT Id, Product2.ProductCode, Quantity, UnitPrice, ProductSellingModel.Name, StartDate, EndDate, SubscriptionTerm, PricingTermCount FROM QuoteLineItem WHERE Quote.Name = 'DOCCHECK-2026'

-- the attribute the rep chose, and the rate entries copied to the line
SELECT AttributeName, AttributeValue, IsPriceImpacting FROM QuoteLineItemAttribute WHERE QuoteLineItem.Quote.Name = 'DOCCHECK-2026'
SELECT Id, Name, UsageResource.Code, RateCard.Name, RateCardEntry.Name, NegotiatedRate, IsChosenRate, RateUnitOfMeasure.UnitCode FROM QuoteLineRateCardEntry WHERE QuoteLineItem.Quote.Name = 'DOCCHECK-2026' ORDER BY UsageResource.Code, RateCard.Name

-- after Create Order: the order, its line, its rate entries (what m3ter reads first)
SELECT Id, OrderNumber, Status, Quote.Name, EffectiveDate FROM Order WHERE Quote.Name = 'DOCCHECK-2026'
SELECT Id, Product2.ProductCode, Quantity, UnitPrice, ServiceDate, EndDate FROM OrderItem WHERE Order.Quote.Name = 'DOCCHECK-2026'
SELECT Id, Name, RateCardEntry.Name, RateCardEntry.RateCard.Name, RateCardEntry.UsageResource.Code, NegotiatedRate, RateUnitOfMeasure.UnitCode FROM OrderItemRateCardEntry WHERE OrderItem.Order.Quote.Name = 'DOCCHECK-2026'

-- after Activate: the asset and its rate entries + tier copies (what m3ter reads for the contract)
SELECT Id, Name, Product2.ProductCode, Account.Name, Status, CreatedDate FROM Asset WHERE Product2.ProductCode = 'VC-DOC-CHECK'
SELECT Id, Name, RateCardEntry.Name, RateCardEntry.RateCard.Name, RateCardEntry.UsageResource.Code, NegotiatedRate FROM AssetRateCardEntry WHERE Asset.Product2.ProductCode = 'VC-DOC-CHECK'
SELECT Id, Name, LowerBound, UpperBound, AdjustmentType, AdjustmentValue FROM AssetRateAdjustment WHERE CreatedDate = TODAY

-- everything else the activation generated (the records the teardown has to unwind)
SELECT Id, Name, Status FROM BillingSchedule WHERE CreatedDate = TODAY
SELECT Id, Name FROM BillingScheduleGroup WHERE CreatedDate = TODAY
SELECT Id, Name FROM UsageEntitlementAccount WHERE CreatedDate = TODAY
SELECT Id, Name, ParentId, UsageResource.Code FROM UsageEntitlementBucket WHERE CreatedDate = TODAY
SELECT Id, Name FROM TransactionUsageEntitlement WHERE CreatedDate = TODAY
SELECT Id, Name FROM BindingObjUsageRsrcPlcy WHERE CreatedDate = TODAY
SELECT Id, Name, StageName, Account.Name FROM Opportunity WHERE CreatedDate = TODAY
```

`NegotiatedRate` is blank on every row except the resource whose *Current Rate* you edited — that is the answer to the "shows 0" question, in data. `BillingSchedule` has no `Name` at some API versions; if refused, select `Id, Status, UsageResourceId` instead.

## Checks

Developer Console → Query Editor. Read a `COUNT()` from the *Total Rows* header — an empty grid is not zero.

| After | Query | Expect |
| --- | --- | --- |
| 0 | `SELECT UnitCode, Status, UnitOfMeasureClass.Code, UnitOfMeasureClass.Status FROM UnitOfMeasure WHERE UnitCode = 'VERIFICATION-CHECK'` | Active · UOM-CLASS-VERIFICATION-USAGE · Active |
| 1a | `SELECT Code, DeveloperName, IsActive, Picklist.Code FROM AttributeDefinition WHERE Code = 'ATTR-DOC-CHECK-FEATURE'` | 1 row, active, PL-DOC-CHECK-FEATURE |
| 1b | `SELECT IsRequired, IsPriceImpacting, Status FROM ProductClassificationAttr WHERE ProductClassification.Code = 'PC-DOC-CHECK'` | true · false · Active |
| 1c | `SELECT ProductCode, UsageModelType, ConfigureDuringSale, BasedOn.Code FROM Product2 WHERE ProductCode = 'VC-DOC-CHECK'` | Anchor · Allowed · PC-DOC-CHECK |
| 1c | `SELECT ProductSellingModel.Name, UnitPrice, IsActive FROM PricebookEntry WHERE Product2.ProductCode = 'VC-DOC-CHECK'` | Term Monthly · 0 · true |
| 2 | `SELECT Code, Status, UsageDefinitionProduct.ProductCode FROM UsageResource WHERE Code LIKE 'RES-DOC-CHECK-%'` | 4 rows, Active, VC-DOC-CHECK |
| 3 | `SELECT UsageResource.Code, Status FROM ProductUsageResource WHERE Product.ProductCode = 'VC-DOC-CHECK'` | 4 rows, Active |
| 3 | `SELECT ProductUsageResource.UsageResource.Code, Type, Quantity, ValidityPeriodUnit, Status FROM ProductUsageGrant WHERE ProductUsageResource.Product.ProductCode = 'VC-DOC-CHECK'` | 4 rows, Grant · 0 · None · Active |
| 3 | `SELECT ProductUsageResource.UsageResource.Code, UsageOveragePolicy.Name FROM ProductUsageResourcePolicy WHERE ProductUsageResource.Product.ProductCode = 'VC-DOC-CHECK'` | 4 rows, Default Usage Overage Policy |
| 3 | `SELECT Product2.ProductCode, GrantBindingType FROM UsagePrdGrantBindingPolicy WHERE Product2.ProductCode = 'VC-DOC-CHECK'` | 1 row, Self |
| 4 | `SELECT RateCard.Name, RateCard.Type, UsageResource.Code, Rate, Status FROM RateCardEntry WHERE Product.ProductCode = 'VC-DOC-CHECK' ORDER BY RateCard.Name` | LIST 4 rows with rates; NO COMMIT 4 rows, Rate blank; all Active |
| 4 | `SELECT RateCardEntry.RateCard.Name, RateCardEntry.UsageResource.Code, LowerBound, UpperBound, AdjustmentValue FROM RateAdjustmentByTier WHERE RateCardEntry.Product.ProductCode = 'VC-DOC-CHECK' ORDER BY RateCardEntry.UsageResource.Code, LowerBound` | 12 rows (3 per resource) |
| 4 | `SELECT PriceBook.Name, RateCard.Name FROM PriceBookRateCard WHERE RateCard.Name LIKE 'Document Check - %'` | 2 rows (4 after 4d), Standard Price Book |
| 5 | `SELECT QualifiedApiName, DataType FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName = 'QuoteLineItem' AND QualifiedApiName LIKE '%Commit%'` | Willingness_To_Commit__c, Commitment_Amount__c |
| 7 | `SELECT AttributeName, AttributeValue FROM QuoteLineItemAttribute WHERE QuoteLineItem.Quote.Name = 'DOCCHECK-2026'` | Feature Type · Boost |
| 7 | `SELECT UsageResource.Code, NegotiatedRate FROM QuoteLineRateCardEntry WHERE QuoteLineItem.Quote.Name = 'DOCCHECK-2026'` | one row per resource per card; NegotiatedRate only on the edited one |

Relationship names that worked in this org: `Product2` on the binding policy, `ProductUsageResource.Product` on grants and policies, `RateCardEntry.Product` on tiers, `Picklist` on the attribute definition; `Product` on the binding policy and `Name` on a grant are refused.

## Tearing it down

Done once already on 13 Oct, 17:38, for the morning build. `rc-config destroy` cannot do this: nothing here is owned by a config, and an **activated order** leaves six kinds of record that block the catalog and have their own rules. The proven script is `scripts/teardown-after-assetization.apex` in the repo — anonymous Apex, one transaction, so a refused line changes nothing and names the next dependant. For this build change its `EDIT` lines to the new codes (`VC-DOC-CHECK`, `RES-DOC-CHECK-%`, `Document Check - %` cards, `PC-DOC-CHECK`, `PL-DOC-CHECK-FEATURE`, `ATTR-DOC-CHECK-FEATURE`) and add the attribute objects after the products: `ProductClassificationAttr` → `ProductClassification` → `AttributeDefinition` → `AttributePicklistValue` → `AttributePicklist`. The custom fields stay (Setup metadata, harmless).

| Record | Rule learned | What to do |
| --- | --- | --- |
| Billing Schedule (one per order item, points at the usage resource) | No `delete()` at all; `UsageResourceId` is read-only | Delete its **Billing Schedule Group** — the schedules cascade |
| Usage Entitlement Bucket | A tree via `ParentId`; parents refuse before children | Delete leaves first, in a loop |
| Usage Entitlement Entry, Transaction Usage Entitlement, Usage Entitlement Account, Binding Object Usage Resource Policy (`BindingObjUsageRsrcPlcy`) | Each blocks the asset, named one at a time | Delete in that order |
| Asset | Blocked by all of the above; its own rate entries and tiers cascade | Delete after them |
| Order, Activated | Cannot be deleted | Status back to Draft, then delete (items cascade) |
| Quote, Renewal Forecast Opportunity | The opportunity is auto-created and holds the price-book entries | Delete both before the price-book entries |

Then the catalog in reverse: rate-card entries Active → Inactive → delete (tiers cascade), price-book rate cards, rate cards, price-book entries, selling-model options, resource policies, grants, product usage resources (Active → Inactive), usage resources (Active → Inactive), category products, category, catalog, products, attribute objects, and last the unit class (default unit blanked, Inactive) and the unit. Probe a doubtful delete first: `Database.setSavepoint()` … `Database.rollback(sp)` … `System.assert(false, msg)`.

## Back to rc-config

This is the shape `models/build_entrust_config.py` should generate next. Against the current `main` config (one Pack product, twelve resources, one Base card):

| Element | Change to the generator |
| --- | --- |
| Product | `UsageModelType` Pack → **Anchor**; `ConfigureDuringSale` Allowed; `BasedOnId` → the classification; Term Monthly stays; `UnitPrice` 0.00 stays |
| Attribute | `01-attributes.json` and `02-classifications.json` return, keyed on Feature Type (Flash / Boost / Sherlock), `IsPriceImpacting` false, `IsRequired` true — the `ORG_MAY_SUFFIX` landmine applies again |
| Resources | Feature × region naming (`RES-DOC-CHECK-<FEATURE>-<REGION>`); the generator's rows gain a region column |
| Bindings | Per resource: `ProductUsageResource` + `ProductUsageGrant` (Type Grant, Quantity 0, `ValidityPeriodUnit` None) + `ProductUsageResourcePolicy` (overage policy, lookup-only) + one `UsagePrdGrantBindingPolicy` Self — the grant file from `config/claude/08-grants.json` is the template |
| Rate cards | Four cards: `09b` becomes LIST (Base), new `09c-no-commit-tiers.json` and `09d-low-commit-tiers.json` (Type Tier, entries without `Rate`, `RateAdjustmentByTier` rows), `09e-full-commit.json` (Base, flat); the simulated org needs `RateAdjustmentByTier` and a rule for which Base/Tier card a quote picks, learned in 4d |
| Commitment | No commitment records; the three custom fields are Setup metadata, outside the tool (a `metadata/` note in the README is enough) |

Settle 4d (card selection) and the Negotiated Rate read-back before touching the generator; record both in README § "Where we left off". Teardown first with the script, then the usual order: `check` → `plan` → `apply` → `apply` → `verify`.

## Appendix — The platform's own commitment (not in their design)

The morning version put a `Commit` grant of 15,000 USD on the Anchor's USD resource with the *Lowest Rate* policy and a 1-year validity — the shape of the org's `QB-MTY-CMT` sample. Their design does not use it ("monetary commitments are not supported downstream"), so it is out of the main path. It remains the one untested question from the morning: whether an Anchor accepts a `Commit` grant at all. If there is a spare hour, add a PUR on the pre-seeded *USD Resource* with a Commit grant and run the Usage Product Validator; whatever it says, write it in the README.
