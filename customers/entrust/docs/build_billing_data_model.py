#!/usr/bin/env python3
"""Build customers/entrust/docs/claude-billing-data-model.html — the interactive data model of
Revenue Cloud *Billing*: what order activation creates, where usage goes, and how
a bill comes out.  A sibling of claude-catalog-data-model.html (same page code,
same look); the semantics change from *load order* to *lifecycle stage*.

Inputs
  billing-fields.json (beside this script)   field metadata pulled from the org (EntityParticle,
                                   v68.0, 20 Oct 2026) — never hand-edit a field name
  claude-catalog-data-model.html (beside this script)   the React 18 runtime is copied from here
  this file                        the annotations: purpose, stage, who creates each
                                   object, row counts for order 00000102, UI paths,
                                   gotchas, which fields are "key"

Run from the repo root:  python3 customers/entrust/docs/build_billing_data_model.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]          # m3ter-rc-config
FIELDS = json.loads((HERE / "billing-fields.json").read_text())
TEMPLATE = (HERE / "claude-catalog-data-model.html").read_text()
OUT = HERE / "claude-billing-data-model.html"

SNAPSHOT = "20 Oct 2026"
ORDER = "00000102"

# ----------------------------------------------------------------------------- the model

DOMAINS = [
    {"id": "setup",    "label": "Billing setup"},
    {"id": "order",    "label": "Order & asset"},
    {"id": "wallet",   "label": "Entitlements (wallet)"},
    {"id": "usage",    "label": "Usage & summaries"},
    {"id": "schedule", "label": "Billing schedules"},
    {"id": "invoice",  "label": "Invoices"},
]

STAGES = [
    {"n": 1, "id": "setup", "label": "Setup",
     "blurb": "Before any order. A legal entity, a billing policy → treatment → treatment item (advance or "
              "arrears), a payment term, and a tax policy → treatment → engine. VC-DOC-CHECK names none of "
              "them, so the org defaults in Billing Settings apply."},
    {"n": 2, "id": "order", "label": "Order",
     "blurb": "A quote becomes an order with one line: VC-DOC-CHECK × 1, 1,000 USD, Term Monthly, 14 Oct–13 Nov. "
              "With Billing on, activation needs a Bill To Contact, a billing address and a shipping address."},
    {"n": 3, "id": "activation", "label": "Activation",
     "blurb": "Two record-triggered flows fire. Order to Asset: the asset, six TransactionUsageEntitlements, the "
              "UsageEntitlementAccount (the wallet) and twelve buckets. Order to Billing Schedule: seven groups and "
              "seven schedules — one for the flat line, six for the usage resources, all ReadyForInvoicing."},
    {"n": 4, "id": "usage", "label": "Usage",
     "blurb": "TransactionJournal → UsageSummary → UsageRatableSummary → UsageBillingPeriodItem (the liable "
              "summary), driven by the scheduled Orchestrate Usage Management flow and two DPE jobs. The invoice "
              "run reads only the liable summary, so a biller that has already rated the usage (m3ter) can write "
              "that record directly."},
    {"n": 5, "id": "invoice", "label": "Invoice",
     "blurb": "Generate Invoices (Account or Order) or an Invoice Batch Run picks ReadyForInvoicing schedules — "
              "usage ones only when a ReadyForInvoicing liable summary matches the bucket and resource — and "
              "writes Invoice, InvoiceLine and BillingPeriodItem. A draft changes nothing upstream; posting "
              "advances the schedule and marks the liable summary Invoiced."},
]

COLUMNS = [
    ["LegalEntity", "TaxEngine", "TaxPolicy", "TaxTreatment", "PaymentTerm", "PaymentTermItem"],
    ["BillingPolicy", "BillingTreatment", "BillingTreatmentItem", "BillingBatchScheduler"],
    ["Order", "OrderItem", "Asset"],
    ["TransactionUsageEntitlement", "UsageEntitlementAccount", "UsageEntitlementBucket", "UsageEntitlementEntry"],
    ["TransactionJournal", "UsageSummary", "UsageRatableSummary", "UsageBillingPeriodItem"],
    ["BillingScheduleGroup", "BillingSchedule", "BsgRelationship"],
    ["InvoiceBatchRun", "Invoice", "InvoiceLine", "BillingPeriodItem", "RevenueTransactionErrorLog"],
]

# Lookup fields that may point at several objects: which one the main chain uses.
PRIMARY = {
    "OrderItem.BindingInstanceTargetId": "Asset",
    "BillingSchedule.ReferenceEntityId": "Order",
    "BillingSchedule.ReferenceEntityItemId": "OrderItem",
    "InvoiceLine.ReferenceEntityItemId": "OrderItem",
    "InvoiceLine.GroupReferenceEntityItemId": "OrderItem",
    "Invoice.ReferenceEntityId": "Order",
    "TransactionJournal.ReferenceRecordId": "Asset",
    "UsageEntitlementBucket.ParentId": "UsageEntitlementAccount",
}
# Relationships the docs call master-detail where the flags alone would say lookup.
MASTER_DETAIL = {
    "UsageEntitlementEntry.EntitlementBucketId",
    "BillingTreatmentItem.BillingTreatmentId",
    "PaymentTermItem.PaymentTermId",
    "OrderItem.OrderId",
    "InvoiceLine.InvoiceId",
    "BillingSchedule.BillingScheduleGroupId",
    "BillingPeriodItem.BillingScheduleId",
    "InvoiceBatchRun.BillingBatchSchedulerId",
    "BsgRelationship.MainBsgId",
    "BsgRelationship.AssociatedBsgId",
}

# One entry per object.  key = fields shown by default (the ones that matter to the chain).
# samples = values read from the org on the snapshot day.  notes = per-field gotchas.
O = []

def obj(id, domain, stage, seq, purpose, by, records, records_note="", anchor=False, status=None,
        ui="", notes=(), key=(), samples=None, fnotes=None):
    O.append(dict(id=id, domain=domain, stage=stage, seq=seq, purpose=purpose, by=by, records=records,
                  recordsNote=records_note, anchor=anchor, status=status, ui=ui, notes=list(notes),
                  key=list(key), samples=samples or {}, fnotes=fnotes or {}))

# ---- stage 1: setup ----------------------------------------------------------------------
obj("LegalEntity", "setup", 1, 1,
    "The selling company on the invoice. Also the key that picks a billing treatment when a policy selects by legal entity.",
    "Billing admin (pre-seeded in this org)", 2, "Default Legal Entity - US and - Canada, both Active, company QuantumBit",
    anchor=True, ui="App Launcher → Legal Entities",
    notes=["The org default legal entity is a Billing Settings choice, not a field on this object — SOQL has no IsDefault here (20 Oct 2026).",
           "Every group for order 00000102 resolved to Default Legal Entity - US."],
    key=["Id", "Name", "CompanyName", "Status", "LegalEntityCountry"],
    samples={"Name": ["Default Legal Entity - US", "Default Legal Entity - Canada"], "CompanyName": ["QuantumBit"], "Status": ["Active"]})

obj("TaxEngine", "setup", 1, 2,
    "The tax calculator a tax treatment hands invoice lines to. Here a mock adapter that returns 10% on drafts.",
    "Billing admin (pre-seeded)", 1, "RLM_MockTaxAdapter, Active", anchor=True,
    ui="App Launcher → Tax Engines",
    notes=["Invoice DOC-000000001 carries 100 USD of estimated tax on 1,000 — the mock's flat 10%. Real engines (Avalara, Vertex) plug in through TaxEngineProvider."],
    key=["Id", "TaxEngineName", "Status", "TaxEngineProviderId", "Type"],
    samples={"TaxEngineName": ["RLM_MockTaxAdapter"], "Status": ["Active"]})

obj("TaxPolicy", "setup", 1, 3,
    "Groups tax treatments; a product points at one through Product2.TaxPolicyId. VC-DOC-CHECK has none, so the org default is used.",
    "Billing admin (pre-seeded)", 1, "Default Tax Policy, Active", anchor=True,
    ui="App Launcher → Tax Policies",
    key=["Id", "Name", "Status", "TreatmentSelection", "DefaultTaxTreatmentId"],
    samples={"Name": ["Default Tax Policy"], "Status": ["Active"]})

obj("TaxTreatment", "setup", 1, 4,
    "The tax parameters a schedule and its invoice lines inherit: taxable or not, tax code, engine, legal entity.",
    "Billing admin (pre-seeded)", 1, "Default Tax Policy (treatment), taxable, code PA020111, US legal entity", anchor=True,
    ui="App Launcher → Tax Treatments",
    notes=["All seven schedules of order 00000102 carry this one treatment (BillingSchedule.TaxTreatmentId = 1ttWs000002qN4DIAU)."],
    key=["Id", "Name", "Status", "TaxPolicyId", "TaxEngineId", "LegalEntityId", "IsTaxable", "TaxCode"],
    samples={"Name": ["Default Tax Policy"], "TaxCode": ["PA020111"], "IsTaxable": ["true"]})

obj("PaymentTerm", "setup", 1, 5,
    "When an invoice is due. The org default is stamped on every billing schedule group and invoice.",
    "Billing admin (pre-seeded)", 2, "Default Payment Term (Net 30, IsDefault) and Net 45", anchor=True,
    ui="App Launcher → Payment Terms",
    key=["Id", "Name", "Status", "IsDefault"],
    samples={"Name": ["Default Payment Term", "Net 45"], "IsDefault": ["true", "false"]})

obj("PaymentTermItem", "setup", 1, 6,
    "The rule inside a payment term: period-based (Net N days) or end-of-month plus N.",
    "Billing admin (pre-seeded)", 2, "30 days and 45 days, both Period-Based", anchor=True,
    ui="Payment Term record → Payment Term Items",
    key=["Id", "Name", "PaymentTermId", "Type", "Period", "PeriodUnit"],
    samples={"Type": ["Period-Based"], "Period": ["30", "45"], "PeriodUnit": ["Days"]})

obj("BillingPolicy", "setup", 1, 7,
    "A named set of billing treatments. Product2.BillingPolicyId chooses one per product; with none, the org default treatment applies.",
    "Billing admin (pre-seeded)", 3, "Billing Policy - Advance, Billing Policy - Arrears (both select by legal entity), Milestone Billing Policy - Software", anchor=True,
    status="Draft → Active ⇄ Inactive. Activating needs a default treatment; a treatment that is the default of an active policy cannot be deactivated.",
    ui="App Launcher → Billing Policies",
    notes=["VC-DOC-CHECK has no BillingPolicyId, so order 00000102 fell through to the org default treatment — which is the Advance one. The Arrears policy exists and is the natural fit for usage; setting it on the product is an open decision (README, 20 Oct)."],
    key=["Id", "Name", "Status", "BillingTreatmentSelection", "DefaultBillingTreatmentId"],
    samples={"Name": ["Billing Policy - Advance", "Billing Policy - Arrears", "Milestone Billing Policy - Software"], "BillingTreatmentSelection": ["LegalEntity", "LegalEntity", "Default"], "Status": ["Active"]},
    fnotes={"BillingTreatmentSelection": "Default: use DefaultBillingTreatmentId for every line. LegalEntity: match the order product's (or org default) legal entity against the treatments, else the default. Manual: the order product's own BillingTreatmentId."})

obj("BillingTreatment", "setup", 1, 8,
    "How an order item is billed: which legal entity, whether it is billed at all, milestone or not. Grouped under a policy.",
    "Billing admin (pre-seeded)", 5, "USA - Advance, Advance - Canada, USA - Arrears, Canada - Arrears, Milestone Billing Treatment", anchor=True,
    status="Draft → Active ⇄ Inactive; Draft or Inactive treatments cannot be assigned to order items.",
    ui="App Launcher → Billing Treatments",
    notes=["Billing Treatment - USA - Advance (1BTWs0000003EXtOAM) is on all seven groups of order 00000102."],
    key=["Id", "Name", "Status", "BillingPolicyId", "LegalEntityId", "ExcludeFromBilling", "IsMilestoneBilling"],
    samples={"Name": ["Billing Treatment - USA - Advance", "Billing Treatment - Advance - Canada", "Billing Treatment - USA - Arrears", "Billing Treatment - Canada - Arrears", "Milestone Billing Treatment"], "ExcludeFromBilling": ["No"]})

obj("BillingTreatmentItem", "setup", 1, 9,
    "The one rule per treatment that shapes the schedule: advance or arrears, and how the amount is split (remainder, percentage, flat).",
    "Billing admin (pre-seeded)", 8, "4 Remainder items (Advance/Arrears × USA/Canada) and 4 milestone Percentage items", anchor=True,
    status="Draft or Active (no Inactive). Draft items are ignored when schedules are created. Activate the item, then the treatment, then the policy.",
    ui="App Launcher → Billing Treatment Items",
    notes=["Billing Treatment Item - Advance - USA (1BDWs000000L1ltOAC) is BillingSchedule.BillingTreatmentItemId on all seven schedules — including the six usage ones. Advance vs Arrears should not matter for usage: Billing takes the period from the liable summary, not the treatment. Unproven until a usage invoice exists."],
    key=["Id", "Name", "Status", "BillingTreatmentId", "BillingType", "Type", "Controller", "ProcessingOrder"],
    samples={"BillingType": ["Advance", "Arrears", "None"], "Type": ["Remainder", "Percentage"], "Controller": ["BillingScheduleGroup", "None"]},
    fnotes={"BillingType": "Advance bills on or before the line's start date, Arrears after it. None is for milestone billing.",
            "Type": "Remainder, Percentage, FlatAmount — the help says these (and Sequencing, Handling0Amount) are required but not used when invoices are generated."})

obj("BillingBatchScheduler", "invoice", 5, 25,
    "A scheduled invoice run: job type (Invoice / Catch-Up / Forecast), cadence, target-date rule and filter criteria. Each firing creates an InvoiceBatchRun.",
    "You — Billing app → Billing Operations Console → Next Invoice Run → New Schedule", 0, "none yet; the first invoice was made on demand", anchor=True,
    status="Draft → Active → Completed / Canceled / Inactive.",
    ui="Billing app → Home (Billing Operations Console) → New Schedule; App Launcher → Billing Batch Schedulers",
    notes=["Usage schedules with a ReadyForInvoicing liable summary are always picked up, whatever the target date; billing period count does not apply to them.",
           "No Name column: the name field is BillingSchedulerName (SOQL, 20 Oct 2026)."],
    key=["Id", "BillingSchedulerName", "Status", "JobType", "FrequencyCadence", "StartDate", "StartTime", "NextRunTime", "RunCriteriaId", "ShouldGenerateInvoiceDocuments"])

# ---- stage 2: order ----------------------------------------------------------------------
obj("Order", "order", 2, 10,
    "The sale. Everything downstream hangs off it: the asset, the wallet, the billing schedules, the invoice.",
    "You, from quote Entrust Test Quote 1 (quote → order → Activate)", 1, "00000102, Activated, start 14 Oct 2026, Acme, 1,000 USD",
    anchor=True, status="Draft → Activated. An activated order cannot be deleted; set it back to Draft first (teardown script).",
    ui="App Launcher → Orders → 00000102. The Related tab lists Billing Schedules (7), Invoices and Revenue Transaction Error Logs.",
    notes=["With Billing on, activation fails unless BillToContactId, the billing address and the shipping address are filled (help: Turn On Billing). 00000102 has all three.",
           "The order's own action menu has no Generate Invoices in this org (Submit for Approval, Change Owner, Clone, Printable View, Reduce Order, New Contract)."],
    key=["Id", "OrderNumber", "Status", "AccountId", "QuoteId", "EffectiveDate", "EndDate", "Pricebook2Id", "BillToContactId", "BillingStreet", "ShippingStreet", "PaymentTermId", "LegalEntityId", "TotalAmount", "ActivatedDate"],
    samples={"OrderNumber": ["00000102"], "Status": ["Activated"], "EffectiveDate": ["2026-10-14"], "TotalAmount": ["1000"], "BillingStreet": ["109 Grafton Street"]})

obj("OrderItem", "order", 2, 11,
    "The order line: product, quantity, price, dates, selling model — and the billing frequency and treatment the schedules are built from.",
    "You (quote line → order product)", 1, "Document Check (VC-DOC-CHECK) × 1, 1,000 USD, Monthly", anchor=True,
    ui="Order 00000102 → Lines / Related → Order Products",
    notes=["BillingTreatmentId is empty on this line, so treatment resolution went: order item → product's billing policy (none) → org default (USA - Advance).",
           "BillingSchedule.ReferenceEntityItemId points here (802Ws00000TbEjHIAV) on all seven schedules."],
    key=["Id", "OrderId", "Product2Id", "PricebookEntryId", "Quantity", "UnitPrice", "TotalPrice", "ServiceDate", "EndDate", "BillingFrequency2", "BillingTreatmentId", "TaxTreatmentId", "LegalEntityId", "BindingInstanceTargetId", "ProductSellingModelId", "PeriodBoundary", "PeriodBoundaryDay", "SubscriptionTerm"],
    samples={"Quantity": ["1"], "UnitPrice": ["1000"], "BillingFrequency2": ["Monthly"]},
    fnotes={"BillingTreatmentId": "Empty here. Set it (or Product2.BillingPolicyId) to stop falling through to the org default.",
            "BindingInstanceTargetId": "Where usage binds: the asset itself for a Self-bound product (UsagePrdGrantBindingPolicy.GrantBindingType = Self)."})

# ---- stage 3: activation ------------------------------------------------------------------
obj("Asset", "order", 3, 12,
    "What the customer now owns. Created only for the anchor product — never for usage resources — and the grant-binding target for everything usage.",
    "Order to Asset flow, on activation", 1, "Document Check (02iWs00000SreQbIAJ), lifecycle 14 Oct–13 Nov 2026",
    ui="Account Acme → Assets; App Launcher → Assets",
    notes=["The asset is the GrantBindingTargetId on the entitlement account, the entitlements and (expected) the liable summaries — the match the invoice run checks.",
           "AssetRateCardEntry and AssetRateAdjustment (rates and tiers copied from the quote) hang off it; they are in the catalog model, not this one."],
    key=["Id", "Name", "AccountId", "Product2Id", "Status", "LifecycleStartDate", "LifecycleEndDate", "CurrentAmount", "CurrentQuantity", "BindingInstanceTargetId", "HasLifecycleManagement", "RenewalTerm"],
    samples={"Name": ["Document Check"], "LifecycleStartDate": ["2026-10-14"], "LifecycleEndDate": ["2026-11-13"]})

obj("TransactionUsageEntitlement", "wallet", 3, 13,
    "One grant per order item × usage resource: what quantity the customer is entitled to, for which resource, bound to which target.",
    "Order to Asset flow, on activation", 6, "one per RES-DOC-CHECK-* resource, EntitlementQuantity 0 (the grants are 0-quantity)",
    ui="App Launcher → Transaction Usage Entitlements",
    key=["Id", "Name", "AccountId", "AssetId", "OrderItemId", "UsageResourceId", "GrantBindingTargetId", "ActionType", "GrantType", "UsageModelType", "EntitlementQuantity", "EffectiveStartDateTime", "EffectiveEndDateTime", "PricebookEntryId"],
    samples={"ActionType": ["New"], "GrantType": ["Grant"], "UsageModelType": ["Anchor"]})

obj("UsageEntitlementAccount", "wallet", 3, 14,
    "The wallet: one per asset (binding target), carrying the billing period cadence the usage summaries are cut to.",
    "Order to Asset flow, on activation", 1, "UEA-0000000002: Acme, asset-bound, bill day 14, 1 MONTH, effective 14 Oct–13 Nov",
    ui="App Launcher → Usage Entitlement Accounts; Unified Usage Dashboard (wallet view)",
    notes=["BillingPeriodStartDateTime and BillingPeriodEndDateTime read 1970-01-01 — never initialised. The zero-value-summary stage of the usage flow is expected to set them.",
           "The six UsageSummary rows written on 20 Oct carry a UsageEntitlementAccountId that is actually the parent *bucket* id — the derived field follows ParentId, so read it with care."],
    key=["Id", "Name", "AccountId", "GrantBindingTargetId", "BillDayOfMonth", "BillingPeriodTerm", "BillingPeriodUnit", "BillingPeriodStartDateTime", "BillingPeriodEndDateTime", "EffectiveStartDateTime", "EffectiveEndDateTime", "PricebookEntryId"],
    samples={"Name": ["UEA-0000000002"], "BillDayOfMonth": ["14"], "BillingPeriodUnit": ["MONTH"], "BillingPeriodStartDateTime": ["1970-01-01T00:00:00Z (unset)"]},
    fnotes={"BillingPeriodStartDateTime": "1970-01-01 on the live record — unset, not a real period."})

obj("UsageEntitlementBucket", "wallet", 3, 15,
    "The balance for one resource in the wallet. A tree: six parent buckets under the account, each with one child bucket per grant.",
    "Order to Asset flow, on activation", 12, "6 parents (UEB-5…10, under the account, end 13 Nov) + 6 children (UEB-11…16, under a parent, no end date)",
    ui="App Launcher → Usage Entitlement Buckets",
    notes=["ParentId is the account for a parent bucket and a bucket for a child. Teardown deletes leaves first (SOQL cannot express the self-join; the Apex script loops).",
           "Which bucket a liable summary must reference — parent or child — is the open question for the m3ter utility. The UsageSummary rows written on 20 Oct point at the children."],
    key=["Id", "Name", "ParentId", "UsageResourceId", "TransactionUsageEntitlementId", "BucketBalance", "ConsumedEntitlement", "ProvisionalBucketBalance", "EffectiveStartDateTime", "EffectiveEndDateTime"],
    samples={"Name": ["UEB-0000000005 … UEB-0000000016"], "BucketBalance": ["0"]})

obj("UsageEntitlementEntry", "wallet", 3, 16,
    "The ledger line behind a bucket balance: credit on grant, debit on consumption, expiry at period end.",
    "Order to Asset flow (Original credit); the drawdown stage later (Consumption debits)", 6, "one Original entry per child bucket",
    ui="Usage Entitlement Bucket → Usage Entitlement Entries",
    key=["Id", "Name", "EntitlementBucketId", "TransactionType", "TransactionReason", "TransactionQuantity", "OpeningBalance", "ClosingBalance", "TransactionDate", "UsageSummaryId", "TransactionUsageEntitlementId"],
    samples={"TransactionType": ["Credit"], "TransactionReason": ["Original"]})

obj("BillingScheduleGroup", "schedule", 3, 17,
    "The billing header for one order item × binding instance (× usage resource): account, legal entity, payment term, treatment, bill day. Schedules hang under it.",
    "Order to Billing Schedule flow (RLM_Order_to_Billing_Schedule_Flow), on activation", 7, "BSG-4 (flat line, ReferenceEntityId = the asset) and BSG-5…10 (usage, ReferenceEntityId empty)",
    ui="Order 00000102 → Related → Billing Schedules → open a schedule → its group; App Launcher → Billing Schedule Groups",
    notes=["All seven: billing account Acme, Default Legal Entity - US, Default Payment Term (Net 30), Billing Treatment - USA - Advance, BillDayOfMonth 14.",
           "No Status, BillingFrequency, NextBillingDate or UsageResourceId on the group — those live on the schedule (SOQL refused all four, 20 Oct 2026).",
           "Deleting a group cascades its schedules; BillingSchedule itself has no delete() (teardown rule)."],
    key=["Id", "BillingScheduleGroupNumber", "BillingAccountId", "ReferenceEntityId", "BindingInstanceId", "BillingTreatmentId", "LegalEntityId", "PaymentTermId", "TaxTreatmentId", "BillDayOfMonth", "BillingType", "BillingMethod", "BillingTermUnit", "StartDate", "EndDate", "EffectiveNextBillingDate", "TotalBilledAmount", "TotalPendingAmount", "AnchorProdtBillingSchdGrpId"],
    samples={"BillingScheduleGroupNumber": ["BSG-000000004 … BSG-000000010"], "BillDayOfMonth": ["14"]},
    fnotes={"ReferenceEntityId": "The asset on the flat line's group only; empty on the six usage groups (20 Oct 2026).",
            "AnchorProdtBillingSchdGrpId": "How a usage resource's group would point back at its anchor product's group. Empty on 00000102."})

obj("BillingSchedule", "schedule", 3, 18,
    "What will be invoiced and when. One per order item (the flat charge) plus one per binding instance × usage resource. The invoice run reads these.",
    "Order to Billing Schedule flow, on activation", 7, "BS-4 flat: 1,000 USD, next billing 14 Oct; BS-5…10 usage: 0 USD, UsageResourceId set",
    status="ReadyForInvoicing → Processing → CompletelyBilled (or Error). Usage schedules are born ReadyForInvoicing and never reach CompletelyBilled: they stay open past their end date for late usage.",
    ui="Order 00000102 → Related → Billing Schedules (7); App Launcher → Billing Schedules (list view All)",
    notes=["A draft invoice leaves the schedule alone: after DOC-000000001, BS-4 still has NextBillingDate 14 Oct, PendingAmount 1,000, BilledAmount empty. Posting advances NextBillingDate, NextChargeFromDate, BilledThroughPeriod and BilledAmount.",
           "For usage schedules Billing computes no invoice periods — it stamps the liable summary's StartDateTime/EndDateTime on the BillingPeriodItem and invoice line.",
           "A second order on the same binding instance × resource updates the existing usage schedule's dates rather than creating another."],
    key=["Id", "BillingScheduleNumber", "Status", "Category", "Type", "BillingScheduleGroupId", "ReferenceEntityId", "ReferenceEntityItemId", "UsageResourceId", "BillingTreatmentItemId", "TaxTreatmentId", "BillingAccountId", "BillingScheduleStartDate", "BillingScheduleEndDate", "NextBillingDate", "NextChargeFromDate", "BillDayOfMonth", "BillingPeriodAmount", "TotalAmount", "BilledAmount", "PendingAmount", "BilledThroughPeriod", "InvoiceBatchRunId", "UnitPrice", "Quantity"],
    samples={"BillingScheduleNumber": ["BS-000000004 … BS-000000010"], "Status": ["ReadyForInvoicing"], "Category": ["Original"], "BillingScheduleStartDate": ["2026-10-14"], "BillingScheduleEndDate": ["2026-11-13"], "NextBillingDate": ["2026-10-14"], "BillingPeriodAmount": ["1000 (BS-4)", "0 (BS-5…10)"]},
    fnotes={"UsageResourceId": "Set only on the six usage schedules — the marker that a schedule bills a resource. Not writeable; the usage flag on the schedule, since the group has none.",
            "NextBillingDate": "Schedules with this on or before the run's target date are invoiced. A draft invoice does not move it; a posted one does.",
            "Status": "Usage schedules: always ReadyForInvoicing, never CompletelyBilled."})

obj("BsgRelationship", "schedule", 3, 19,
    "Links a bundle's component groups to the main group so the invoice can show the bundle together. Not used by a single-line order.",
    "Order to Billing Schedule flow, for bundles", 0, "none for 00000102",
    ui="Billing Schedule Group → related lists",
    key=["Id", "Name", "MainBsgId", "AssociatedBsgId", "MainBsgRole", "AssociatedBsgRole", "AssociatedBsgPricing"])

# ---- stage 4: usage --------------------------------------------------------------------------
obj("TransactionJournal", "usage", 4, 20,
    "Raw consumption: one row per usage event (resource, quantity, when, against which asset). The Create Usage Summary DPE aggregates them.",
    "Your usage feed — m3ter, the Usage Ingestion API, or a data load. Shared object: Loyalty and Accounting use it too, hence the airline and GL fields.", 0, "none yet (the 20 Oct usage summaries were written directly, bypassing journals)",
    anchor=True,
    status="Pending → Processed once aggregated into a UsageSummary. Rows that arrive after the summary period's waiting period (default 3 days) stay Pending and are ignored for that period.",
    ui="App Launcher → Transaction Journals (filter UsageType = UsageManagement)",
    notes=["UsageType must be UsageManagement; ReferenceRecordId is the asset; UsageResourceId the resource; ActivityDate inside the billing period.",
           "The m3ter design skips this object: m3ter has already aggregated and rated, so it writes the liable summary instead."],
    key=["Id", "Name", "Status", "UsageType", "ActivityDate", "Quantity", "QuantityUnitOfMeasureId", "UsageResourceId", "ReferenceRecordId", "AccountId", "UsageSummaryId", "UniqueIdentifier", "StartDate", "EndDate", "ProductId"],
    fnotes={"UsageType": "UsageManagement for consumption rows. Create-only.",
            "ReferenceRecordId": "The asset the usage belongs to (Asset or Vehicle)."})

obj("UsageSummary", "usage", 4, 21,
    "Aggregated consumption for one bucket over one summary period: consumed, debited from the grant, and the overage left to charge.",
    "Create Usage Summary DPE (Generate Usage Summary subflow). Zero-value rows are pre-created for the period by the Create Empty Summaries batch.", 6,
    "UAG-1…6, written directly by John's sync at 09:47 on 20 Oct: one per resource, 14–31 Oct, status New, OverageUnits 0, pointing at the child buckets",
    status="New → UsageSummaryInProgress → UsageSummaryComplete (frozen at T + waiting period) → DrawdownComplete → RatableSummaryComplete → LiableSummaryComplete.",
    ui="App Launcher → Usage Summaries; the demo flow RLM Usage Summaries Data Tables shows them as a table",
    notes=["Status drives the pipeline: only UsageSummaryComplete rows are drawn down, only DrawdownComplete rows are rated, only rated rows reach a liable summary.",
           "LiableSummaryId (→ UsageBillingPeriodItem) is the only link from a summary to its liable summary — it is on this side, so a liable summary can exist with no summary behind it."],
    key=["Id", "Name", "Status", "AccountId", "AssetId", "GrantBindingTargetId", "UsageEntitlementBucketId", "UsageEntitlementAccountId", "UsageResourceId", "UomId", "StartDateTime", "EndDateTime", "ConsumptionUnits", "DebitedUnits", "OverageUnits", "RatableSummaryId", "LiableSummaryId"],
    samples={"Name": ["UAG-0000000001 … 06"], "Status": ["New"], "StartDateTime": ["2026-10-14T00:00:00Z"], "EndDateTime": ["2026-10-31T23:59:59Z"], "ConsumptionUnits": ["873", "3552", "645", "5645", "1029", "5020"]},
    fnotes={"UsageEntitlementBucketId": "The child bucket (UEB-11…16) on the rows written 20 Oct.",
            "UsageEntitlementAccountId": "Read-only, derived — and on the 20 Oct rows it holds the parent bucket's id, not the UEA's."})

obj("UsageRatableSummary", "usage", 4, 22,
    "The rated view of a bucket's overage for the billing period: overage quantity, tier, net unit rate from the rating procedure, total amount.",
    "Generate Usage Ratable Summary subflow: drawdown via the entitlement service, then the rating request (Rating Procedure, decision tables)", 0, "none yet",
    status="New → InProgress (provisional, re-rated as usage lands) → SummaryCreated (period closed) → RatingComplete / RatingFailed.",
    ui="App Launcher → Usage Ratable Summaries",
    notes=["This is where the List vs Commit rate-card question bites: the rating procedure must pick one entry per resource, and order 00000102 carries both cards on every resource (README, 14 Oct)."],
    key=["Id", "Name", "Status", "AccountId", "AssetId", "UsageEntitlementBucketId", "UsageResourceId", "StartDateTime", "EndDateTime", "OverageQuantity", "TierQuantity", "NetUnitRate", "TotalAmount", "RatingRequestId", "RatingDecisionDateTime"])

obj("UsageBillingPeriodItem", "usage", 4, 23,
    "The liable summary: the overage quantity and amount to invoice for one bucket in one billing period. The invoice run reads this — not the summaries.",
    "Create Liable Summary DPE (Generate Liable Summary subflow) — or the m3ter utility, which writes it directly with the bill already rated", 0, "none yet",
    anchor=True,
    status="New → InProgress → LiableSummaryComplete → ReadyForInvoicing → Invoiced (set by posting) / InvoicingFailed. No default: a creator must set it. Voiding a posted invoice reverts Invoiced to ReadyForInvoicing.",
    ui="App Launcher → Liable Summaries → All Liable Summaries (needs the Usage Management Run Time permission set)",
    notes=["Invoiced when: Status ReadyForInvoicing; liable summary, bucket and entitlement account share the asset as GrantBindingTargetId; the usage billing schedule and the bucket name the same resource. Then Billing stamps StartDateTime/EndDateTime on the BillingPeriodItem and invoice line.",
           "Insert contract (EntityParticle, 20 Oct): required AccountId, UsageEntitlementBucketId, StartDateTime, EndDateTime, OverageQuantity, OverageAmount, TotalUsedQuantity, UoMId, Status; set AssetId and GrantBindingTargetId to the asset. Every field is updateable, so create at New and promote, or create at ReadyForInvoicing — to be tested.",
           "The RLM_*__c text fields mirror the lookups for this demo org's data-table flows; ignore them."],
    key=["Id", "UsageBillingPeriodItemNum", "Status", "AccountId", "AssetId", "GrantBindingTargetId", "UsageEntitlementBucketId", "UsageEntitlementAccountId", "UsageResourceId", "StartDateTime", "EndDateTime", "OverageQuantity", "OverageAmount", "TotalUsedQuantity", "UoMId", "CurrencyIsoCode"],
    fnotes={"UsageEntitlementBucketId": "Required. Derives UsageResourceId and UsageEntitlementAccountId. Parent or child bucket is the open question — the platform's own run will show it.",
            "Status": "Required, no default. ReadyForInvoicing is what the invoice run looks for.",
            "UoMId": "The counted unit (VERIFICATION-CHECK), not the currency unit.",
            "OverageAmount": "Required. For an m3ter-rated bill this is the line amount; OverageQuantity the billable quantity, TotalUsedQuantity the gross usage."})

# ---- stage 5: invoice ------------------------------------------------------------------------
obj("InvoiceBatchRun", "invoice", 5, 26,
    "One execution of an invoice scheduler: filters schedules, generates invoices in parallel, taxes them, advances the schedules, and summarises the run.",
    "A BillingBatchScheduler firing (Batch Management Service). Generate Invoices on an Account/Order does not create one.", 0, "none; DOC-000000001 was made on demand",
    status="Started → Completed / Failed / Stopped / Canceled, with StatusSubtype naming the stage (filtering, generation, summarisation).",
    ui="App Launcher → Invoice Batch Runs; Billing Operations Console → Invoice Batch Run Details",
    key=["Id", "InvoiceBatchRunNumber", "Status", "StatusSubtype", "JobType", "BillingBatchSchedulerId", "StartTime", "CompletionTime", "TotalFilteredBillingSchedules", "TotalInvoicesGenerated", "TotalInvoicesFailed", "TotalInvoicedAmount", "TotalDraftInvoices", "TotalDraftInvoiceAmount"])

obj("Invoice", "invoice", 5, 27,
    "The bill. Header totals, dates, due date from the payment term, legal entity, balance. Draft until posted.",
    "Generate Invoices (quick action) or an invoice batch run", 1, "DOC-000000001: Draft, dated 20 Oct, due 19 Nov, 1,000 + 100 tax = 1,100 USD, Acme",
    status="Draft → Posted (tax finalised, schedules advanced, liable summaries Invoiced) → Voided (reverts them). Split* values are for billing arrangements.",
    ui="Account Acme → Related → Invoices; Order 00000102 → Related → Invoices; App Launcher → Invoices; Billing Operations Console tiles",
    notes=["Generate Invoices is on neither the Account nor the Order action menu in this org — John reached it another way on 20 Oct (route to be recorded).",
           "A draft invoice touches nothing upstream, so it can be regenerated freely while experimenting; delete drafts before teardown."],
    key=["Id", "DocumentNumber", "Status", "BillingAccountId", "InvoiceDate", "DueDate", "PostedDate", "PaymentTermId", "LegalEntityId", "BillToContactId", "TotalAmount", "TotalTaxAmount", "TotalAmountWithTax", "Balance", "InvoiceBatchRunId", "ReferenceEntityId", "CreationMode"],
    samples={"DocumentNumber": ["DOC-000000001"], "Status": ["Draft"], "InvoiceDate": ["2026-10-20"], "DueDate": ["2026-11-19"], "TotalAmount": ["1000"], "TotalTaxAmount": ["100"], "TotalAmountWithTax": ["1100"]},
    fnotes={"BillingAccountId": "The billing account — there is no BillToAccountId (SOQL, 20 Oct 2026).",
            "DueDate": "InvoiceDate + the payment term (Net 30 → 19 Nov)."})

obj("InvoiceLine", "invoice", 5, 28,
    "One charge (or tax, or adjustment) on the invoice, tied back to its billing schedule. Usage lines carry the resource, consumed quantity and overage.",
    "The invoice run, one per billing period item", 1, "Document Check, Charge, 1 × 1,000, tax 100 (Estimated), 14 Oct–13 Nov, from BS-4",
    ui="Invoice DOC-000000001 → Invoice Lines; Invoice Line Summary component groups usage lines under their product",
    notes=["IsUsageBasedInvoiceLine, UsageProductId, UsageOverageQuantity, UsageProductBillSchdGrpId and UnitOfMeasureId are the usage columns — all empty on the flat line.",
           "No Status or ChargeType column: Type is the charge type (Charge / Tax / Adjustment) and InvoiceStatus mirrors the header (SOQL, 20 Oct 2026)."],
    key=["Id", "Name", "InvoiceId", "Type", "Product2Id", "BillingScheduleId", "BillingScheduleGroupId", "ReferenceEntityItemId", "Quantity", "UnitPrice", "ChargeAmount", "TaxAmount", "TaxRate", "LineAmount", "InvoiceLineStartDate", "InvoiceLineEndDate", "IsUsageBasedInvoiceLine", "UsageProductId", "UsageOverageQuantity", "UsageProductBillSchdGrpId", "UnitOfMeasureId", "LegalEntityId", "TaxTreatmentId", "TaxProcessingStatus"],
    samples={"Name": ["Document Check"], "Type": ["Charge"], "ChargeAmount": ["1000"], "TaxAmount": ["100"], "LineAmount": ["1100"], "InvoiceLineStartDate": ["2026-10-14"], "InvoiceLineEndDate": ["2026-11-13"], "TaxProcessingStatus": ["Estimated"]},
    fnotes={"TaxProcessingStatus": "Estimated on a draft (the mock engine's 10%); actual tax is calculated on posting.",
            "InvoiceLineStartDate": "For a usage line these come from the liable summary, not from the schedule's period arithmetic."})

obj("BillingPeriodItem", "invoice", 5, 29,
    "The slice of a billing schedule that one invoice line billed: period, amount — and for usage, the quantities and the liable summary it came from.",
    "The invoice run", 1, "BPI-000000001: BS-4, 14 Oct–13 Nov, 1,000, Draft",
    status="Draft → Reviewed; Canceled; Catch Up Processed (catch-up bill runs).",
    ui="Billing Schedule → Billing Period Items; Invoice Line → Billing Period Items",
    notes=["RelatedUsageBillPeriodItemId is the back-link from a usage invoice line's period item to the UsageBillingPeriodItem that fed it — the proof of which liable summary was billed.",
           "No PeriodStartDate: the columns are BillingPeriodStartDate / BillingPeriodEndDate (SOQL, 20 Oct 2026)."],
    key=["Id", "BillingPeriodItemNumber", "Status", "InvoiceStatus", "BillingScheduleId", "BillingScheduleGroupId", "InvoiceId", "InvoiceLineId", "InvoiceBatchRunId", "BillingPeriodStartDate", "BillingPeriodEndDate", "Amount", "OverageQuantity", "TotalUsedQuantity", "UnitOfMeasureId", "RelatedUsageBillPeriodItemId"],
    samples={"BillingPeriodItemNumber": ["BPI-000000001"], "Status": ["Draft"], "InvoiceStatus": ["Draft"], "Amount": ["1000"], "BillingPeriodStartDate": ["2026-10-14"], "BillingPeriodEndDate": ["2026-11-13"]},
    fnotes={"RelatedUsageBillPeriodItemId": "Set on usage lines only: which liable summary this period item invoiced."})

obj("RevenueTransactionErrorLog", "invoice", 5, 30,
    "Where Billing explains a failure: a schedule that could not be invoiced, a suspended group, a tax error. Check it when an invoice does not appear.",
    "Billing, on any failed generation or posting", 0, "none",
    ui="Account / Order / Invoice Batch Run → Related → Revenue Transaction Error Logs; Billing Operations Console → Billing Revenue Transaction Error Logs",
    key=["Id", "ErrorLogNumber", "Category", "Severity", "ErrorCode", "ErrorMessage", "PrimaryRecordId", "RelatedRecordId", "BillingScheduleGroupId"])

# ----------------------------------------------------------------------------- build

OBJ_IDS = {o["id"] for o in O}
assert OBJ_IDS == set(FIELDS["fields"]), OBJ_IDS ^ set(FIELDS["fields"])
assert sorted(sum(COLUMNS, [])) == sorted(OBJ_IDS)
assert len({o["seq"] for o in O}) == len(O)

PICK = FIELDS["picklists"]

def build():
    objects, edges = [], []
    for o in sorted(O, key=lambda x: x["seq"]):
        col = next(c for c, ids in enumerate(COLUMNS) if o["id"] in ids)
        fields = []
        key = set(o["key"])
        for name, typ, flags, ref in FIELDS["fields"][o["id"]]:
            f = {"n": name, "t": "lookup" if typ == "reference" else typ, "used": name in key}
            if "R" in flags: f["req"] = True
            if flags.replace("R", "") == "": f["ro"] = True
            elif "u" not in flags: f["co"] = True
            if name == "Id":
                f["k"] = "pk"; f["t"] = "id"; f["used"] = False
            if name in o["samples"]: f["samples"] = o["samples"][name]
            if name in o["fnotes"]: f["note"] = o["fnotes"][name]
            pk = f"{o['id']}.{name}"
            if pk in PICK: f["vals"] = PICK[pk]
            if ref:
                targets = ref.split("|")
                inside = [t for t in targets if t in OBJ_IDS]
                if inside:
                    primary = PRIMARY.get(pk, inside[0] if len(inside) == 1 else None)
                    kind_md = pk in MASTER_DETAIL or (flags in ("R", "Rc"))
                    for t in inside:
                        kind = "hi" if t == o["id"] else ("md" if kind_md and t == primary else "lk")
                        used = f["used"] and t == primary
                        edges.append({"from": o["id"], "field": name, "to": t, "kind": kind, "used": used,
                                      "poly": len(targets) > 1})
                    f["k"] = "hi" if primary == o["id"] else ("md" if kind_md else "lk")
                    f["to"] = primary or inside[0]
                    if len(targets) > 1: f["poly"] = targets
                else:
                    f["k"] = "lk"; f["to"] = " or ".join(targets[:2]) + (" …" if len(targets) > 2 else ""); f["ext"] = True
            fields.append(f)
        # key fields first in the order given, then the rest alphabetically — the card reads top-down
        order = {n: i for i, n in enumerate(o["key"])}
        fields.sort(key=lambda f: (0 if f["n"] == "Id" else 1 if f["n"] in order else 2, order.get(f["n"], 0), f["n"]))
        objects.append({**{k: v for k, v in o.items() if k not in ("key", "samples", "fnotes")}, "col": col, "fields": fields})
    return {"title": "Claude Billing Data Model", "snapshot": SNAPSHOT, "order": ORDER,
            "domains": DOMAINS, "stages": STAGES, "columns": COLUMNS, "objects": objects, "edges": edges}


MODEL = build()

# ----------------------------------------------------------------------------- the page

def react_blobs(src: str) -> str:
    blobs = re.findall(r"<script>/\* React(?:DOM)? 18\.3\.1.*?</script>", src, re.S)
    assert len(blobs) == 2, "expected the React and ReactDOM blobs in the template"
    return "\n".join(blobs)


STYLE = r"""
/* Layout: a one-screen schema workbench. Toolbar on top, an infinite pannable canvas of table
   cards below, a detail sheet that slides over the right edge (bottom sheet on phones). */
:root {
  --sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, monospace;
  --bg: #e9eef0;          /* canvas: cool drafting-paper grey */
  --dot: #c3ced3;
  --surface: #ffffff;
  --surface-2: #f3f6f7;
  --ink: #14232a;
  --ink-2: #4c5e67;
  --ink-3: #7d8e97;
  --line: #c5d0d5;
  --hair: #e6ecee;
  --edge: #5f737d;
  --edge-soft: #9fb0b8;
  --accent: #0a6c8c;
  --accent-ink: #ffffff;
  --mark: #fdf0c2;
  --warn: #b0500a;
  --shadow: rgba(20, 35, 42, .10);
  --d-setup: #6a4fc0;    --d-setup-bg: #ebe6f8;
  --d-order: #1c6bb3;    --d-order-bg: #e0edf9;
  --d-wallet: #9a5f06;   --d-wallet-bg: #f8edd6;
  --d-usage: #b23c3a;    --d-usage-bg: #f9e4e2;
  --d-schedule: #24764a; --d-schedule-bg: #dff1e6;
  --d-invoice: #0b7a7a;  --d-invoice-bg: #dcf1f0;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0e161a; --dot: #24323a; --surface: #172229; --surface-2: #1d2a32;
    --ink: #e3ebee; --ink-2: #a4b4bc; --ink-3: #74878f; --line: #2f3f48; --hair: #212f37;
    --edge: #8ea3ad; --edge-soft: #4d616b; --accent: #5cc6e2; --accent-ink: #06222c;
    --mark: #4a3d10; --warn: #f0a35e; --shadow: rgba(0, 0, 0, .45);
    --d-setup: #ab97f0;    --d-setup-bg: #2a2545;
    --d-order: #74b5ee;    --d-order-bg: #1a2d42;
    --d-wallet: #e3ab50;   --d-wallet-bg: #3a2e15;
    --d-usage: #f08e88;    --d-usage-bg: #402221;
    --d-schedule: #6fc895; --d-schedule-bg: #183326;
    --d-invoice: #5fd0cc;  --d-invoice-bg: #10332f;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0e161a; --dot: #24323a; --surface: #172229; --surface-2: #1d2a32;
  --ink: #e3ebee; --ink-2: #a4b4bc; --ink-3: #74878f; --line: #2f3f48; --hair: #212f37;
  --edge: #8ea3ad; --edge-soft: #4d616b; --accent: #5cc6e2; --accent-ink: #06222c;
  --mark: #4a3d10; --warn: #f0a35e; --shadow: rgba(0, 0, 0, .45);
  --d-setup: #ab97f0;    --d-setup-bg: #2a2545;
  --d-order: #74b5ee;    --d-order-bg: #1a2d42;
  --d-wallet: #e3ab50;   --d-wallet-bg: #3a2e15;
  --d-usage: #f08e88;    --d-usage-bg: #402221;
  --d-schedule: #6fc895; --d-schedule-bg: #183326;
  --d-invoice: #5fd0cc;  --d-invoice-bg: #10332f;
  color-scheme: dark;
}
html, body { height: 100%; }
body { background: var(--bg); color: var(--ink); font: 400 13px/1.45 var(--sans); overflow: hidden; }
#root { height: 100%; display: flex; flex-direction: column; }
button, input { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

[data-d="setup"]    { --dc: var(--d-setup);    --dbg: var(--d-setup-bg); }
[data-d="order"]    { --dc: var(--d-order);    --dbg: var(--d-order-bg); }
[data-d="wallet"]   { --dc: var(--d-wallet);   --dbg: var(--d-wallet-bg); }
[data-d="usage"]    { --dc: var(--d-usage);    --dbg: var(--d-usage-bg); }
[data-d="schedule"] { --dc: var(--d-schedule); --dbg: var(--d-schedule-bg); }
[data-d="invoice"]  { --dc: var(--d-invoice);  --dbg: var(--d-invoice-bg); }

/* ---------- toolbar ---------- */
.bar { flex: none; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;
  padding: 10px 16px; background: var(--surface); border-bottom: 1px solid var(--line); }
.brand { display: flex; flex-direction: column; margin-right: auto; min-width: 0; }
.brand h1 { margin: 0; font: 600 15px/1.25 var(--sans); letter-spacing: -.005em; text-wrap: balance; }
.brand p { margin: 0; font-size: 11.5px; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.grp { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.lbl { font-size: 10.5px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: var(--ink-3); }
.search { height: 30px; width: 220px; max-width: 100%; padding: 0 10px; border: 1px solid var(--line);
  border-radius: 4px; background: var(--surface-2); }
.search::placeholder { color: var(--ink-3); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.seg button { height: 28px; padding: 0 10px; border: 0; background: var(--surface-2); color: var(--ink-2); }
.seg button + button { border-left: 1px solid var(--line); }
.seg button[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); font-weight: 500; }
.btn { height: 30px; padding: 0 10px; border: 1px solid var(--line); border-radius: 4px;
  background: var(--surface-2); color: var(--ink); white-space: nowrap; }
.btn:hover { border-color: var(--ink-3); }
.btn[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.btn.sq { width: 30px; padding: 0; font-size: 16px; line-height: 1; }
.zoom { min-width: 42px; text-align: center; font-size: 11.5px; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.chip { height: 26px; padding: 0 9px 0 7px; display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid var(--line); border-radius: 13px; background: var(--surface-2); color: var(--ink-3); font-size: 12px; }
.chip i { width: 9px; height: 9px; border-radius: 2px; background: var(--line); }
.chip[aria-pressed="true"] { color: var(--ink); background: var(--dbg); border-color: var(--dc); }
.chip[aria-pressed="true"] i { background: var(--dc); }
.controls { display: contents; }
.more { display: none; }

/* ---------- the stage strip: the story of a bill, left to right ---------- */
.story { flex: none; display: flex; align-items: stretch; gap: 0; background: var(--surface); border-bottom: 1px solid var(--line);
  overflow-x: auto; scrollbar-width: thin; }
.story button { flex: 1 0 auto; min-width: 150px; display: flex; align-items: center; gap: 8px; padding: 7px 14px; border: 0;
  border-right: 1px solid var(--hair); background: none; color: var(--ink-2); font: 500 12px/1.3 var(--sans); text-align: left; }
.story button:hover { background: var(--surface-2); }
.story button[aria-pressed="true"] { color: var(--ink); background: var(--surface-2); box-shadow: inset 0 -2px 0 var(--accent); }
.story .n { flex: none; width: 20px; height: 20px; border-radius: 50%; border: 1.5px solid var(--ink-3); color: var(--ink-3);
  font: 600 11px/17px var(--sans); text-align: center; }
.story button[aria-pressed="true"] .n { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.story .arrow { flex: none; align-self: center; color: var(--ink-3); font-size: 14px; padding: 0 2px; }
.blurb { flex: none; padding: 8px 16px 10px; background: var(--surface-2); border-bottom: 1px solid var(--line);
  color: var(--ink); font-size: 12.5px; line-height: 1.5; max-width: 100%; }
.blurb b { font-weight: 600; margin-right: 6px; }

/* ---------- canvas ---------- */
.stage { position: relative; flex: 1; min-height: 0; overflow: hidden; }
.canvas { position: absolute; inset: 0; overflow: hidden; touch-action: none; cursor: grab;
  background-image: radial-gradient(var(--dot) 1px, transparent 1.2px); }
.canvas.panning { cursor: grabbing; }
.world { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
.edges { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }
.edge .hit { fill: none; stroke: transparent; stroke-width: 14; pointer-events: stroke; cursor: pointer; }
.edge .ln { fill: none; stroke: var(--edge); stroke-width: 1.25; }
.edge .mk { fill: none; stroke: var(--edge); stroke-width: 1.25; stroke-linecap: round; }
.edge.md .ln { stroke-width: 2; }
.edge.unused .ln { stroke: var(--edge-soft); stroke-dasharray: 5 4; }
.edge.unused .mk { stroke: var(--edge-soft); }
.edge.dim { opacity: .13; }
.edge.hot .ln, .edge.hot .mk { stroke: var(--accent); }
.edge.hot .ln { stroke-width: 2.4; }

.card { position: absolute; width: 280px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 5px; box-shadow: 0 1px 3px var(--shadow); cursor: grab; user-select: none;
  -webkit-user-select: none; touch-action: none; }
.card.drag { cursor: grabbing; box-shadow: 0 8px 22px var(--shadow); z-index: 5; }
.card.sel { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent), 0 6px 18px var(--shadow); z-index: 4; }
.card.dim { opacity: .26; }
.hd { height: 52px; box-sizing: border-box; padding: 7px 10px 0 8px; background: var(--dbg);
  border-bottom: 1px solid var(--line); border-radius: 4px 4px 0 0; }
.hd .nm { display: flex; align-items: center; gap: 7px; font: 600 13px/20px var(--sans); white-space: nowrap; }
.seq { flex: none; box-sizing: border-box; min-width: 21px; height: 20px; padding: 0 4px; border-radius: 4px;
  background: var(--dc); color: var(--surface); border: 1.5px solid var(--dc);
  font: 600 11.5px/17px var(--sans); font-variant-numeric: tabular-nums; text-align: center; }
.seq.anchor { background: transparent; color: var(--dc); }
.hd .nm span { overflow: hidden; text-overflow: ellipsis; }
.hd .meta { display: flex; gap: 6px; align-items: center; margin-top: 1px; padding-left: 28px;
  font: 400 10.5px/16px var(--sans); color: var(--ink-2); white-space: nowrap; overflow: hidden; }
.hd .meta span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.tag { flex: none; padding: 0 5px; border: 1px solid var(--dc); border-radius: 3px; color: var(--dc);
  font: 600 9px/13px var(--sans); letter-spacing: .05em; text-transform: uppercase; }
.row { height: 22px; box-sizing: border-box; display: flex; align-items: center; padding-right: 8px;
  font: 400 11.5px/21px var(--mono); border-top: 1px solid var(--hair); }
.hd + .row { border-top: 0; }
.row .g { flex: none; width: 30px; text-align: center; font: 600 9px/1 var(--sans); letter-spacing: .05em; color: var(--ink-3); }
.row.fk .g, .row.pk .g { color: var(--dc); }
.row .n { flex: 0 1 auto; min-width: 60px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row.pk .n, .row.key .n { font-weight: 600; }
.row.unused .n { color: var(--ink-2); }
.row.dep .n { text-decoration: line-through; text-decoration-color: var(--ink-3); }
.row .k { flex: none; margin-left: 5px; font-size: 8px; color: var(--dc); }
.row .w { flex: none; margin-left: 5px; width: 6px; height: 6px; border-radius: 50%; background: var(--warn); }
.row .t { flex: 1 1 0; min-width: 0; margin-left: 8px; font-size: 10.5px; color: var(--ink-3); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; text-align: right; }
.row.hit { background: var(--mark); }
.row.hot { background: var(--surface-2); box-shadow: inset 2px 0 0 var(--accent); }
.ft { display: block; width: 100%; height: 24px; box-sizing: border-box; padding: 0 10px 0 30px; border: 0;
  border-top: 1px solid var(--line); border-radius: 0 0 4px 4px; background: var(--surface-2);
  color: var(--ink-2); font: 500 10.5px/23px var(--sans); text-align: left; }
.ft:hover { color: var(--accent); }
.elabel { position: absolute; transform: translate(-50%, -50%); padding: 3px 8px; border-radius: 3px;
  background: var(--ink); color: var(--surface); font: 500 11px/1.4 var(--mono); white-space: nowrap;
  pointer-events: none; z-index: 9; box-shadow: 0 2px 8px var(--shadow); }
.elabel em { font: 400 10.5px var(--sans); font-style: normal; opacity: .8; margin-left: 8px; }

/* ---------- overlays ---------- */
.legend { position: absolute; left: 16px; bottom: 16px; max-width: min(330px, calc(100% - 32px));
  background: var(--surface); border: 1px solid var(--line); border-radius: 5px;
  box-shadow: 0 2px 10px var(--shadow); font-size: 11.5px; }
.legend > button { display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; height: 30px;
  padding: 0 10px; border: 0; background: none; font-weight: 600; font-size: 11px; letter-spacing: .07em; text-transform: uppercase; color: var(--ink-2); }
.legend .body { padding: 2px 12px 10px; display: grid; grid-template-columns: 44px 1fr; gap: 5px 10px; align-items: center; color: var(--ink-2); }
.legend svg { display: block; overflow: visible; }
.legend .gl { font: 600 9px/1 var(--sans); letter-spacing: .05em; color: var(--ink-3); text-align: center; }
.legend .src { grid-column: 1 / -1; margin: 5px 0 0; padding-top: 7px; border-top: 1px solid var(--hair); line-height: 1.45; }
.hint { position: absolute; right: 16px; bottom: 16px; max-width: calc(100% - 380px); padding: 5px 10px; border-radius: 4px;
  background: var(--surface); border: 1px solid var(--line); color: var(--ink-2); font-size: 11.5px; pointer-events: none; }

.panel { position: absolute; top: 0; right: 0; bottom: 0; width: min(380px, 100%); display: flex; flex-direction: column;
  background: var(--surface); border-left: 1px solid var(--line); box-shadow: -6px 0 24px var(--shadow); z-index: 20; }
.panel header { flex: none; padding: 14px 16px 12px; background: var(--dbg); border-bottom: 1px solid var(--line); }
.panel header .top { display: flex; align-items: flex-start; gap: 10px; }
.panel .top .seq { margin-top: 1px; min-width: 24px; height: 22px; font-size: 12.5px; line-height: 19px; }
.panel h2 { flex: 1; min-width: 0; margin: 0; font: 600 15px/1.3 var(--mono); overflow-wrap: anywhere; }
.panel .dom { font: 600 10px/1 var(--sans); letter-spacing: .07em; text-transform: uppercase; color: var(--dc); margin-bottom: 6px; }
.panel .x { flex: none; width: 28px; height: 28px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface); font-size: 16px; line-height: 1; }
.panel .purpose { margin: 8px 0 0; color: var(--ink); max-width: 44ch; }
.panel .scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 16px 24px; }
.panel h3 { margin: 18px 0 7px; font: 600 10.5px/1 var(--sans); letter-spacing: .07em; text-transform: uppercase; color: var(--ink-3); }
.panel h3:first-child { margin-top: 0; }
.facts { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 5px 12px; }
.facts dt { color: var(--ink-2); }
.facts dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.facts code, .rel code, .fld code { font: 500 11.5px var(--mono); }
.notes { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
.notes li { padding-left: 9px; border-left: 2px solid var(--warn); font-size: 12px; color: var(--ink); }
.rel { list-style: none; margin: 0; padding: 0; display: grid; gap: 3px; }
.rel button { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 6px; width: 100%; padding: 5px 8px; border: 1px solid var(--hair);
  border-radius: 4px; background: var(--surface-2); text-align: left; }
.rel button:hover { border-color: var(--accent); }
.rel .sq { color: var(--ink-3); font: 500 10.5px var(--sans); font-variant-numeric: tabular-nums; }
.rel .kind { margin-left: auto; font-size: 10.5px; color: var(--ink-3); }
.fld { padding: 7px 0; border-top: 1px solid var(--hair); }
.fld .l1 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; }
.fld .l1 code { font-weight: 600; }
.fld.unused .l1 code { font-weight: 400; color: var(--ink-2); }
.fld .ty { color: var(--ink-3); font: 400 11px var(--mono); }
.fld .bd { padding: 0 5px; border-radius: 3px; background: var(--surface-2); border: 1px solid var(--line); color: var(--ink-2); font-size: 10px; line-height: 15px; white-space: nowrap; }
.fld .bd.on { border-color: var(--dc); color: var(--dc); }
.fld .bd.wn { border-color: var(--warn); color: var(--warn); }
.fld p { margin: 3px 0 0; font-size: 12px; color: var(--ink-2); overflow-wrap: anywhere; }
.fld p.note { color: var(--ink); padding-left: 9px; border-left: 2px solid var(--warn); }
.panel .src { margin: 16px 0 0; font-size: 11.5px; color: var(--ink-3); }

@media (max-width: 720px) {
  .bar { padding: 8px 16px; gap: 6px 10px; }
  .brand h1 { font-size: 14px; }
  .more { display: inline-flex; align-items: center; }
  .controls { display: none; flex-basis: 100%; flex-wrap: wrap; align-items: center; gap: 8px 10px; }
  .controls.open { display: flex; }
  .search { width: 100%; }
  .hint { display: none; }
  .story button { min-width: 120px; padding: 6px 10px; }
  .panel { top: auto; left: 0; width: 100%; height: 56%; border-left: 0; border-top: 1px solid var(--line); box-shadow: 0 -6px 24px var(--shadow); }
}
@media (prefers-reduced-motion: no-preference) {
  .card, .edge { transition: opacity .12s; }
}
"""

APP = r"""
(function () {
  'use strict';
  const { useState, useRef, useEffect, useMemo, useCallback } = React;
  const h = React.createElement;
  const MODEL = JSON.parse(document.getElementById('model').textContent);
  const OBJ = Object.fromEntries(MODEL.objects.map(o => [o.id, o]));
  const DOMAIN = Object.fromEntries(MODEL.domains.map(d => [d.id, d.label]));
  const STAGE = Object.fromEntries(MODEL.stages.map(s => [s.n, s]));
  const W = 280, HEAD = 52, ROW = 22, FOOT = 24, COLGAP = 110, ROWGAP = 44;
  const STORE = 'claude-billing-erd-v1';
  const KIND = { lk: 'lookup', md: 'master-detail', hi: 'hierarchy' };
  const USED_EDGES = MODEL.edges.filter(e => e.used).length;
  const ORDER_ROWS = MODEL.objects.filter(o => o.stage >= 2).reduce((n, o) => n + o.records, 0);

  function loadSaved() { try { return JSON.parse(localStorage.getItem(STORE) || 'null') || {}; } catch (e) { return {}; } }
  function saveState(v) { try { localStorage.setItem(STORE, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  const isFk = f => f.k === 'lk' || f.k === 'md' || f.k === 'hi';

  /* Which rows a card shows, and how tall that makes it. Row positions are computed, never measured,
     so a relationship line can land exactly on the field that holds the foreign key. */
  function buildLayout(st) {
    const raw = st.q.trim().toLowerCase(), q = /^\d+$/.test(raw) ? '' : raw;   // a bare number searches stages, not field names
    const map = {};
    for (const o of MODEL.objects) {
      const all = st.expanded[o.id] !== undefined ? st.expanded[o.id] : st.mode === 'all';
      const rows = o.fields.filter(f => f.k === 'pk' || f.used || all ||
        (q && f.n.toLowerCase().includes(q)) ||
        (st.showUnused && isFk(f) && f.to && !f.ext));
      const extra = o.fields.filter(f => !f.used && f.k !== 'pk').length;
      const hidden = o.fields.length - rows.length;
      map[o.id] = { rows, all, extra, hidden, foot: extra > 0, h: HEAD + rows.length * ROW + (extra > 0 ? FOOT : 0) + 2 };
    }
    return map;
  }
  function tidy(layout, domains) {
    const pos = {};
    MODEL.columns.forEach((col, c) => {
      let y = 0;
      for (const id of col) {
        pos[id] = { x: c * (W + COLGAP), y };
        if (domains[OBJ[id].domain]) y += layout[id].h + ROWGAP;
      }
    });
    return pos;
  }
  function edgeGeom(e, pos, layout) {
    const s = pos[e.from], t = pos[e.to], L = layout[e.from];
    const i = L.rows.findIndex(f => f.n === e.field);
    const sy = i >= 0 ? s.y + HEAD + i * ROW + ROW / 2 : s.y + HEAD + L.rows.length * ROW + FOOT / 2;
    const ty = t.y + HEAD + ROW / 2;
    const dx = (t.x + W / 2) - (s.x + W / 2);
    let sx, tx, sd, td, c1, c2;
    if (e.from === e.to || Math.abs(dx) < W * 0.75) {           // stacked in one column: loop out to the right
      sx = s.x + W; tx = t.x + W; sd = 1; td = 1;
      const b = 46 + Math.min(70, Math.abs(ty - sy) * 0.12);
      c1 = sx + b; c2 = tx + b;
    } else {
      if (dx > 0) { sx = s.x + W; sd = 1; tx = t.x; td = -1; } else { sx = s.x; sd = -1; tx = t.x + W; td = 1; }
      const c = Math.max(54, Math.abs(tx - sx) * 0.45);
      c1 = sx + sd * c; c2 = tx + td * c;
    }
    const a = sx + sd * 12, b2 = tx + td * 9;
    const d = `M${a} ${sy} C${c1} ${sy} ${c2} ${ty} ${b2} ${ty}`;
    let mk = `M${a} ${sy}L${sx} ${sy - 5.5}M${a} ${sy}L${sx} ${sy}M${a} ${sy}L${sx} ${sy + 5.5}` +   // crow's foot: many
             `M${b2} ${ty}L${tx} ${ty}M${tx + td * 6} ${ty - 5.5}L${tx + td * 6} ${ty + 5.5}`;       // bar: one
    if (e.kind === 'md') mk += `M${tx + td * 10} ${ty - 5.5}L${tx + td * 10} ${ty + 5.5}`;           // second bar: required parent
    const mx = (a + 3 * c1 + 3 * c2 + b2) / 8, my = (sy + ty) / 2;
    return { d, mk, mx, my };
  }

  function App() {
    const saved = useMemo(loadSaved, []);
    const [mode, setMode] = useState(saved.mode === 'all' ? 'all' : 'key');
    const [expanded, setExpanded] = useState({});
    const [showUnused, setShowUnused] = useState(!!saved.showUnused);
    const [domains, setDomains] = useState(() => Object.fromEntries(MODEL.domains.map(d => [d.id, true])));
    const [stage, setStage] = useState(0);
    const [q, setQ] = useState('');
    const [selected, setSelected] = useState(null);
    const [hoverObj, setHoverObj] = useState(null);
    const [hoverEdge, setHoverEdge] = useState(null);
    const [dragging, setDragging] = useState(null);
    const [panning, setPanning] = useState(false);
    const [legendOpen, setLegendOpen] = useState(false);
    const [barOpen, setBarOpen] = useState(false);
    const [view, setView] = useState({ x: 40, y: 40, k: 0.6 });
    const [custom, setCustom] = useState(!!saved.pos);

    const layout = useMemo(() => buildLayout({ mode, expanded, showUnused, q }), [mode, expanded, showUnused, q]);
    const [pos, setPos] = useState(() => {
      const base = tidy(buildLayout({ mode: saved.mode === 'all' ? 'all' : 'key', expanded: {}, showUnused: !!saved.showUnused, q: '' }),
        Object.fromEntries(MODEL.domains.map(d => [d.id, true])));
      return saved.pos ? Object.assign(base, saved.pos) : base;
    });
    const canvasRef = useRef(null);
    const stateRef = useRef({}); stateRef.current = { view, pos, layout, domains };

    // Until someone moves a card by hand, keep the automatic arrangement in step with card heights.
    useEffect(() => { if (!custom) setPos(tidy(layout, domains)); }, [layout, domains, custom]);
    useEffect(() => { saveState({ mode, showUnused, pos: custom ? pos : undefined }); }, [mode, showUnused, custom, dragging === null && pos]);

    const fit = useCallback((p, l, dm) => {
      const el = canvasRef.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const ids = MODEL.objects.filter(o => dm[o.domain]).map(o => o.id);
      if (!ids.length || !r.width) return;
      const x0 = Math.min(...ids.map(i => p[i].x)), y0 = Math.min(...ids.map(i => p[i].y));
      const x1 = Math.max(...ids.map(i => p[i].x + W)) + 60, y1 = Math.max(...ids.map(i => p[i].y + l[i].h));
      const pad = r.width < 720 ? 16 : 36;
      const k = clamp(Math.min((r.width - pad * 2) / (x1 - x0), (r.height - pad * 2) / (y1 - y0)), 0.12, 1.1);
      setView({ k, x: (r.width - (x1 - x0) * k) / 2 - x0 * k, y: Math.max(pad, (r.height - (y1 - y0) * k) / 2) - y0 * k });
    }, []);
    useEffect(() => { fit(pos, layout, domains); }, []);   // eslint-disable-line

    const zoomAt = useCallback((cx, cy, factor) => {
      setView(v => { const k = clamp(v.k * factor, 0.12, 2.5); const r = k / v.k; return { k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r }; });
    }, []);
    const zoomBtn = f => { const r = canvasRef.current.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, f); };

    // Scroll pans; pinch or Ctrl/Cmd-scroll zooms about the pointer.
    useEffect(() => {
      const el = canvasRef.current;
      const onWheel = ev => {
        ev.preventDefault();
        if (ev.ctrlKey || ev.metaKey) {
          const r = el.getBoundingClientRect();
          zoomAt(ev.clientX - r.left, ev.clientY - r.top, Math.exp(-ev.deltaY * 0.01));
        } else {
          setView(v => ({ ...v, x: v.x - ev.deltaX, y: v.y - ev.deltaY }));
        }
      };
      el.addEventListener('wheel', onWheel, { passive: false });
      const onKey = ev => { if (ev.key === 'Escape') { setSelected(null); setQ(''); setStage(0); } };
      window.addEventListener('keydown', onKey);
      return () => { el.removeEventListener('wheel', onWheel); window.removeEventListener('keydown', onKey); };
    }, [zoomAt]);

    // Background drag pans; two fingers pinch-zoom.
    const pts = useRef(new Map()); const moved = useRef(false);
    const bgDown = ev => {
      if (ev.target.closest('.card')) return;
      ev.currentTarget.setPointerCapture(ev.pointerId);
      pts.current.set(ev.pointerId, { x: ev.clientX, y: ev.clientY }); moved.current = false; setPanning(true);
    };
    const bgMove = ev => {
      const P = pts.current; if (!P.has(ev.pointerId)) return;
      const prev = P.get(ev.pointerId), cur = { x: ev.clientX, y: ev.clientY };
      if (P.size === 1) {
        if (Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y) > 0) moved.current = true;
        setView(v => ({ ...v, x: v.x + cur.x - prev.x, y: v.y + cur.y - prev.y }));
      } else if (P.size === 2) {
        const other = [...P.entries()].find(([id]) => id !== ev.pointerId)[1];
        const d0 = Math.hypot(prev.x - other.x, prev.y - other.y), d1 = Math.hypot(cur.x - other.x, cur.y - other.y);
        const r = canvasRef.current.getBoundingClientRect();
        if (d0 > 0) zoomAt((cur.x + other.x) / 2 - r.left, (cur.y + other.y) / 2 - r.top, d1 / d0);
        moved.current = true;
      }
      P.set(ev.pointerId, cur);
    };
    const bgUp = ev => {
      if (!pts.current.has(ev.pointerId)) return;
      pts.current.delete(ev.pointerId);
      if (!pts.current.size) { setPanning(false); if (!moved.current) setSelected(null); }
    };

    // Card drag. A press that never moves is a click, which opens the detail sheet.
    const drag = useRef(null);
    const cardDown = (ev, id) => {
      if (ev.button || ev.target.closest('.ft')) return;
      ev.stopPropagation();
      ev.currentTarget.setPointerCapture(ev.pointerId);
      const p = stateRef.current.pos[id];
      drag.current = { id, px: ev.clientX, py: ev.clientY, ox: p.x, oy: p.y, moved: false };
    };
    const cardMove = ev => {
      const d = drag.current; if (!d) return;
      const k = stateRef.current.view.k, dx = (ev.clientX - d.px) / k, dy = (ev.clientY - d.py) / k;
      if (!d.moved && Math.abs(ev.clientX - d.px) + Math.abs(ev.clientY - d.py) < 4) return;
      if (!d.moved) { d.moved = true; setDragging(d.id); setCustom(true); }
      setPos(p => ({ ...p, [d.id]: { x: Math.round(d.ox + dx), y: Math.round(d.oy + dy) } }));
    };
    const cardUp = () => {
      const d = drag.current; if (!d) return; drag.current = null;
      if (d.moved) { setDragging(null); return; }
      if (selected === d.id) setSelected(null); else { setSelected(d.id); reveal(d.id); }
    };

    const reveal = id => {
      const r = canvasRef.current.getBoundingClientRect(), p = stateRef.current.pos[id], l = stateRef.current.layout[id];
      const phone = r.width <= 720;
      setView(v => {
        if (phone) {                       // sheet covers the lower part: bring the table into the strip above it
          const k = Math.max(v.k, 0.5), free = r.height * 0.44;
          return { k, x: r.width / 2 - (p.x + W / 2) * k, y: Math.max(12, (free - l.h * k) / 2) - p.y * k };
        }
        const free = r.width - 380, x0 = p.x * v.k + v.x, x1 = x0 + W * v.k;
        let x = v.x;
        if (x1 > free - 24) x -= x1 - (free - 24);
        if (x0 + (x - v.x) < 24) x = 24 - p.x * v.k;
        return x === v.x ? v : { ...v, x };
      });
    };
    const goTo = id => {
      setSelected(id);
      if (!domains[OBJ[id].domain]) setDomains(dm => ({ ...dm, [OBJ[id].domain]: true }));
      const r = canvasRef.current.getBoundingClientRect(), p = stateRef.current.pos[id], l = stateRef.current.layout[id];
      setView(v => { const k = Math.max(v.k, 0.7); const side = r.width > 720 ? 380 : 0;
        return { k, x: (r.width - side) / 2 - (p.x + W / 2) * k, y: Math.max(30, r.height * (side ? 0.5 : 0.19) - (p.y + l.h / 2) * k) }; });
    };

    // ---- what is in focus
    const ql = q.trim().toLowerCase();
    const edges = MODEL.edges.filter(e => domains[OBJ[e.from].domain] && domains[OBJ[e.to].domain] && (e.used || showUnused));
    const focus = hoverObj || selected;
    const edgeKey = e => e.from + '.' + e.field + '>' + e.to;
    const hotEdges = new Set(); const near = new Set();
    if (hoverEdge) { const e = edges.find(x => edgeKey(x) === hoverEdge); if (e) { hotEdges.add(hoverEdge); near.add(e.from); near.add(e.to); } }
    else if (focus) { near.add(focus); edges.forEach(e => { if (e.from === focus || e.to === focus) { hotEdges.add(edgeKey(e)); near.add(e.from); near.add(e.to); } }); }
    const matches = o => /^\d+$/.test(ql) ? o.stage === +ql : (o.id.toLowerCase().includes(ql) || o.fields.some(f => f.n.toLowerCase().includes(ql)));
    const inStage = o => !stage || o.stage === stage;
    const isDim = o => (near.size && !near.has(o.id)) || (!near.size && ((ql && !matches(o)) || !inStage(o)));

    const label = hoverEdge && edges.find(x => edgeKey(x) === hoverEdge);
    const labelGeom = label && edgeGeom(label, pos, layout);
    const visibleCount = MODEL.objects.filter(o => domains[o.domain]).length;
    const fieldHot = (o, f) => [...hotEdges].some(k => k.startsWith(o.id + '.' + f.n + '>'));

    return h('div', { style: { display: 'contents' } },
      h('div', { className: 'bar' },
        h('div', { className: 'brand' },
          h('h1', null, MODEL.title),
          h('p', null, `${MODEL.objects.length} objects · ${USED_EDGES} relationships on the chain · ${ORDER_ROWS} rows behind order ${MODEL.order} on ${MODEL.snapshot}`)),
        h('button', { id: 'more', className: 'btn more', 'aria-expanded': barOpen, 'aria-controls': 'controls', onClick: () => setBarOpen(v => !v) }, barOpen ? 'Hide controls' : 'Controls'),
        h('div', { id: 'controls', className: 'controls' + (barOpen ? ' open' : '') },
        h('input', { id: 'q', className: 'search', type: 'search', placeholder: 'Find an object, field or stage', value: q,
          'aria-label': 'Find an object, field or stage number', onChange: ev => setQ(ev.target.value) }),
        h('div', { className: 'grp' },
          h('span', { className: 'lbl' }, 'Fields'),
          h('div', { className: 'seg', role: 'group', 'aria-label': 'Which fields to show' },
            h('button', { id: 'mode-key', 'aria-pressed': mode === 'key', onClick: () => { setMode('key'); setExpanded({}); } }, 'Key fields'),
            h('button', { id: 'mode-all', 'aria-pressed': mode === 'all', onClick: () => { setMode('all'); setExpanded({}); } }, 'All'))),
        h('button', { id: 'unused', className: 'btn', 'aria-pressed': showUnused, onClick: () => setShowUnused(v => !v),
          title: 'Lookups between these objects that the billing chain does not rely on' }, 'Other lookups'),
        h('div', { className: 'grp', role: 'group', 'aria-label': 'Areas' },
          MODEL.domains.map(d => h('button', { key: d.id, id: 'dom-' + d.id, className: 'chip', 'data-d': d.id, 'aria-pressed': domains[d.id],
            onClick: () => setDomains(dm => ({ ...dm, [d.id]: !dm[d.id] })) }, h('i'), d.label))),
        h('div', { className: 'grp' },
          h('button', { id: 'tidy', className: 'btn', onClick: () => { const p = tidy(layout, domains); setCustom(false); setPos(p); fit(p, layout, domains); },
            title: 'Put every table back in its starting place' }, 'Reset layout'),
          h('button', { id: 'fit', className: 'btn', onClick: () => fit(pos, layout, domains) }, 'Fit'),
          h('button', { id: 'zoom-out', className: 'btn sq', 'aria-label': 'Zoom out', onClick: () => zoomBtn(1 / 1.25) }, '−'),
          h('span', { className: 'zoom' }, Math.round(view.k * 100) + '%'),
          h('button', { id: 'zoom-in', className: 'btn sq', 'aria-label': 'Zoom in', onClick: () => zoomBtn(1.25) }, '+')))),

      h('div', { className: 'story', role: 'group', 'aria-label': 'The life of a bill, stage by stage' },
        MODEL.stages.map((s, i) => [
          i > 0 && h('span', { key: 'a' + s.n, className: 'arrow', 'aria-hidden': true }, '→'),
          h('button', { key: s.n, id: 'stage-' + s.n, 'aria-pressed': stage === s.n, onClick: () => setStage(stage === s.n ? 0 : s.n),
            title: s.blurb }, h('span', { className: 'n' }, s.n), s.label)])),
      stage > 0 && h('div', { className: 'blurb', role: 'status' }, h('b', null, `Stage ${stage} · ${STAGE[stage].label}.`), STAGE[stage].blurb),

      h('div', { className: 'stage' },
        h('div', { ref: canvasRef, className: 'canvas' + (panning ? ' panning' : ''),
            style: { backgroundSize: `${22 * view.k}px ${22 * view.k}px`, backgroundPosition: `${view.x}px ${view.y}px` },
            onPointerDown: bgDown, onPointerMove: bgMove, onPointerUp: bgUp, onPointerCancel: bgUp },
          h('div', { className: 'world', style: { transform: `translate(${view.x}px,${view.y}px) scale(${view.k})` } },
            h('svg', { className: 'edges', width: 1, height: 1, 'aria-hidden': true },
              edges.map(e => {
                const g = edgeGeom(e, pos, layout), key = edgeKey(e), hot = hotEdges.has(key);
                const dim = !hot && (near.size || (ql && !(matches(OBJ[e.from]) && matches(OBJ[e.to]))) || (stage && !(inStage(OBJ[e.from]) && inStage(OBJ[e.to]))));
                return h('g', { key, className: 'edge ' + e.kind + (e.used ? '' : ' unused') + (hot ? ' hot' : '') + (dim ? ' dim' : '') },
                  h('path', { className: 'ln', d: g.d }), h('path', { className: 'mk', d: g.mk }),
                  h('path', { className: 'hit', d: g.d, onPointerEnter: () => setHoverEdge(key), onPointerLeave: () => setHoverEdge(null) }));
              })),
            MODEL.objects.filter(o => domains[o.domain]).map(o => {
              const L = layout[o.id], p = pos[o.id];
              return h('div', { key: o.id, className: 'card' + (selected === o.id ? ' sel' : '') + (dragging === o.id ? ' drag' : '') + (isDim(o) ? ' dim' : ''),
                  'data-d': o.domain, 'data-id': o.id, style: { left: p.x, top: p.y }, tabIndex: 0, role: 'button',
                  'aria-label': o.id + ', stage ' + o.stage + ' ' + STAGE[o.stage].label + ', ' + plural(o.records, 'row') + '. Open details.',
                  onPointerDown: ev => cardDown(ev, o.id), onPointerMove: cardMove, onPointerUp: cardUp, onPointerCancel: cardUp,
                  onPointerEnter: () => setHoverObj(o.id), onPointerLeave: () => setHoverObj(null),
                  onKeyDown: ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); if (selected === o.id) setSelected(null); else { setSelected(o.id); reveal(o.id); } } } },
                h('div', { className: 'hd' },
                  h('div', { className: 'nm' },
                    h('b', { className: 'seq' + (o.anchor ? ' anchor' : ''),
                      title: (o.anchor ? 'Written by you or an integration' : 'Created by the platform') + ' · position ' + o.seq + ' of ' + MODEL.objects.length + ' along the chain' }, o.seq),
                    h('span', null, o.id)),
                  h('div', { className: 'meta' },
                    h('span', { title: o.recordsNote }, plural(o.records, 'row') + ' · ' + STAGE[o.stage].label.toLowerCase()),
                    o.anchor && h('span', { className: 'tag', title: o.by }, 'you write'),
                    o.status && h('span', { className: 'tag', title: o.status }, 'lifecycle'))),
                L.rows.map(f => {
                  const fk = isFk(f);
                  const cls = 'row' + (f.k === 'pk' ? ' pk' : '') + (fk ? ' fk' : '') + (f.req && f.k !== 'pk' ? ' key' : '') + (f.used || f.k === 'pk' ? '' : ' unused') +
                    (ql && !/^\d+$/.test(ql) && f.n.toLowerCase().includes(ql) ? ' hit' : '') + (fieldHot(o, f) ? ' hot' : '');
                  const tip = (fk ? KIND[f.k] + (f.to ? ' → ' + f.to : '') : (f.t || 'type unknown')) +
                    (f.req ? ' · required' : '') + (f.ro ? ' · read-only' : '') + (f.co ? ' · create-only' : '') + (f.note ? '\n' + f.note : '');
                  const firstEdge = fk && f.to && !f.ext ? MODEL.edges.find(e => e.from === o.id && e.field === f.n && e.to === f.to) : null;
                  return h('div', { key: f.n, className: cls, title: tip,
                      onPointerEnter: firstEdge ? () => setHoverEdge(edgeKey(firstEdge)) : undefined,
                      onPointerLeave: firstEdge ? () => setHoverEdge(null) : undefined },
                    h('span', { className: 'g' }, f.k === 'pk' ? 'PK' : f.k === 'md' ? 'MD' : fk ? 'FK' : ''),
                    h('span', { className: 'n' }, f.n),
                    f.req && f.k !== 'pk' && h('span', { className: 'k', 'aria-label': 'required' }, '◆'),
                    f.note && h('span', { className: 'w', 'aria-label': 'has a known gotcha' }),
                    h('span', { className: 't' }, (fk && f.to ? '→ ' + f.to : f.t || '—')));
                }),
                L.foot && h('button', { className: 'ft', onPointerDown: ev => ev.stopPropagation(),
                    onClick: ev => { ev.stopPropagation(); setExpanded(x => ({ ...x, [o.id]: !L.all })); } },
                  L.all ? 'Show only the key fields' : `+ ${L.hidden} more ${L.hidden === 1 ? 'field' : 'fields'}`));
            }),
            label && h('div', { className: 'elabel', style: { left: labelGeom.mx, top: labelGeom.my, transform: `translate(-50%,-50%) scale(${1 / view.k})` } },
              `${label.from}.${label.field} → ${label.to}`,
              h('em', null, 'many to one · ' + KIND[label.kind] + (label.poly ? ' · polymorphic' : '') + (label.used ? '' : ' · not on the chain'))))),

        visibleCount === 0 && h('div', { className: 'hint', style: { left: '50%', right: 'auto', bottom: '50%', transform: 'translate(-50%, 50%)', maxWidth: 'calc(100% - 32px)' } },
          'Every area is switched off. Turn one back on in the toolbar.'),

        h('div', { className: 'legend' },
          h('button', { id: 'legend-toggle', 'aria-expanded': legendOpen, onClick: () => setLegendOpen(v => !v) }, 'Legend', h('span', null, legendOpen ? '–' : '+')),
          legendOpen && h('div', { className: 'body' },
            h('svg', { width: 44, height: 12, 'aria-hidden': true }, h('g', { className: 'edge lk' },
              h('path', { className: 'ln', d: 'M12 6H35' }), h('path', { className: 'mk', d: 'M12 6L0 0.5M12 6L0 6M12 6L0 11.5M35 6H44M38 0.5V11.5' }))),
            h('span', null, 'Lookup. Many rows on the left point to one on the right.'),
            h('svg', { width: 44, height: 12, 'aria-hidden': true }, h('g', { className: 'edge md' },
              h('path', { className: 'ln', d: 'M12 6H31' }), h('path', { className: 'mk', d: 'M12 6L0 0.5M12 6L0 6M12 6L0 11.5M31 6H44M34 0.5V11.5M38 0.5V11.5' }))),
            h('span', null, 'Master-detail (or a required, system-set parent). The child cannot exist without it.'),
            h('svg', { width: 44, height: 12, 'aria-hidden': true }, h('g', { className: 'edge lk unused' },
              h('path', { className: 'ln', d: 'M12 6H35' }), h('path', { className: 'mk', d: 'M12 6L0 0.5M12 6L0 6M12 6L0 11.5M35 6H44M38 0.5V11.5' }))),
            h('span', null, 'A lookup between these objects that the billing chain does not rely on.'),
            h('span', { className: 'gl', style: { display: 'flex', gap: 3, justifyContent: 'center' }, 'data-d': 'schedule' },
              h('b', { className: 'seq' }, '18'), h('b', { className: 'seq anchor' }, '23')),
            h('span', null, 'Position along the chain. Filled: the platform creates it. Outlined: you, an admin or an integration writes it.'),
            h('span', { className: 'gl' }, 'PK · FK · MD'), h('span', null, 'Record Id, lookup field, master-detail field.'),
            h('span', { className: 'gl', style: { fontSize: 10 } }, '◆'), h('span', null, 'Required on insert (not nillable).'),
            h('span', { className: 'gl' }, h('span', { style: { display: 'inline-block', width: 6, height: 6, borderRadius: 3, background: 'var(--warn)' } })),
            h('span', null, 'A gotcha recorded on 20 Oct. Open the table to read it.'),
            h('span', { className: 'gl', style: { font: '400 10.5px var(--sans)' } }, '1 → 5'), h('span', null, 'The strip above the canvas: click a stage to see only what it creates.'),
            h('p', { className: 'src' }, 'Field names, types, required / create-only / read-only flags and lookup targets come from EntityParticle in m3ter-arm-260 (API v68.0) on ' + MODEL.snapshot + '. Row counts and sample values are from the same day. Status lifecycles are from the Salesforce help (documents/billing-usage-to-invoice.md).'))),

        !selected && h('div', { className: 'hint' }, 'Click a stage above to follow the story · drag a table to move it · scroll to pan · pinch or Ctrl/⌘-scroll to zoom · click a table for its fields'),

        selected && h(Panel, { o: OBJ[selected], goTo, close: () => setSelected(null) })));
  }

  function Panel({ o, goTo, close }) {
    const out = o.fields.filter(f => isFk(f) && f.to);
    const into = MODEL.edges.filter(e => e.to === o.id && e.from !== o.id);
    const keyCount = o.fields.filter(f => f.used).length;
    const st = STAGE[o.stage];
    return h('aside', { className: 'panel', 'data-d': o.domain, 'aria-label': o.id + ' details' },
      h('header', null,
        h('div', { className: 'dom' }, DOMAIN[o.domain]),
        h('div', { className: 'top' }, h('b', { className: 'seq' + (o.anchor ? ' anchor' : '') }, o.seq), h('h2', null, o.id), h('button', { id: 'panel-close', className: 'x', 'aria-label': 'Close details', onClick: close }, '×')),
        h('p', { className: 'purpose' }, o.purpose)),
      h('div', { className: 'scroll' },
        h('h3', null, 'In the life of a bill'),
        h('dl', { className: 'facts' },
          h('dt', null, 'Stage'), h('dd', null, `${o.stage} · ${st.label} — position ${o.seq} of ${MODEL.objects.length} along the chain.`),
          h('dt', null, 'Created by'), h('dd', null, o.by),
          h('dt', null, 'Rows on ' + MODEL.snapshot), h('dd', null, String(o.records) + (o.recordsNote ? ' — ' + o.recordsNote : '')),
          o.status && h('dt', null, 'Lifecycle'), o.status && h('dd', null, o.status),
          o.ui && h('dt', null, 'Where in the UI'), o.ui && h('dd', null, o.ui),
          h('dt', null, 'Key fields'), h('dd', null, `${keyCount} of ${o.fields.length - 1}`)),
        o.notes.length > 0 && h('h3', null, 'Worth knowing'),
        o.notes.length > 0 && h('ul', { className: 'notes' }, o.notes.map((n, i) => h('li', { key: i }, n))),
        out.length > 0 && h('h3', null, 'Points to'),
        out.length > 0 && h('ul', { className: 'rel' }, out.map(f => h('li', { key: f.n },
          f.ext ? h('button', { disabled: true, style: { cursor: 'default' } }, h('code', null, f.n), '→ ' + f.to, h('span', { className: 'kind' }, KIND[f.k] + ' · outside this model'))
                : h('button', { onClick: () => goTo(f.to) }, h('code', null, f.n), '→ ' + f.to, h('span', { className: 'sq' }, 'stage ' + OBJ[f.to].stage), h('span', { className: 'kind' }, KIND[f.k] + (f.poly ? ' · polymorphic' : '') + (f.used ? '' : ' · not on the chain')))))),
        into.length > 0 && h('h3', null, 'Pointed to by'),
        into.length > 0 && h('ul', { className: 'rel' }, into.map(e => h('li', { key: e.from + e.field },
          h('button', { onClick: () => goTo(e.from) }, h('code', null, e.from + '.' + e.field), h('span', { className: 'sq' }, 'stage ' + OBJ[e.from].stage), h('span', { className: 'kind' }, KIND[e.kind] + (e.used ? '' : ' · not on the chain')))))),
        h('h3', null, 'Fields'),
        o.fields.map(f => {
          const fk = isFk(f);
          return h('div', { key: f.n, className: 'fld' + (f.used || f.k === 'pk' ? '' : ' unused') },
            h('div', { className: 'l1' },
              h('code', null, f.n),
              h('span', { className: 'ty' }, (f.t || 'type unknown') + (fk && f.to ? ' → ' + f.to : '')),
              f.k === 'pk' && h('span', { className: 'bd on' }, 'primary key'),
              f.used && h('span', { className: 'bd on' }, 'key field'),
              f.req && f.k !== 'pk' && h('span', { className: 'bd' }, 'required'),
              f.co && h('span', { className: 'bd' }, 'create-only'),
              f.ro && h('span', { className: 'bd' }, 'read-only'),
              f.poly && h('span', { className: 'bd' }, 'polymorphic')),
            f.poly && h('p', null, 'Can point to: ' + f.poly.join(', ')),
            f.samples && h('p', null, 'In the org: ', f.samples.map((s, i) => h('code', { key: i }, (i ? ', ' : '') + String(s)))),
            f.vals && h('p', null, 'Values: ' + f.vals.join(', ')),
            f.note && h('p', { className: 'note' }, f.note));
        }),
        h('p', { className: 'src' }, 'Field list from EntityParticle in m3ter-arm-260 on ' + MODEL.snapshot + ' (system audit fields omitted). Required means not nillable; read-only means neither createable nor updateable — set by the platform.')));
  }

  ReactDOM.createRoot(document.getElementById('root')).render(h(App));
})();
"""

HEAD_COMMENT = f"""<!-- Interactive data model of Revenue Cloud Billing: what order activation creates, where usage goes,
     and how a bill comes out. Generated {SNAPSHOT} by customers/entrust/docs/build_billing_data_model.py from
     billing-fields.json (EntityParticle, m3ter-arm-260, v68.0) and the annotations in that script.
     Open this file in a browser. It is a snapshot: re-run the generator when the org or the notes change. -->"""

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{HEAD_COMMENT}
<style>html, body {{ margin: 0; }}</style>
<title>Claude Billing Data Model</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{STYLE}</style>
</head>
<body>
<div id="root"></div>
<script type="application/json" id="model">{json.dumps(MODEL, separators=(',', ':'), ensure_ascii=False)}</script>
{react_blobs(TEMPLATE)}
<script>{APP}</script>
</body>
</html>
"""

OUT.write_text(page)
n_fields = sum(len(o["fields"]) for o in MODEL["objects"])
print(f"wrote {OUT.relative_to(ROOT)}: {len(MODEL['objects'])} objects, {n_fields} fields, "
      f"{len(MODEL['edges'])} edges ({sum(e['used'] for e in MODEL['edges'])} on the chain), {len(page):,} bytes")
