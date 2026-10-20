#!/usr/bin/env python3
"""Build models/verification-catalog-structure.html from the recommendation YAML.

    python3 models/build_structure_chart.py [yaml] [out.html]

The page is self-contained (React and the fonts are inlined, copied from the
m3ter structure charts) and draws the Revenue Cloud catalog the YAML
recommends: price book -> rate cards -> products (with their USD/EUR rates)
-> usage resources -> units, plus the catalog/category tree and the Is Retry
attribute. "Open another config" in the page accepts a JSON file of the same
shape as the embedded <script id="config-data"> block.

The React blob and the @font-face lines are read from the files beside this
script in structure-chart/ (react-inline.html, fonts.css); otherwise React is loaded
from cdnjs and the system fonts are used.
"""
import json
import sys
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "verification-catalog.recommendation.yaml"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "verification-catalog-structure.html"

y = yaml.safe_load(src.read_text())
cat = y["catalog"]

# Records known to exist in m3ter-arm-260 (hand build, 2026-10-06). Keyed by
# the code used in this chart. Extend when more of the catalog is applied.
ORG = {
    "PB-STANDARD": {"id": "01s (Standard Price Book)", "status": "Active"},
    "PB-RATECARD-D-USD": {"id": "1CIWs0000006kZdOAI", "status": "Active", "link": "PRC-00000009"},
    "PB-RATECARD-B-EUR": {"id": "1CIWs0000006kbFOAQ", "status": "Active", "link": "PRC-00000010"},
    "VC-DOCUMENT-REPORT-STANDARD-HYBRID": {"id": "01tWs00000H8LDZIA3", "status": "Active", "pbe": "01uWs000007RGkbIAG"},
    "VC-BUNDLE-AE": {"id": "01tWs00000H8LtVIAV", "status": "Active"},
    "RES-DOCUMENT-REPORT-STANDARD-HYBRID": {"id": "1BRWs0000006MttOAE", "status": "Active"},
    "RES-BUNDLE-AE": {"id": "1BRWs0000006MvVOAU", "status": "Active"},
    "RCE:PB-RATECARD-D-USD:VC-DOCUMENT-REPORT-STANDARD-HYBRID": {"id": "1CJWs0000007Po5OAE", "status": "Active"},
    "RCE:PB-RATECARD-B-EUR:VC-DOCUMENT-REPORT-STANDARD-HYBRID": {"id": "1CJWs0000007PphOAE", "status": "Active"},
    "RCE:PB-RATECARD-D-USD:VC-BUNDLE-AE": {"id": "1CJWs0000007PrJOAU", "status": "Active"},
    "VERIFICATION-UOM-CLASS": {"id": "1BQWs0000006wfdOAA", "status": "Active"},
    "CHECK": {"id": "0hEWs0000018yEXMAY", "status": "Active"},
    "EUR": {"id": "0hEWs0000018yHlMAI", "status": "Active"},
    "USD": {"id": "0hEWs000000pnq4MAA", "status": "Active"},
    "BLOCK": {"id": "created 2026-10-06, id not recorded", "status": "Active"},
    "PSM_EvergreenMonthly": {"id": "pre-seeded, lookup-only", "status": "Active"},
    "CAT-BUNDLES": {"id": "0ZGWs000001cwDhOAI", "status": "Active"},
    "CAT-VERIFICATION": {"id": "0ZSWs000001B5OnOAK", "status": "Active"},
    "IS-RETRY": {"id": "0tjWs000001GtzFIAS", "status": "Active"},
    "PC-VERIFICATION-CHECK": {"id": "11BWs00000cPgB3MAK", "status": "Active"},
}


def d(v):
    return v.isoformat() if isinstance(v, date) else v


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [jsonable(v) for v in o]
    return d(o)


products = []
for p in cat["products"]:
    products.append({
        "code": p["code"], "name": p["name"], "category": p["category"],
        "kind": "product",
        "m3ter_meter": p.get("m3ter_meter"), "m3ter_aggregation": p.get("m3ter_aggregation"),
        "resource": p["resource"], "classification": p.get("classification"),
        "attributes": p.get("attributes") or ([a for a in ("IS-RETRY",)] if p.get("priced_by_attribute") else []),
        "m3ter_dimensions_unpriced": p.get("m3ter_dimensions_unpriced", []),
        "note": p.get("note"),
    })
for b in cat["bundles"]:
    products.append({
        "code": b["code"], "name": b["name"], "category": b["category"], "kind": "bundle",
        "m3ter_compound_aggregation": b.get("m3ter_compound_aggregation"),
        "m3ter_calculation": b.get("m3ter_calculation"),
        "components": b.get("components", []), "rule": b.get("rule"),
        "resource": b["resource"], "classification": b.get("classification"),
        "observed_price": b.get("observed_price", {}), "anomaly": b.get("anomaly"),
        "attributes": [],
    })

# Products priced per attribute value carry the attribute (the rate dict form).
rates = []
for pb in y["price_books"]:
    for code, v in pb["rates"].items():
        if isinstance(v, dict):
            for seg, val in v.items():
                rates.append({"rate_card": pb["code"], "product": code, "rate": val, "segment": seg})
            for p in products:
                if p["code"] == code and "IS-RETRY" not in p["attributes"]:
                    p["attributes"].append("IS-RETRY")
        else:
            rates.append({"rate_card": pb["code"], "product": code, "rate": v, **({"contract": True} if code.startswith("VC-BUNDLE") else {})})

data = {
    "meta": {**jsonable(y["meta"]), "source_yaml": src.name, "built": date.today().isoformat()},
    "price_book": {"code": "PB-STANDARD", "name": "Standard Price Book",
                   "note": "The only price book in the org; every rate card hangs off it through PriceBookRateCard. Every product also gets a 0.00 PricebookEntry here so it can be quoted."},
    "selling_model": {"name": "Evergreen Monthly", **jsonable(cat["selling_model"])},
    "rate_cards": [{
        "code": pb["code"], "name": pb["rate_card"]["name"], "currency": pb["currency"],
        "type": pb["rate_card"].get("type"), "effective_from": d(pb["rate_card"].get("effective_from")),
        "rate_unit": pb.get("rate_unit"), "m3ter_plan_template": pb.get("m3ter_plan_template"),
        "m3ter_bill_frequency": pb.get("m3ter_bill_frequency"), "note": pb.get("note"),
        "history_not_loaded": jsonable(pb.get("history_not_loaded")),
    } for pb in y["price_books"]],
    "catalog": {"code": "CATALOG", **jsonable(cat["product_catalog"])} if "product_catalog" in cat else {"code": "CATALOG", "name": "Verification Catalog"},
    "categories": jsonable(cat["categories"]),
    "classifications": jsonable(cat.get("classifications", [])),
    "attributes": jsonable(cat.get("attributes", [])),
    "units": jsonable(cat["units"]),
    "products": products,
    "rates": rates,
    "accounts": jsonable(y.get("accounts", [])),
    "decisions": jsonable(y.get("decisions", {})),
    "open_questions": jsonable(y.get("open_questions", [])),
    "org": ORG,
}

VENDOR = HERE / "structure-chart"
react = (VENDOR / "react-inline.html").read_text() if (VENDOR / "react-inline.html").exists() else (
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>\n'
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>')
fonts = (VENDOR / "fonts.css").read_text() if (VENDOR / "fonts.css").exists() else ""

CSS = r"""
:root {
  --ground: #EDF0F3; --surface: #FFFFFF; --ink: #15202B; --muted: #5B6875; --rule: #CDD5DD; --wash: #E1E6EB;
  --usd: #2C6DB8; --eur: #C4266F; --calc: #94640A; --wire: #8C99A7; --built: #1F8A5B;
  --sans: 'Onest', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root { --ground: #12181F; --surface: #1C252F; --ink: #E7EDF3; --muted: #97A5B3; --rule: #33404D; --wash: #25303C;
          --usd: #78AEEE; --eur: #F472A8; --calc: #E0AC45; --wire: #6F7E8D; --built: #5CC894; }
}
* { box-sizing: border-box; }
html { background: var(--ground); }
body { margin: 0; background: var(--ground); color: var(--ink); font: 13px/1.4 var(--sans); -webkit-font-smoothing: antialiased; }
button { font: inherit; color: inherit; }
.mono { font-family: var(--mono); font-size: 0.86em; letter-spacing: -0.01em; }
.quiet { color: var(--muted); }
.page { padding: 20px 24px 40px; min-width: min-content; }
.top { display: flex; flex-wrap: wrap; gap: 14px 40px; justify-content: space-between; align-items: flex-end; margin-bottom: 18px; }
.top-title { max-width: 760px; }
.top h1 { display: inline; margin: 0 14px 0 0; font-size: 34px; line-height: 1.1; font-weight: 600; letter-spacing: -0.025em; }
.top-code { color: var(--muted); font-size: 13px; }
.top p { margin: 8px 0 0; color: var(--muted); max-width: 72ch; }
.top-tools { display: flex; flex-direction: column; gap: 10px; align-items: flex-end; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 20px; list-style: none; margin: 0; padding: 0; color: var(--muted); font-size: 12px; }
.legend li { display: flex; align-items: center; gap: 7px; }
.controls { display: flex; gap: 10px; align-items: center; }
.seg { display: inline-flex; border: 1px solid var(--rule); border-radius: 7px; overflow: hidden; }
.seg button { border: 0; background: transparent; padding: 5px 12px; cursor: pointer; color: var(--muted); }
.seg button[aria-pressed='true'] { background: var(--ink); color: var(--ground); }
.ghost { border: 1px solid var(--rule); background: transparent; border-radius: 7px; padding: 5px 12px; cursor: pointer; white-space: nowrap; }
.ghost:hover, .seg button:hover { border-color: var(--ink); color: var(--ink); }
.seg button[aria-pressed='true']:hover { color: var(--ground); }
.error { margin: 0 0 14px; padding: 9px 12px; border-left: 3px solid var(--eur); background: var(--surface); max-width: 80ch; }
:focus-visible { outline: 2px solid var(--usd); outline-offset: 2px; }
.canvas { position: relative; }
.col-heads { position: sticky; top: 0; z-index: 3; background: var(--ground); border-bottom: 1px solid var(--rule); }
.col-heads span { position: absolute; bottom: 8px; font-weight: 600; font-size: 12px; white-space: nowrap; }
.col-heads i { font-style: normal; font-weight: 400; color: var(--muted); margin-left: 7px; font-variant-numeric: tabular-nums; }
.stage { position: relative; margin-top: 14px; }
.wires { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }
.edge { fill: none; stroke: var(--wire); stroke-width: 1.4; transition: opacity 0.15s; }
.edge.usd { stroke: var(--usd); stroke-width: 1.2; opacity: 0.45; }
.edge.eur { stroke: var(--eur); stroke-width: 1.2; opacity: 0.45; }
.edge.calc { stroke: var(--calc); stroke-width: 1.5; stroke-dasharray: 5 4; }
.edge.attr { stroke: var(--calc); stroke-width: 1.3; stroke-dasharray: 2 3; }
.edge.feed, .edge.unit, .edge.member { stroke-width: 1.2; }
.edge.link { stroke-width: 1.6; }
.legend .edge { opacity: 1; }
.stage.tracing .edge { opacity: 0.07; }
.stage.tracing .edge.lit { opacity: 1; }
.node { position: absolute; margin: 0; text-align: left; background: var(--surface); border: 1px solid var(--rule); cursor: pointer; overflow: hidden; transition: opacity 0.15s; }
.node:hover { border-color: var(--ink); }
.node.sel { border-color: var(--ink); box-shadow: 0 0 0 1.5px var(--ink); }
.stage.tracing .node:not(.lit) { opacity: 0.28; }
.card { border-radius: 10px; padding: 7px 11px; display: flex; flex-direction: column; justify-content: center; gap: 3px; }
.card > * { flex-shrink: 0; }
.card-name { font-weight: 600; line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-code { color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-meta { color: var(--muted); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.k-pricebook, .k-catalog { border-radius: 14px; border-width: 1.5px; border-color: var(--ink); }
.k-attribute { border-style: dashed; border-color: var(--calc); }
.k-sellingmodel, .k-uomclass { border-style: dotted; }
.row { border-radius: 6px; padding: 0 9px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.row.bundle { border-style: dashed; border-color: var(--calc); }
.row-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.built::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--built); margin-right: 7px; vertical-align: 1px; flex-shrink: 0; }
.rate { white-space: nowrap; font-variant-numeric: tabular-nums; font-size: 12.5px; display: inline-flex; gap: 8px; align-items: baseline; }
.rate b { font-weight: 600; }
.rate .usd { color: var(--usd); }
.rate .eur { color: var(--eur); }
.rate-none { color: var(--muted); font-size: 11.5px; }
.panel-slot { position: absolute; left: 0; bottom: 0; pointer-events: none; }
.panel { position: sticky; pointer-events: auto; overflow: auto; border-top: 2px solid var(--ink); padding: 14px 16px 6px 0; }
.panel h2 { margin: 0; font-size: 20px; line-height: 1.2; font-weight: 600; letter-spacing: -0.015em; }
.panel h3 { margin: 22px 0 6px; font-size: 13px; font-weight: 600; }
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.detail-kind { margin: 4px 0 0; color: var(--muted); }
.prose { margin: 12px 0 0; max-width: 72ch; }
.panel > div > .quiet { margin: 12px 0 0; }
.link { border: 0; background: none; padding: 0; cursor: pointer; text-decoration: underline; text-decoration-color: var(--wire); text-underline-offset: 2px; text-align: left; }
.link:hover { text-decoration-color: var(--ink); }
.calc { margin: 12px 0 0; padding: 10px 12px; background: var(--wash); border-radius: 6px; font: 11.5px/1.5 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }
.org { margin: 10px 0 0; padding: 8px 12px; border-left: 3px solid var(--built); background: var(--surface); max-width: 72ch; }
.org.none { border-left-color: var(--rule); color: var(--muted); }
.fields { display: grid; grid-template-columns: max-content 1fr; gap: 0 18px; margin: 0; }
.fields dt, .fields dd { margin: 0; padding: 4px 0; border-bottom: 1px solid var(--rule); }
.fields dt { color: var(--muted); }
.fields dd { overflow-wrap: anywhere; }
.grid { border-collapse: collapse; width: 100%; font-size: 12.5px; }
.grid.tight { width: auto; min-width: 60%; }
.grid th { text-align: left; font-weight: 600; font-size: 11.5px; color: var(--muted); padding: 4px 16px 4px 0; border-bottom: 1px solid var(--ink); white-space: nowrap; }
.grid td { padding: 4px 16px 4px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
.grid .nowrap { white-space: nowrap; }
.grid .num { text-align: right; font-variant-numeric: tabular-nums; }
.grid tr.live td { font-weight: 600; }
.grid tr.idle td { color: var(--muted); }
@media (prefers-reduced-motion: reduce) { .edge, .node { transition: none; } }
@media print { .controls { display: none; } .col-heads, .panel { position: static; } }
"""

APP_JS = r"""
const { useState, useMemo, useEffect, useRef } = React;
const h = React.createElement;
const arr = (v) => Array.isArray(v) ? v : [];
const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
function money(value, currency) {
  if (typeof value !== "number") return String(value);
  try { return new Intl.NumberFormat("en", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value); }
  catch (err) { return value.toFixed(2); }
}
function fmtDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return String(iso);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
function midTrunc(text, max) {
  if (!text || text.length <= max) return text;
  const head = Math.ceil((max - 1) * 0.4);
  return `${text.slice(0, head)}…${text.slice(text.length - (max - 1 - head))}`;
}
function flatFields(obj, omit = []) {
  const out = [];
  const walk = (o, prefix) => Object.entries(o).forEach(([k, v]) => {
    if (!prefix && omit.includes(k)) return;
    const label = prefix ? `${prefix}.${k}` : k;
    if (v === null || v === void 0 || v === "") return;
    if (Array.isArray(v)) { if (v.length && v.every((x) => typeof x !== "object")) out.push([label, v.join(", ")]); return; }
    if (typeof v === "object") { walk(v, label); return; }
    out.push([label, String(v)]);
  });
  walk(obj || {}, "");
  return out;
}
// Which Revenue Cloud sObjects each box stands for. Load order from the data model.
const KINDS = {
  pricebook:    { title: "Price book", many: "Price books", sobjects: "Pricebook2 (lookup-only) + PricebookEntry per product" },
  sellingmodel: { title: "Selling model", many: "Selling models", sobjects: "ProductSellingModel (lookup-only) + ProductSellingModelOption per product" },
  ratecard:     { title: "Rate card", many: "Rate cards", sobjects: "RateCard + PriceBookRateCard" },
  catalog:      { title: "Catalog", many: "Catalogs", sobjects: "ProductCatalog" },
  category:     { title: "Category", many: "Categories", sobjects: "ProductCategory + ProductCategoryProduct per product" },
  attribute:    { title: "Attribute", many: "Attributes", sobjects: "AttributePicklist + AttributePicklistValue + AttributeDefinition + ProductClassificationAttr" },
  product:      { title: "Product", many: "Products", sobjects: "Product2 + ProductSellingModelOption + PricebookEntry + RateCardEntry per rate card" },
  resource:     { title: "Usage resource", many: "Usage resources", sobjects: "UsageResource + ProductUsageResource" },
  uom:          { title: "Unit of measure", many: "Units of measure", sobjects: "UnitOfMeasure" },
  uomclass:     { title: "Unit of measure class", many: "Unit of measure classes", sobjects: "UnitOfMeasureClass" },
};
function buildModel(cfg) {
  const nodes = new Map();
  const add = (kind, key, data) => { if (key === void 0 || key === null) return; nodes.set(`${kind}:${key}`, { id: `${kind}:${key}`, kind, key, data }); };
  const pb = cfg.price_book || { code: "PB-STANDARD", name: "Standard Price Book" };
  add("pricebook", pb.code, pb);
  if (cfg.selling_model) add("sellingmodel", cfg.selling_model.use || "PSM", { code: cfg.selling_model.use, name: cfg.selling_model.name || "Evergreen Monthly", ...cfg.selling_model });
  arr(cfg.rate_cards).forEach((r) => add("ratecard", r.code, r));
  if (cfg.catalog) add("catalog", cfg.catalog.code || "CATALOG", cfg.catalog);
  arr(cfg.categories).forEach((c) => add("category", c.code, c));
  arr(cfg.attributes).forEach((a) => add("attribute", a.code, a));
  arr(cfg.products).forEach((p) => add("product", p.code, p));
  const resources = new Map();
  arr(cfg.products).forEach((p) => { if (p.resource && p.resource.code) resources.set(p.resource.code, { ...p.resource, name: p.resource.name || `${p.name} Checks`, product: p.code }); });
  resources.forEach((r, code) => add("resource", code, r));
  const units = cfg.units || {};
  if (units.class) add("uomclass", units.class.code, units.class);
  arr(units.members).forEach((u) => add("uom", u.code, u));
  const catByName = new Map(arr(cfg.categories).map((c) => [c.name, c.code]));
  const edgeMap = new Map();
  const link = (type, from, to) => {
    if (!nodes.has(from) || !nodes.has(to)) return;
    const k = `${type}|${from}|${to}`;
    if (!edgeMap.has(k)) edgeMap.set(k, { id: k, type, from, to, count: 0 });
    edgeMap.get(k).count += 1;
  };
  arr(cfg.rate_cards).forEach((r) => link("link", `pricebook:${pb.code}`, `ratecard:${r.code}`));
  arr(cfg.categories).forEach((c) => link("member", `catalog:${(cfg.catalog || {}).code || "CATALOG"}`, `category:${c.code}`));
  const ratesByProduct = new Map();
  const ratesByCard = new Map();
  const push = (m, k, v) => { if (!m.has(k)) m.set(k, []); m.get(k).push(v); };
  const cardCurrency = new Map(arr(cfg.rate_cards).map((r) => [r.code, r.currency]));
  arr(cfg.rates).forEach((r) => {
    const cur = (cardCurrency.get(r.rate_card) || "").toLowerCase();
    link(cur === "usd" ? "usd" : cur === "eur" ? "eur" : "usd", `ratecard:${r.rate_card}`, `product:${r.product}`);
    push(ratesByProduct, `product:${r.product}`, r);
    push(ratesByCard, `ratecard:${r.rate_card}`, r);
  });
  arr(cfg.products).forEach((p) => {
    const cat = catByName.get(p.category) || p.category;
    link("feed", `category:${cat}`, `product:${p.code}`);
    if (p.resource) link("feed", `product:${p.code}`, `resource:${p.resource.code}`);
    arr(p.attributes).forEach((a) => link("attr", `attribute:${a}`, `product:${p.code}`));
    arr(p.components).forEach((c) => link("calc", `product:${p.code}`, `product:${c}`));
  });
  resources.forEach((r, code) => { if (r.unit) link("unit", `resource:${code}`, `uom:${r.unit}`); });
  if (units.class) arr(units.members).forEach((u) => link("member", `uom:${u.code}`, `uomclass:${units.class.code}`));
  const edges = [...edgeMap.values()];
  const fwd = new Map(); const back = new Map();
  edges.forEach((e) => { push(fwd, e.from, e.to); push(back, e.to, e.from); });
  const org = cfg.org || {};
  const orgOf = (node) => {
    if (!node) return null;
    return org[node.key] || null;
  };
  return { cfg, nodes, edges, fwd, back, ratesByProduct, ratesByCard, cardCurrency, org, orgOf };
}
const COLS = {
  pricebook:    { x: 0,    w: 170, h: 88, gap: 10 },
  sellingmodel: { x: 0,    w: 170, h: 78, gap: 10 },
  ratecard:     { x: 214,  w: 220, h: 88, gap: 10 },
  catalog:      { x: 478,  w: 190, h: 70, gap: 10 },
  category:     { x: 478,  w: 190, h: 60, gap: 8 },
  attribute:    { x: 478,  w: 190, h: 78, gap: 10 },
  product:      { x: 740,  w: 350, h: 30, gap: 4 },
  resource:     { x: 1130, w: 240, h: 30, gap: 4 },
  uom:          { x: 1410, w: 130, h: 60, gap: 10 },
  uomclass:     { x: 1410, w: 130, h: 70, gap: 10 },
};
const STAGE_W = 1540;
const HEAD_H = 36;
const RATE_CORRIDOR = COLS.category.x + COLS.category.w + 16;   // rate wires run here, right of the category column
const BUNDLE_CORRIDOR = COLS.product.x - 16;                    // bundle -> component loops run here
function layout(model) {
  const { nodes, edges } = model;
  const ofKind = (k) => [...nodes.values()].filter((n) => n.kind === k);
  const label = (n) => (n.data.name || n.key || "").toLowerCase();
  const categories = ofKind("category");
  const catOrder = new Map(categories.map((c, i) => [c.id, i]));
  const products = ofKind("product");
  const catOf = (p) => edges.find((e) => e.type === "feed" && e.to === p.id && e.from.startsWith("category:"));
  products.sort((a, b) => {
    const ca = catOf(a), cb = catOf(b);
    const ia = ca ? catOrder.get(ca.from) : 1e6, ib = cb ? catOrder.get(cb.from) : 1e6;
    return ia - ib || Number(a.data.kind === "bundle") - Number(b.data.kind === "bundle");
  });
  const prodIndex = new Map(products.map((p, i) => [p.id, i]));
  const resources = ofKind("resource");
  const firstProd = (r) => { const u = edges.filter((e) => e.type === "feed" && e.to === r.id).map((e) => prodIndex.get(e.from)); return u.length ? Math.min(...u) : 1e6; };
  resources.sort((a, b) => firstProd(a) - firstProd(b) || label(a).localeCompare(label(b)));
  const pos = new Map();
  const stack = (kind, list, y0) => {
    const c = COLS[kind];
    list.forEach((n, i) => pos.set(n.id, { x: c.x, y: y0 + i * (c.h + c.gap), w: c.w, h: c.h }));
    return list.length ? y0 + list.length * (c.h + c.gap) - c.gap : y0;
  };
  const pbBottom = stack("pricebook", ofKind("pricebook"), 0);
  const smBottom = stack("sellingmodel", ofKind("sellingmodel"), pbBottom + 20);
  const rcBottom = stack("ratecard", ofKind("ratecard"), 0);
  const catBottom = stack("catalog", ofKind("catalog"), 0);
  const categoriesBottom = stack("category", categories, catBottom + 14);
  const attrBottom = stack("attribute", ofKind("attribute"), categoriesBottom + 20);
  const productsBottom = stack("product", products, 0);
  const resourcesBottom = stack("resource", resources, 0);
  const uomClassBottom = stack("uomclass", ofKind("uomclass"), 0);
  const uomBottom = stack("uom", ofKind("uom"), uomClassBottom + 14);
  const panelTop = Math.max(pbBottom, smBottom, rcBottom, attrBottom) + 26;
  const height = Math.max(productsBottom, resourcesBottom, uomBottom, panelTop + 460) + 24;
  const curve = (x1, y1, x2, y2) => { const dx = Math.max(18, (x2 - x1) / 2); return `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`; };
  const paths = edges.map((e) => {
    const a = pos.get(e.from); const b = pos.get(e.to);
    let d;
    if (e.type === "usd" || e.type === "eur") {
      const y = a.y + a.h / 2;
      d = `M${a.x + a.w} ${y} H${RATE_CORRIDOR} ${curve(RATE_CORRIDOR, y, b.x, b.y + b.h / 2).replace(/^M[\d.]+ [\d.]+ /, "")}`;
    } else if (e.type === "calc") {
      // bundle -> component: out to a corridor left of the product column and back in
      const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2, cx = BUNDLE_CORRIDOR;
      d = `M${a.x} ${y1} C${cx} ${y1} ${cx} ${y2} ${b.x} ${y2}`;
    } else if (e.type === "member" && e.from.startsWith("uom:")) {
      // unit -> class, both in the right-most column: short vertical hook
      const x = a.x + a.w / 2, cx = a.x + a.w + 16;
      d = `M${a.x + a.w} ${a.y + a.h / 2} C${cx} ${a.y + a.h / 2} ${cx} ${b.y + b.h / 2} ${b.x + b.w} ${b.y + b.h / 2}`;
    } else if (e.type === "member") {
      d = curve(a.x + a.w * 0.5, a.y + a.h, b.x + b.w * 0.5 - 1, b.y).replace(/C[^ ]+ [^ ]+ [^ ]+ [^ ]+/, (m) => m);
      const x1 = a.x + 16, x2 = b.x + 16;
      d = `M${x1} ${a.y + a.h} L${x2} ${b.y}`;
    } else {
      d = curve(a.x + a.w, a.y + a.h / 2, b.x, b.y + b.h / 2);
    }
    return { ...e, d };
  });
  const order = { usd: 0, eur: 0, feed: 1, unit: 1, member: 1, link: 2, attr: 3, calc: 4 };
  paths.sort((a, b) => order[a.type] - order[b.type]);
  const counts = {};
  Object.keys(COLS).forEach((k) => { counts[k] = ofKind(k).length; });
  const ordered = [...nodes.values()].sort((a, b) => pos.get(a.id).x - pos.get(b.id).x || pos.get(a.id).y - pos.get(b.id).y);
  return { pos, paths, height, panelTop, counts, ordered };
}
function rateSummary(model, productId) {
  const rows = model.ratesByProduct.get(productId) || [];
  const byCur = {};
  rows.forEach((r) => {
    const cur = model.cardCurrency.get(r.rate_card) || "?";
    if (!byCur[cur]) byCur[cur] = new Set();
    byCur[cur].add(r.rate);
  });
  return Object.entries(byCur).map(([cur, set]) => {
    const vals = [...set].sort((a, b) => a - b);
    return { cur, text: vals.length === 1 ? money(vals[0], cur) : `${money(vals[0], cur)}–${money(vals[vals.length - 1], cur)}`, contract: rows.some((r) => r.contract) };
  });
}
function Rate({ parts }) {
  if (!parts.length) return h("span", { className: "rate rate-none" }, "not priced");
  return h("span", { className: "rate" }, parts.map((p) => h("b", { key: p.cur, className: p.cur.toLowerCase(), title: `${p.cur} rate card${p.contract ? " (contract price, observed on the account)" : ""}` }, p.text)));
}
function NodeBody({ node, model, mode }) {
  const d = node.data;
  const primary = mode === "code" ? d.code || d.name : d.name || d.code;
  const built = !!model.orgOf(node);
  if (node.kind === "product") {
    const parts = rateSummary(model, node.id);
    const rateChars = parts.reduce((n, p) => n + p.text.length + 1, 0) || 10;
    const room = Math.floor((COLS.product.w - 28 - rateChars * 7.2) / 6.8);
    return h(React.Fragment, null, h("span", { className: `row-label ${built ? "built" : ""} ${mode === "code" ? "mono" : ""}` }, mode === "code" ? midTrunc(primary, room) : midTrunc(primary, room + 4)), h(Rate, { parts }));
  }
  if (node.kind === "resource") {
    const room = Math.floor((COLS.resource.w - 20) / 6.8);
    return h("span", { className: `row-label ${built ? "built" : ""} ${mode === "code" ? "mono" : ""}` }, midTrunc(primary, room));
  }
  let meta = "";
  if (node.kind === "pricebook") meta = `${plural(arr(model.cfg.rate_cards).length, "rate card")}, ${plural(arr(model.cfg.products).length, "entry", "entries")} at 0.00`;
  else if (node.kind === "sellingmodel") meta = `on all ${plural(arr(model.cfg.products).length, "product")}`;
  else if (node.kind === "ratecard") { const n = new Set((model.ratesByCard.get(node.id) || []).map((r) => r.product)).size; meta = `${d.currency}, ${d.type || ""} · ${plural(n, "rate")}`; }
  else if (node.kind === "catalog") meta = plural(arr(model.cfg.categories).length, "category", "categories");
  else if (node.kind === "category") meta = plural((model.fwd.get(node.id) || []).length, "product");
  else if (node.kind === "attribute") meta = `on ${plural((model.fwd.get(node.id) || []).length, "product")}` + (d.priced_today === false ? ", not priced" : "");
  else if (node.kind === "uom") meta = plural((model.back.get(node.id) || []).filter((x) => x.startsWith("resource:")).length, "resource");
  else if (node.kind === "uomclass") meta = plural((model.back.get(node.id) || []).length, "unit");
  return h(React.Fragment, null, h("span", { className: `card-name ${built ? "built" : ""}` }, d.name || d.code), h("span", { className: "mono card-code" }, d.code || ""), h("span", { className: "card-meta" }, meta));
}
function FieldList({ rows }) {
  if (!rows.length) return null;
  return h("dl", { className: "fields" }, rows.map(([k, v]) => h(React.Fragment, { key: k }, h("dt", { className: "mono" }, k), h("dd", null, v))));
}
function NodeLink({ id, model, onSelect }) {
  const n = model.nodes.get(id);
  if (!n) return h("span", null, id.split(":").slice(1).join(":"));
  return h("button", { type: "button", className: "link", onClick: () => onSelect(id) }, n.data.name || n.key);
}
function OrgBox({ node, model, extra }) {
  const o = model.orgOf(node);
  if (!o) return h("p", { className: "org none" }, "Not yet built in m3ter-arm-260.");
  return h("p", { className: "org" }, "In m3ter-arm-260: ", h("span", { className: "mono" }, o.id), o.status ? ` (${o.status})` : "", o.link ? h(React.Fragment, null, ", price book link ", h("span", { className: "mono" }, o.link)) : null, o.pbe ? h(React.Fragment, null, ", price book entry ", h("span", { className: "mono" }, o.pbe)) : null, extra || null);
}
function RateTable({ rows, model, show, onSelect }) {
  if (!rows.length) return h("p", { className: "quiet" }, "No rates.");
  const name = (id) => { const n = model.nodes.get(id); return n ? (n.data.name || n.key).toLowerCase() : id; };
  const sorted = [...rows].sort((a, b) => show === "product" ? name(`product:${a.product}`).localeCompare(name(`product:${b.product}`)) : (a.rate_card || "").localeCompare(b.rate_card || "") || (a.segment || "").localeCompare(b.segment || ""));
  const hasSeg = sorted.some((r) => r.segment);
  const card = (code) => model.nodes.get(`ratecard:${code}`);
  return h("table", { className: "grid" }, h("thead", null, h("tr", null, show === "product" && h("th", null, "Product"), show === "card" && h("th", null, "Rate card"), hasSeg && h("th", null, "Attribute value"), h("th", { className: "num" }, "Rate"), h("th", null, "Effective from"), h("th", null, "Status"))), h("tbody", null, sorted.map((r, i) => {
    const c = card(r.rate_card) || { data: {} };
    const o = model.org[`RCE:${r.rate_card}:${r.product}`];
    const cls = o ? "live" : r.contract ? "idle" : "";
    return h("tr", { key: i, className: cls }, show === "product" && h("td", null, h(NodeLink, { id: `product:${r.product}`, model, onSelect })), show === "card" && h("td", null, h(NodeLink, { id: `ratecard:${r.rate_card}`, model, onSelect })), hasSeg && h("td", { className: "mono" }, r.segment || ""), h("td", { className: "num" }, money(r.rate, c.data.currency || "USD")), h("td", { className: "nowrap" }, fmtDate(c.data.effective_from) || ""), h("td", { className: "nowrap" }, o ? `Built, ${o.status}` : r.contract ? "Contract price, not catalog" : "Recommended"));
  })));
}
function Overview({ model }) {
  const { cfg } = model;
  const products = arr(cfg.products);
  const bundles = products.filter((p) => p.kind === "bundle");
  const built = products.filter((p) => model.org[p.code]).length;
  const sections = Object.entries(KINDS).map(([k, v]) => [v.many, k]);
  return h("div", null, h("h2", null, "How this is priced"),
    h("p", { className: "prose" }, "One ", h("strong", null, "Standard Price Book"), " carries ", plural(arr(cfg.rate_cards).length, "rate card"), " (", arr(cfg.rate_cards).map((r) => r.currency).join(" and "), "). Every product has a 0.00 price book entry so it can be quoted, and the real per-check rate sits on a rate card entry per currency — one flat rate, no tiers. Usage arrives on the product's usage resource, in the unit the resource names, and is rated at that entry."),
    h("p", { className: "prose" }, plural(products.length - bundles.length, "product"), " come 1:1 from m3ter meters; ", plural(bundles.length, "bundle"), " come from m3ter compound aggregations and are products of their own with their own resource, because Revenue Cloud cannot rate max() of two resources (decision D3). The dashed amber lines show which component products a bundle stands in for."),
    h("p", { className: "prose" }, built ? `${built} of ${products.length} products are built in m3ter-arm-260 (green dot); the rest are the recommendation.` : "Nothing in this file has been built in an org yet."),
    h("p", { className: "quiet" }, "Select any box to trace what it connects to and see its fields."),
    h("h3", null, "In this file"),
    h("table", { className: "grid tight" }, h("thead", null, h("tr", null, h("th", null, "Drawn as"), h("th", { className: "num" }, "Boxes"), h("th", null, "Revenue Cloud records it stands for"))), h("tbody", null, sections.map(([title, k]) => h("tr", { key: k }, h("td", null, title), h("td", { className: "num" }, [...model.nodes.values()].filter((n) => n.kind === k).length), h("td", { className: "quiet" }, KINDS[k].sobjects))), h("tr", null, h("td", null, "Rates (coloured lines)"), h("td", { className: "num" }, arr(cfg.rates).length), h("td", { className: "quiet" }, "RateCardEntry")))),
    arr(cfg.open_questions).length > 0 && h(React.Fragment, null, h("h3", null, "Open questions"), h("ul", null, cfg.open_questions.map((q, i) => h("li", { key: i, className: "prose", style: { margin: "4px 0" } }, typeof q === "string" ? q : Object.entries(q).map(([k, v]) => h(React.Fragment, { key: k }, h("strong", null, k), ": ", String(v))))))));
}
function Detail({ id, model, onSelect }) {
  const node = model.nodes.get(id);
  const d = node.data;
  const out = (type) => model.edges.filter((e) => e.type === type && e.from === id).map((e) => e.to);
  const into = (type) => model.edges.filter((e) => e.type === type && e.to === id).map((e) => e.from);
  const links = (ids) => ids.map((x, i) => h(React.Fragment, { key: x }, i > 0 && ", ", h(NodeLink, { id: x, model, onSelect })));
  const cfg = model.cfg;
  return h("div", null,
    h("div", { className: "detail-head" }, h("h2", null, d.name || node.key), h("button", { type: "button", className: "ghost", onClick: () => onSelect(null) }, "Clear selection")),
    h("p", { className: "detail-kind" }, KINDS[node.kind].title, " ", h("span", { className: "mono" }, d.code || node.key), " · ", h("span", { className: "quiet" }, KINDS[node.kind].sobjects)),
    h(OrgBox, { node, model }),
    node.kind === "product" && h(React.Fragment, null,
      h("p", { className: "prose" }, d.kind === "bundle" ? h(React.Fragment, null, "A bundle product: m3ter computes ", h("span", { className: "mono" }, d.m3ter_compound_aggregation), " and sends one usage record against the bundle's own resource ", links(out("feed").filter((x) => x.startsWith("resource:"))), ". Stands in for ", links(out("calc")), ", which are rated at 0 under the contract.") : h(React.Fragment, null, "Usage comes from the m3ter meter ", h("span", { className: "mono" }, d.m3ter_meter), " via aggregation ", h("span", { className: "mono" }, d.m3ter_aggregation), " onto the resource ", links(out("feed").filter((x) => x.startsWith("resource:"))), "."), " In category ", links(into("feed")), ".", into("attr").length > 0 && h(React.Fragment, null, " Carries the attribute ", links(into("attr")), " (both values priced the same today, so no adjustment rule)."), into("calc").length > 0 && h(React.Fragment, null, " Absorbed by the bundle ", links(into("calc")), " on accounts that have it.")),
      d.m3ter_calculation && h("pre", { className: "calc" }, d.m3ter_calculation),
      d.anomaly && h("p", { className: "error", role: "note", style: { marginTop: 12 } }, d.anomaly),
      h("h3", null, "Rates"), h(RateTable, { rows: model.ratesByProduct.get(id) || [], model, show: "card", onSelect }),
      h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d, ["m3ter_calculation", "anomaly", "components", "attributes", "kind"]) })),
    node.kind === "ratecard" && h(React.Fragment, null,
      h("p", { className: "prose" }, "Hangs off ", links(into("link")), " through a PriceBookRateCard. Rates are expressed in the ", h("span", { className: "mono" }, d.rate_unit), " unit of measure. m3ter plan template ", h("span", { className: "mono" }, d.m3ter_plan_template), d.m3ter_bill_frequency ? ` (${d.m3ter_bill_frequency})` : "", "."),
      h("h3", null, "Rate card entries"), h(RateTable, { rows: model.ratesByCard.get(id) || [], model, show: "product", onSelect }),
      d.history_not_loaded && h(React.Fragment, null, h("h3", null, "Older price versions (not loaded, decision D5)"), h("table", { className: "grid tight" }, h("thead", null, h("tr", null, h("th", null, "Period"), h("th", { className: "num" }, "Products priced"))), h("tbody", null, Object.entries(d.history_not_loaded).map(([k, v]) => h("tr", { key: k, className: "idle" }, h("td", null, k), h("td", { className: "num" }, Object.keys(v || {}).length)))))),
      h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d, ["history_not_loaded"]) })),
    node.kind === "pricebook" && h(React.Fragment, null, h("p", { className: "prose" }, d.note), h("p", { className: "prose" }, "Rate cards: ", links(out("link")), "."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d, ["note"]) })),
    node.kind === "sellingmodel" && h(React.Fragment, null, h("p", { className: "prose" }, d.why || ""), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "catalog" && h(React.Fragment, null, h("p", { className: "prose" }, "Categories: ", links(out("member")), "."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "category" && h(React.Fragment, null, h("p", { className: "prose" }, "Products: ", links(out("feed")), "."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "attribute" && h(React.Fragment, null, h("p", { className: "prose" }, "From the m3ter WHAT field ", h("span", { className: "mono" }, d.m3ter_field), ". Attached to ", links(out("attr")), " through the classification. ", d.priced_today === false ? "Both values are priced identically today, so no AttributeBasedAdjRule exists (decision D2)." : ""), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "resource" && h(React.Fragment, null, h("p", { className: "prose" }, "Receives usage for ", links(into("feed")), ", measured in ", links(out("unit")), "."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "uom" && h(React.Fragment, null, h("p", { className: "prose" }, "Used by ", links(into("unit")), ". In the class ", links(out("member")), "."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })),
    node.kind === "uomclass" && h(React.Fragment, null, h("p", { className: "prose" }, "Units: ", links(into("member")), ". Draft-only on create; activate after its default unit exists."), h("h3", null, "Fields"), h(FieldList, { rows: flatFields(d) })));
}
function trace(model, sel) {
  const walk = (adj) => { const seen = new Set([sel]); const todo = [sel]; while (todo.length) { (adj.get(todo.pop()) || []).forEach((m) => { if (!seen.has(m)) { seen.add(m); todo.push(m); } }); } return seen; };
  return { up: walk(model.back), down: walk(model.fwd) };
}
function App({ initial, initialName }) {
  const [cfg, setCfg] = useState(initial);
  const [fileName, setFileName] = useState(initialName);
  const [sel, setSel] = useState(null);
  const [mode, setMode] = useState("name");
  const [error, setError] = useState(null);
  const [view, setView] = useState({ w: window.innerWidth, h: window.innerHeight });
  const fileInput = useRef(null);
  const model = useMemo(() => buildModel(cfg), [cfg]);
  const lay = useMemo(() => layout(model), [model]);
  const lit = useMemo(() => sel && model.nodes.has(sel) ? trace(model, sel) : null, [model, sel]);
  useEffect(() => {
    const onResize = () => setView({ w: window.innerWidth, h: window.innerHeight });
    const onKey = (e) => { if (e.key === "Escape") setSel(null); };
    window.addEventListener("resize", onResize); window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("resize", onResize); window.removeEventListener("keydown", onKey); };
  }, []);
  const title = (cfg.catalog && cfg.catalog.name) || "Revenue Cloud catalog";
  useEffect(() => { document.title = `${title} — Revenue Cloud structure`; }, [title]);
  const zoom = Math.min(1, Math.max(0.72, (view.w - 48) / STAGE_W));
  const openFile = (e) => {
    const file = e.target.files && e.target.files[0]; e.target.value = ""; if (!file) return;
    file.text().then((text) => {
      let next; try { next = JSON.parse(text); } catch (err) { setError(`${file.name} isn't valid JSON, so nothing was loaded.`); return; }
      if (!next || typeof next !== "object" || !Array.isArray(next.products)) { setError(`${file.name} has no products array, so nothing was loaded. The page expects the JSON shape of its own config-data block (built from the recommendation YAML by models/build_structure_chart.py).`); return; }
      setError(null); setSel(null); setCfg(next); setFileName(file.name);
    });
  };
  const isLit = (id) => !lit || lit.up.has(id) || lit.down.has(id);
  const edgeLit = (e) => !lit || lit.up.has(e.from) && lit.up.has(e.to) || lit.down.has(e.from) && lit.down.has(e.to);
  const products = arr(cfg.products);
  const nProd = products.filter((p) => p.kind !== "bundle").length, nBundle = products.length - nProd;
  const line = (cls) => h("svg", { width: "28", height: "8", "aria-hidden": "true" }, h("path", { d: "M0 4H28", className: `edge ${cls}` }));
  const colHeads = [["pricebook", "Price book"], ["ratecard", "Rate cards"], ["catalog", "Catalog & categories"], ["product", "Products"], ["resource", "Usage resources"], ["uom", "Units"]];
  return h("div", { className: "page" },
    h("header", { className: "top" },
      h("div", { className: "top-title" }, h("h1", null, title), h("span", { className: "mono top-code" }, "Revenue Cloud"), h("p", null, "How the Revenue Cloud catalog in ", h("span", { className: "mono" }, fileName), " fits together: ", plural(arr(cfg.rates).length, "rate"), " on ", plural(arr(cfg.rate_cards).length, "rate card"), " pricing ", plural(nProd, "product"), nBundle ? ` and ${plural(nBundle, "bundle")}` : "", ", each metered on its own usage resource.")),
      h("div", { className: "top-tools" },
        h("ul", { className: "legend", "aria-label": "What the lines mean" },
          h("li", null, line("usd"), "USD rate card entry"), h("li", null, line("eur"), "EUR rate card entry"), h("li", null, line("calc"), "Bundle stands in for"), h("li", null, line("attr"), "Attribute on product"),
          h("li", null, h("span", { className: "built" }), "Built in m3ter-arm-260")),
        h("div", { className: "controls" },
          h("div", { className: "seg", role: "group", "aria-label": "Label boxes with" }, h("button", { type: "button", "aria-pressed": mode === "name", onClick: () => setMode("name") }, "Names"), h("button", { type: "button", "aria-pressed": mode === "code", onClick: () => setMode("code") }, "Codes")),
          h("button", { type: "button", className: "ghost", onClick: () => fileInput.current.click() }, "Open another config"),
          h("input", { ref: fileInput, type: "file", accept: ".json,application/json", hidden: true, onChange: openFile })))),
    error && h("p", { className: "error", role: "alert" }, error),
    h("div", { className: "canvas", style: { width: STAGE_W, zoom } },
      h("div", { className: "col-heads", style: { height: HEAD_H } }, colHeads.map(([kind, t]) => h("span", { key: kind, style: { left: COLS[kind].x, width: COLS[kind].w } }, t, kind === "product" && h("i", null, products.length), kind === "resource" && h("i", null, lay.counts.resource)))),
      h("div", { className: `stage ${lit ? "tracing" : ""}`, style: { height: lay.height } },
        h("svg", { className: "wires", width: STAGE_W, height: lay.height, "aria-hidden": "true" }, lay.paths.map((e) => h("path", { key: e.id, d: e.d, className: `edge ${e.type} ${edgeLit(e) ? "lit" : ""}` }))),
        lay.ordered.map((n) => {
          const p = lay.pos.get(n.id);
          const shape = n.kind === "product" || n.kind === "resource" ? "row" : "card";
          return h("button", { key: n.id, type: "button", className: `node ${shape} k-${n.kind} ${n.data.kind === "bundle" ? "bundle" : ""} ${isLit(n.id) ? "lit" : ""} ${sel === n.id ? "sel" : ""}`, style: { left: p.x, top: p.y, width: p.w, height: p.h }, "aria-pressed": sel === n.id, title: `${KINDS[n.kind].title}: ${n.data.name || n.key}${n.data.code ? ` (${n.data.code})` : ""}`, onClick: () => setSel(sel === n.id ? null : n.id) }, h(NodeBody, { node: n, model, mode }));
        }),
        h("div", { className: "panel-slot", style: { top: lay.panelTop, width: COLS.category.x + COLS.category.w } },
          h("section", { className: "panel", style: { top: HEAD_H + 10, maxHeight: view.h / zoom - HEAD_H - 34 }, "aria-live": "polite" },
            sel && model.nodes.has(sel) ? h(Detail, { id: sel, model, onSelect: setSel }) : h(Overview, { model }))))));
}
const embedded = JSON.parse(document.getElementById("config-data").textContent);
ReactDOM.createRoot(document.getElementById("root")).render(h(App, { initial: embedded, initialName: document.getElementById("config-data").dataset.name }));
"""

config_json = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
script_name = Path(__file__).name
html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revenue Cloud config structure</title>
<style>
{fonts}{CSS}
</style>
</head>
<body>
<div id="root"></div>
<!-- The config this chart draws: built from {src.name} by {script_name}. "Open another config" swaps it for a JSON file of the same shape. -->
<script id="config-data" type="application/json" data-name="{src.name}">{config_json}</script>
{react}
<script>
{APP_JS}
</script>
</body>
</html>
"""
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size:,} bytes): {len(products)} products, {len(rates)} rates, {len(data['rate_cards'])} rate cards")
