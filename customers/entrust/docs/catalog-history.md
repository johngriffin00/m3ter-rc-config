# The Entrust catalog in Revenue Cloud — what was built, and the shapes before it

Moved from `revenue-cloud-config/README.md` (§ "The Entrust Verification catalog" and § "Earlier shapes") on 20 Oct 2026 with the config; paths updated, text otherwise as written. The engine knowledge it refers to (landmines, design decisions, troubleshooting) stays in that README.

## The Entrust Verification catalog (`customers/entrust/revenue-cloud`)

**The Document Check catalog — the console build of 13–14 October 2026,
reproduced.** Run every command with `--config-dir customers/entrust/revenue-cloud`. The files
are **generated** by `customers/entrust/revenue-cloud/build_config.py` — edit the generator and
re-run it; `python3 customers/entrust/revenue-cloud/build_config.py --check` (and
`tests/test_entrust.py`) fails if the files on disk drift from it, or if a
file the generator no longer writes is still there.

**The design.** The Salesforce team's *Entrust Product and Pricing
Requirements* (`customers/entrust/docs/`, 13 Oct): one `Anchor` product with a
*Feature Type* attribute that selects a usage resource, one resource per
feature × region, 0-quantity grants so every check is overage, rate cards per
commitment model, and the commitment as custom quote-line fields rather than
a platform grant. John built it by hand in the org
(`customers/entrust/docs/document-check-console-walkthrough.md`, click by click),
it was read back over SOQL on 14 Oct, and the generator reproduces that build
record for record — names, codes, dates, rates, tiers — so that **`rc-config
verify` against the hand-built org is the proof the tool describes it**, and
`apply` from an empty org rebuilds it.

**What it builds.** ONE Anchor product `Document Check` (`VC-DOC-CHECK`),
Configure During Sale Allowed, Based On the classification `Document Check`
(`PC-DOC-CHECK`) which carries the one attribute *Feature Type*
(`ATTR-DOC-CHECK-FEATURE`, picklist `PL-DOC-CHECK-FEATURE`: Flash (default) /
Boost / Sherlock, **required, not price impacting** — a selector, not a
price); a Term Monthly selling-model option and a single **0.00 USD**
price-book entry (by design: the money is on the rate cards). SIX
Usage-category resources `RES-DOC-CHECK-<FEATURE>-<REGION>` (USA, ANY) in the
`VERIFICATION-CHECK` unit (Type `Custom`) of the `Verification Usage` class,
every one with `UsageDefinitionProductId` = the product; each bound by a
`ProductUsageResource` carrying a `ProductUsageGrant` (Type Grant, **Quantity
0**, `ValidityPeriodUnit None`) and a `ProductUsageResourcePolicy` pointing at
the owned *DC Usage Overage Policy* (Overage Chargeable Yes) and *DC Monthly
Rating Frequency*; one `UsagePrdGrantBindingPolicy` (Self) on the product.
TWO rate cards on the Standard Price Book, each with one Negotiable Term
Monthly USD entry per resource, **keyed on rate card + product + resource**:
*Document Check Rate Card - List (Base)* with the list rate per check, and
*Document Check Rate Card - Commit (Tier)* with no rate and three
`RateAdjustmentByTier` bands per entry (0–10,000 / 10,000–25,000 / 25,000–open,
all `Override`). The *Entrust Catalog* with a *Document Checks* category.
Every effective date is `2026-09-01T19:00:00Z` — what was typed in the
console. Looked up, never owned: the Standard Price Book, Term Monthly, the
pre-seeded USD unit (the unit a rate is *expressed* in).

| Resource (`Code`) | List (USD / check) | Commit tiers 0–10k / 10k–25k / 25k+ |
|---|---|---|
| Document Check - Boost - USA (`RES-DOC-CHECK-BOOST-USA`) | 5.75 | 0.65 / 0.50 / 0.40 |
| Document Check - Boost - ANY (`RES-DOC-CHECK-BOOST-ANY`) | 6.20 | 0.75 / 0.65 / 0.55 |
| Document Check - Flash - USA (`RES-DOC-CHECK-FLASH-USA`) | 2.00 | 1.60 / 1.30 / 1.10 |
| Document Check - Flash - ANY (`RES-DOC-CHECK-FLASH-ANY`) | 2.25 | 1.50 / 1.20 / 1.00 |
| Document Check - Sherlock - USA (`RES-DOC-CHECK-SHERLOCK-USA`) | 6.50 | 0.50 / 0.40 / 0.30 |
| Document Check - Sherlock - ANY (`RES-DOC-CHECK-SHERLOCK-ANY`) | 6.75 | 0.80 / 0.70 / 0.60 |

The tier values are the org's, as built on 14 Oct (the Flash and Sherlock
sets look swapped against the List rates — change the org first, then the
generator, never the other way round). Which card a quote line picks for a
resource is the open experiment; the walkthrough's LOW COMMIT / FULL COMMIT
cards were dropped as adding nothing to that answer.

```
catalog.toml                   api 66.0; the four pricing tables + the THREE tier tables (no attribute adjustments)
01-attributes.json             OWNED picklist + 3 values (Flash IsDefault) + the Feature Type definition          5 owned
02-classifications.json        OWNED classification + its attribute row (required, not price impacting)         2 owned
03-units-of-measure.json       OWNED Verification Usage class (DefaultUnitOfMeasureId forward ref) + the
                               VERIFICATION-CHECK unit (Type Custom); @lookup-only USD unit                    2 owned, 1 looked up
03b-policies.json              OWNED DC Usage Overage Policy (Yes) + DC Monthly Rating Frequency (Monthly)      2 owned
04-usage-resources.json        6 Usage resources, feature x region; UsageDefinitionProductId forward refs      6 owned
05-selling-models.json         @lookup-only Term Monthly                                                        1 looked up
06-products.json               ONE Anchor product, USD, Configure During Sale, Based On the classification      1 owned
06b-catalog.json               OWNED Entrust Catalog; Document Checks category; 1 placement (not primary)       3 owned
07-product-junctions.json      1 selling-model option, 6 product-usage-resource links (IsOptional false)        7 owned
08-grants.json                 6 zero-quantity Grants, 6 policy rows, 1 Self grant binding policy              13 owned
09a-price-book-entries.json    @lookup-only Standard Price Book; 1 USD entry at 0.00 on Term Monthly           1 owned, 1 looked up
09b-list-rate-card.json        OWNED List (Base) card + price-book link; 6 entries with Rate                    8 owned
09c-commit-rate-card.json      OWNED Commit (Tier) card + link; 6 entries without Rate; 18 tiers              26 owned
```

**79 records: 76 owned + 3 looked up.** A clean first `apply` reports
`Created 76, Linked 7, Found (org-owned) 3, Activated 31, Tables refreshed 7`
(Linked = six resource→product references plus the class's default unit;
Activated = the class, 6 resources, 6 links, 6 grants, 12 rate-card entries;
116 writes including the classification attribute's `IsRequired` re-sent
once); the second `Unchanged 76, Found 3` and no refresh; `destroy` reports
`Deactivated 31, Deleted 76, Purged 76`. The tiers are created before any
Commit entry is activated (`test_tiers_go_in_before_the_entry_is_activated`)
because the org refuses a tier on an Active entry. **Proven offline only**
(`tests/test_entrust.py`, 22 tests). **The org holds the same catalog, built
by hand** — `verify` is the next step ("Where we left off").

**Growing it.** A new feature × region is one row in the generator's
`RESOURCES` table — nine records: resource, link, grant, policy row, an entry
on each card, three tiers. `apply` on top reports `Created 9, Unchanged 76,
Linked 1, Activated 5` (`test_a_new_feature_region_is_an_ordinary_change`).
Grant labels are 40 characters at most (the pre-flight catches it).

**Not in the catalog, by their design:** the commitment. *Estimated Usage
Amount*, *Willingness to Commit* and *Commitment Amount* are custom fields on
Quote Line Item and Order Product (walkthrough Step 5) — Setup metadata, not
records, so outside this tool; the formula that fills *Commitment Amount* is
the Salesforce team's open question.

### Earlier shapes (history)

**8 Oct — one Pack product, twelve resources** (`main` up to commit
`f965adb`): `Entrust Identity Verification` (`VC-IDV`), no attribute, twelve
`RES-VC-*` resources from the Alloy quote on *Rate Card D USD Default
Pricing*, 49 records. Proven offline, never applied. **7 Oct — eleven
products, one resource each** (commit `65902ea`): applied and verified in the
org, quoted as ALLOY-2025, torn down 13 Oct; it showed the one-to-one was the
wrong model (every line at 0.00, two identical Boost lines). The m3ter source
for both was the Alloy auto-renewal quote of May 2025 (`models/Entrust quote
reconstruction - First Mile Group Alloy.xlsx`), and the rule it set still
holds: **nothing a quote can show names an m3ter identifier**
(`test_nothing_a_quote_can_show_names_an_m3ter_identifier`). Its rate card,
for reference — the other 22 Rate Card D items and the spend commitment
(round two) come back to it:

| Quote line | Usage resource (`Code`) | Rate Card D (USD) | Alloy plan (USD) | m3ter meter |
|---|---|---|---|---|
| A-01 | Document Check - Boost (USA) (`RES-VC-DOC-BOOST-USA`) | 1.59 | 0.40 | `document_report_standard_hybrid`, country USA |
| A-02 | Document Check - Boost (All other countries) (`RES-VC-DOC-BOOST-ANY`) | 1.59 | 0.68 | `document_report_standard_hybrid`, every other country |
| A-03 | Document Check - Flash (`RES-VC-DOC-FLASH`) | 0.54 | 0.54 | `document_report_standard_auto` |
| A-04 | Document Check - Sherlock (`RES-VC-DOC-SHERLOCK`) | 2.78 | 2.78 | `document_report_standard_manual` |
| A-05 | Facial Similarity Check - Selfie Hybrid (`RES-VC-SELFIE-HYBRID`) | 0.95 | 0.25 | `facial_similarity_report_standard` |
| A-06 | Facial Similarity Check - Selfie Auto (`RES-VC-SELFIE-AUTO`) | 0.77 | 0.25 | `facial_similarity_report_photo_fully_auto` |
| A-07 | Motion PLG (`RES-VC-MOTION-PLG`) | 1.21 | 0.30 | `facial_similarity_report_motion` |
| A-08 | Proof of Address (`RES-VC-PROOF-OF-ADDRESS`) | 2.36 | 1.60 | `proof_of_address_report_standard` |
| A-09 | Facial Similarity Check Upgrade - Known Faces (`RES-VC-KNOWN-FACES`) | 0.00 | 0.12 | `known_faces_report_standard` |
| A-10 | Repeat Attempts (`RES-VC-REPEAT-ATTEMPTS`) | 0.00 | 0.00 | `repeat_attempts_report_standard` |
| A-11 | Device Intelligence - Standard (`RES-VC-DEVICE-INTEL`) | 0.00 | 0.00 | `applicant_fraud_report_standard` |
| A-12 | OCR Autofill (`RES-VC-OCR-AUTOFILL`) | 0.00 | 0.00 | `autofill` |

In the 8 Oct shape all twelve were resources of the one product `VC-IDV`.
The "Alloy plan" column is the negotiated price: it was **not** in the
catalog. It is entered per resource on the one quote line
(`QuoteLineRateCardEntry.NegotiatedRate` through "Manage Usage Resources";
every rate-card entry is `Negotiable`) and reaches rating through the
asset's rate-card entry. Known Faces is the reminder that a negotiated rate
can be *higher* than the list rate.

**Round two, in order of value.** (1) The spend commitment, as a second
product: `CommitmentSpend` product → Currency resource → `Commit` grant
(Quantity 1, 1 Year) → `ProductUsageResourcePolicy` →
`UsageCommitmentPolicy`, the shape that applied cleanly on October 7;
quantity 15,000 at 1.00 on Term Annual; a currency unit with `Scale 2` from
the start (the pre-seeded USD unit has none, and adopting it would make
`destroy` delete a seeded record — create a second currency unit instead, or
decide to never destroy the seeded one). The Alloy quote is then two lines:
the commitment at 15,000 USD and the verification product at 0.00 with its
twelve rates. (2) The other 22 Rate Card D items, one more row each in
`RESOURCES`. (3) The ETSI video checks priced per `is_retry` segment — in the
single-product shape, two resources, like Boost. The archived EUR catalog in
`customers/entrust/revenue-cloud/archive/` has the record shapes for (1).

**The EUR catalog it replaces** is in `customers/entrust/revenue-cloud/archive/` (134 records,
Signicat and Wolt, applied and verified on October 7 and torn down the same
evening — `documents/handoff-2026-10-07b.md`). Keep it for reference; it
must not be applied (its EUR price-book entries and decimal commitment
quantity are exactly what the USD restart removes). What the org taught us
while building it still holds and shaped the USD design:

- `Product2.UsageModelType` offers `Anchor`, `Commit` (Token Commitment),
  `CommitmentQuantity`, `CommitmentSpend` (Monetary Commitment), `Pack`.
- **A spend commitment is not bound to its Pack products in the catalog.**
  The org's own sample, `QB-MTY-CMT`, is a `CommitmentSpend` product →
  `ProductUsageResource` on "USD Resource" (Category `Currency`) →
  `ProductUsageGrant` Type `Commit`, Quantity 5000, UoM USD, 1 Month,
  `ExpiringFirst` → `ProductUsageResourcePolicy` → `UsageCommitmentPolicy`
  ("Lowest Rate"; `CommitmentRate` is `Lowest Commitment Rate` or `Bounded
  Object Rate`). No Anchor, no bundle component, no
  `UsagePrdGrantBindingPolicy`: every grant-binding policy in the org sits
  on an `Anchor` product with `GrantBindingType = Self`. The Pack ↔ balance
  link is made at quote time ("Manage Usage Resources" on the line: Binding
  Type Target / Target Type Product / Scope Quote Line Item) and lands as
  `UsageCmtAssetRelatedObj` when contracted — untested end to end.
- `UsageResourcePolicy` (resource-level) *requires* a commitment policy;
  `ProductUsageResourcePolicy` (product-level, master-detail to the PUR)
  does not. Use the product-level one, like the sample.
- `QuoteLineRateCardEntry` has `NegotiatedRate`, `IsChosenRate`,
  `RateCardEntryId`, `UsageResourceId`, `RateUnitOfMeasureId`;
  `AssetRateCardEntry` and `OrderItemRateCardEntry` are the downstream
  copies. A negotiated usage rate can therefore be proven without rating any
  usage: negotiate it on the line, contract, read the asset entry. A plain
  line-level discount is the wrong lever for a usage line.
- Picklists checked rather than guessed: `Product2.Family` has no
  "Verification" (we use `Services`); `ConfigureDuringSale` is `Allowed` /
  `NotAllowed`; `ProductUsageGrant.Type` is `Grant` / `Commit`;
  `ValidityPeriodUnit` is `Month` / `Year` / `None`; `UnitOfMeasure.Type`
  has `Count` (used for CHECK) as well as `Custom`.
- The country attribute works at quote time: price-impacting + required
  gives a `QuoteLineItemAttribute` row with `IsPriceImpacting true`;
  `IsRequired` on `ProductClassificationAttr` only sticks on update (the
  engine re-sends it).
- Quote line editor defaults: start date today, 1-month term; the end date
  is derived from the line's term, not typed.
- The three walls the WOLT-2026 quote hit, now landmine rows: EUR price-book
  entries the pricing decision table ignores; a quote line only saves against
  an entry in the quote's currency; a decimal quantity is refused unless the
  product's unit carries a `Scale`.

---



## The models and documents (from README § "Project layout")

**The billing data-model diagram.** `customers/entrust/docs/claude-billing-data-model.html`
is the same workbench for the other half of the story: the 29 objects between
an activated order and a posted invoice — billing setup (legal entity,
policy → treatment → item, payment term, tax), order and asset, the wallet
(entitlements and buckets), usage and its summaries, billing schedules, and
invoices. Its numbers are not a load order but the position along that
chain, and a stage strip across the top (1 Setup → 2 Order → 3 Activation →
4 Usage → 5 Invoice) dims everything a stage does not create and explains
it in a sentence. Outlined numbers mark what *you* write (setup records, the
order, usage journals, the liable summary an external biller fills);
filled ones what the platform creates. Each table's detail sheet says who
creates it, how many rows order 00000102 had on 20 Oct 2026, its status
lifecycle, where to find it in the UI, and the gotchas from
`documents/billing-usage-to-invoice.md`. It is **generated**:
`python3 customers/entrust/docs/build_billing_data_model.py` (which writes into `customers/entrust/docs/`) reads
`customers/entrust/docs/billing-fields.json` (every field's name, type, required /
create-only / read-only flag and lookup target, pulled from `EntityParticle`
in the org on 20 Oct 2026 — no field name in it is typed by hand) and the
annotations in the script, and copies the React runtime from the catalog
page. Re-pull the JSON and re-run it when the org changes; edit the
script, never the HTML.

**The documentation set.** `customers/entrust/docs/index.html` wraps the pages
above into one navigable site: a contents pane in John's reading order —
(1) the catalog data model, (2) the Document Check console walkthrough,
(3) Revenue Cloud → m3ter: the m3sh Order Handler, then the Python order
sync, (4) usage into m3ter and the first bill (not yet written), (5) the
billing data model, (6) m3ter → Revenue Cloud Billing: the m3sh Usage Data
workflows, then the bill-sync design. Step 2 has two pages: the console
walkthrough (2.1) and `verification-catalog-setup-guide.html` (2.2), the
same build record by record as `rc-config` describes it — **generated** by
`customers/entrust/docs/build_setup_guide.py`, which embeds `customers/entrust/revenue-cloud/*.json` at build
time so the page cannot drift from the config (the 7 Oct version had drifted:
eleven Pack products and Rate Card D). Re-run it after the generator changes
the config. Each page loads in a reader pane (← → move through the set, every
step has its own `#hash`), stays a self-contained file, and opens on its own
with one click. The overview page carries the loop in one diagram and where
things stand. `bill-sync-design.html` is the twin of `order-sync-design.html`
for the other direction: eight bricks (`ReadBill` … `LinkAndBucket`), the
m3ter → Salesforce mapping tables for `UsageSummary`, `UsageRatableSummary`
and `UsageBillingPeriodItem` with every field name from `models/billing-
fields.json`, and the decisions — it is a design; `demoscripts/billsync`
does not exist yet.

**The m3ter recommendation.** `customers/entrust/analysis/verification-catalog.recommendation.yaml`
is a draft Revenue Cloud catalog derived from two m3ter account exports
(October 6, 2026): one shared Verification Check catalog (33 products, 2
bundles, 2 price books) plus per-account overlays, written in business terms
one level above `config/*.json`, with the decisions and open questions
inline. `customers/entrust/analysis/m3ter-to-revenue-cloud.md` is the rationale and the
object-by-object mapping. On October 6, 2026 the worked example (one
product, the AE bundle, both rate cards, three rate card entries) was
built by hand in m3ter-arm-260 and SOQL-verified Active; the
click-by-click record with screenshots is the Claude Docs manual
"Revenue Cloud Verification Catalog — Setup Manual", and the record ids
are in the YAML's `meta.status`. That build settled D1 (two `Base` rate
cards under the Standard Price Book, no second price book), created the
EUR unit in the Currency class, and found that `UnitOfMeasureClass` is
Draft-only on create and that `UsageResource` categories are Usage /
Token / Currency — all folded back into the YAML and the md. The
remaining 31 products are the input to `customers/entrust/revenue-cloud/`, hand-translated
first. `customers/entrust/analysis/verification-catalog-structure.html` draws that YAML the way
the m3ter structure charts drew the exports — price book → rate cards →
products with their USD/EUR rates → usage resources → units, plus the
catalog tree and the Is Retry attribute, with a green dot on everything
already built in the org; regenerate it with
`python3 customers/entrust/analysis/build_structure_chart.py` after editing the YAML (React and
the fonts it inlines live in `customers/entrust/analysis/structure-chart/`).

**The quoting recommendation (v2).** `customers/entrust/analysis/verification-quoting.recommendation.yaml`
starts from the other end: three real renewal quotes (Signicat, Wolt 2025,
Wolt 2026) reconstructed from m3ter in `customers/entrust/analysis/Entrust quote reconstruction -
Signicat and Wolt.xlsx`, and asks what the catalog must contain for a seller
to build those quotes and for rating to reproduce the January 2026 bills.
It narrows v1 to the 12 metered products on the quotes, replaces Is Retry
with a price-impacting Country attribute (one quote line per country, no
catalog adjustment), switches to the Term Monthly selling model, and adds
the two products v1 had no equivalent for: a `CommitmentSpend` product with
a currency usage resource for the minimum prepayment and its drawdown, and
a one-time customer-success fee. The three quotes are in the YAML as
acceptance fixtures (lines, discounts, net prices, totals) and the two bills
as rating fixtures. Its `verify_in_org` list is the gate before any
`customers/entrust/revenue-cloud/*.json` is written; items 1 and 2 (how a spend commitment
binds to usage, and whether a negotiated line rate reaches rating) decide
the design. Regenerate with `python3 customers/entrust/analysis/build_quoting_recommendation.py`
(needs `openpyxl`). **On October 7, 2026 the gate was passed by describe
and the JSON was written**, then built, verified and torn down the same day
when the EUR quote hit three currency-shaped walls; that catalog is now
`customers/entrust/revenue-cloud/archive/`, and `customers/entrust/revenue-cloud/` is the USD restart from the
Alloy quote — see "The Entrust Verification catalog" below. The answers are
also inline in the YAML's `verify_in_org`.

