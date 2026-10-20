# Restructuring plan — three repos, one loop

20 October 2026 · John Griffin, with Claude · status: agreed 20 Oct; phases 1–4 done (4b: the m3ter-side Entrust config, pending), phase 5 next

## The decision

Keep the two platform repos as **tools**. Create this repo, `m3ter-rc-config`, for the
layer that is cross-cutting — the **integration** (the quote → order → m3ter → bill →
liable summary → invoice loop) — with each customer as a folder inside it.

| Repo | Role after the move | Depends on |
| --- | --- | --- |
| `m3ter-config` | m3ter SDK (`m3sdk`), m3sh SDK (`m3shsdk`), the generic config/usage scripts, the library of m3ter-only customer JSON | — |
| `revenue-cloud-config` | `rc-config` tool, simulated org, platform docs (pcm, pricing, rate-usage, billing chain, data models) | — |
| `m3ter-rc-config` | the sync code, the Salesforce SDK the syncs use, the webhook front doors, and `customers/<name>/` with that customer's m3ter config, Revenue Cloud config, mapping bricks, snapshots, analysis and docs | both tools, as editable path dependencies |

Why not one super project: the tools have separate test suites, auth, lifecycles and
landmine knowledge; merging buys only "no switching" and costs a giant context for every
session and a blurred line between "the tool is wrong" and "this customer's config is
wrong". The pain was never the separation — it was the integration having no home.

Why the customer is a folder, not a repo: the sync code and the loop are the same for
every customer; only `mapping.py`/`policy.py`, the configs and the docs change (the
bill-sync design already says `mapping.py` is "the only catalog-specific brick").

Rule for where a customer lives: **a customer that spans both platforms lives here**;
an m3ter-only customer stays in `m3ter-config/json/<name>/`.

## Target layout

```
m3ter-rc-config/
  README.md                 single source of truth (as in the other two repos)
  CLAUDE.md                 session rules; "Current state" for the syncs moves here
  pyproject.toml            deps: m3ter-config + revenue-cloud-config (editable, ../),
                            simple-salesforce, flask, python-dotenv, requests
  parameters/               gitignored; m3ter.env etc. (copy, not shared)
  sync/
    core/                   context.py, step.py, dates.py, sf_step.py  (shared bricks)
    ordersync/              sf_order.py, step_account/plan/pricing/accountplan.py, sync_order.py
    billsync/               read_bill.py, resolve.py, step_usagesummary/ratablesummary/ubpi/link.py, sync_bill.py
  salesforcesdk/            moved from m3ter-config (only the syncs use it)
  webhooks/                 app.py + handlerRC / handlerSalesforce* (the Flask front doors)
  customers/
    entrust/
      README.md             the customer's loop in one page; links to everything below
      DECISIONS.md          the one open-questions / decision log (card selection, parent vs
                            child bucket, region bands, commitment as Balance, status on create…)
      mapping.py, policy.py the customer's bricks (phase 2: loaded by --customer entrust)
      m3ter/                json/entrust/*.json configs (foris-config, document-check vertical slice…)
      revenue-cloud/        config/entrust/*.json + catalog.toml + build_config.py (+ archive/)
      m3sh/                 json/entrust/m3sh/ exports + workflows/entrust/ decompiled DSL
      snapshots/            orders/00000102.json, bills/…, m3ter org dumps (001Ws…-config.json)
      analysis/             verification-catalog/-quoting recommendation YAMLs,
                            m3ter-to-revenue-cloud.md, the two quote-reconstruction xlsx
      docs/                 documents/entrust/ (index, end-to-end-flow, walkthrough, setup guide,
                            order/bill sync designs, m3sh structure pages, requirements PDF)
        archive/            JG Entrust RCA Config.docx (6 Oct), verification-catalog-build-steps.md (7 Oct)
  tests/                    test_entrust.py (generator vs simulated org), sync tests against snapshots
```

## Move list

### Out of `m3ter-config` → here

| From | To | Note |
| --- | --- | --- |
| `demoscripts/ordersync/` | `sync/ordersync/` + `sync/core/` (context, step, dates) | imports `demoscripts.ordersync.step` → `sync.core.step` |
| `demoscripts/billsync/` | `sync/billsync/` (+ `sf_step.py` → `sync/core/`) | billsync reuses ordersync's context/step — now shared in core |
| `salesforcesdk/` | `salesforcesdk/` | used only by the syncs and `test_salesforce_connection.py`; later candidate to merge with `rc_config.client` |
| `demoscripts/test_salesforce_connection.py` | `scripts/` | |
| `handlers/handlerRC.py`, `handlerSalesforce*.py` | `customers/entrust/m3sh/python-handlers/` (reference) | `app.py` is a generic one-handler switch and stays with the other ~17 handlers; the front doors here are written fresh |
| `json/entrust/*.json` (configs, org dumps) | `customers/entrust/m3ter/`, `customers/entrust/snapshots/` | |
| `json/entrust/orders/`, `json/entrust/bills/` | `customers/entrust/snapshots/` | `--from-file` paths change |
| `json/entrust/m3sh/` | `customers/entrust/m3sh/exports/` | |
| `workflows/entrust/` | `customers/entrust/m3sh/dsl/` | depends on `m3shsdk` (stays in the tool); `workflows/probe/` stays |
| `json/entrust/documents/*.html`, `json/entrust/claude-catalog-data-model.html` | drop — duplicates of `documents/entrust/` | |
| README § "Order activation → m3ter sync", § "Bill → Revenue Cloud usage sync" | this README | |
| CLAUDE.md "Teaching mode for the syncs", "Current state" (syncs) | this CLAUDE.md | |

Stays in `m3ter-config`: `m3sdk`, `m3shsdk`, `m3utils`, `demoscripts/create_config.py` /
`delete_config.py` / data generators / `m3sh/` tooling, `structurechart/`, every other
`json/<customer>/`, `parameters/`, `data/`, `webhooks/` for the other customers,
`tests/test_m3sh_*`.

Tool changes needed in `m3ter-config`:
- **Packaging.** Add a build system to `pyproject.toml` with `packages = ["m3sdk", "m3shsdk", "m3utils"]` so `uv add --editable ../m3ter-config` works and `PYTHONPATH=.` is no longer needed by consumers. Rename the project to `m3ter-config` (pyproject still says `m3ter-onboarding-framework-v2`; CLAUDE.md and README still name the old path and GitHub URL; `.idea/*.iml` too).
- **Secrets.** `git rm --cached google/token.json webhooks/token.pickle`, add both to `.gitignore`, rotate the Google OAuth token. (History scrub optional — private repo, one user.)
- Check `create_config.py` / `delete_config.py` accept an arbitrary config path, so a customer's m3ter config can live outside `json/`.

### Out of `revenue-cloud-config` → here

| From | To | Note |
| --- | --- | --- |
| `config/entrust/` (+ `archive/`) | `customers/entrust/revenue-cloud/` | `rc-config … --config-dir customers/entrust/revenue-cloud` |
| `models/build_entrust_config.py` | `customers/entrust/revenue-cloud/build_config.py` | the generator travels with its output |
| `models/build_setup_guide.py` | `customers/entrust/docs/build_setup_guide.py` | reads the config + writes the HTML; both now local |
| `models/build_quoting_recommendation.py`, `verification-*.recommendation.yaml`, `verification-catalog-structure.html`, `m3ter-to-revenue-cloud.md`, both `Entrust quote reconstruction*.xlsx`, `00124000018txRVAAY-structure.html` | `customers/entrust/analysis/` | |
| `documents/entrust/` | `customers/entrust/docs/` (+ `archive/`) | see docs hygiene below |
| `tests/test_entrust.py` | `tests/test_entrust.py` | needs `fake_org` importable — see tool change |
| README § "The Entrust Verification catalog", § "Earlier shapes", the Entrust parts of § "Where we left off" | `customers/entrust/README.md` + `DECISIONS.md` | |
| CLAUDE.md "Current state" (all Entrust) | this CLAUDE.md | leave the RC CLAUDE.md with tool state only |

Stays in `revenue-cloud-config`: `src/rc_config`, `config/claude` (the reference catalog
the tool was built on), `tests/` (fake org and the engine tests), `models/build_billing_data_model.py`
+ `billing-fields.json`, `claude-catalog-data-model.html`, `build_structure_chart.py` +
`structure-chart/`, `documents/{pcm,pricing,rate-usage,billing-usage-to-invoice,deployment,…}.md`,
the handoff notes, `scripts/teardown-after-assetization.apex` (generic once the EDIT lines are
parameters), README landmines / design decisions / troubleshooting.

Tool changes needed in `revenue-cloud-config`:
- Move `tests/fake_org.py` (and the fixture schema) to `src/rc_config/testing/` so the simulated org is importable by this repo's tests.
- Drop the `config/entrust` default/help-text references in `cli.py` / `engine.py`.
- The two generated data-model pages (catalog, billing) are platform knowledge: keep them in `documents/` and regenerate from there; `customers/entrust/docs/index.html` links to them.

### Docs hygiene for `customers/entrust/docs/`

- Mark every page **generated** (setup guide, end-to-end flow, both data models, the two m3sh structure pages — regenerate, never edit) or **hand-written** (walkthrough, designs).
- One source for the walkthrough: keep the `.md`, generate the `.html`.
- `archive/` for the 6 Oct docx and the 7 Oct build steps, each with a one-line "superseded by" note.
- Collapse the open questions repeated across the walkthrough, setup guide, bill-sync design and end-to-end flow into `DECISIONS.md`; each page links to it instead of restating.

## Phases

1. ~~**Hygiene first** (m3ter-config): untrack and rotate the two tokens; rename the project consistently; add packaging. Commit, push.~~ **Done 20 Oct** — `google/token.json`, `webhooks/token.pickle` (and `credentials.json`) scrubbed from all 43 commits with `git filter-repo`, force-pushed; repo renamed consistently; hatchling packaging with `m3sdk`, `m3shsdk`, `m3utils`. Google OAuth grant revocation is John's.
2. ~~**Skeleton here**: `pyproject.toml` with both editable path deps, `README.md`, `CLAUDE.md`, `.gitignore` (`parameters/`, snapshots of org dumps if they hold keys), `git init`, GitHub repo `johngriffin00/m3ter-rc-config`.~~ **Done 20 Oct** — `uv sync` installs both tools editable; `tests/test_skeleton.py` passes; `main` pushed to GitHub.
3. ~~**Move the syncs**: copy `ordersync`, `billsync`, `salesforcesdk`, fix imports to `sync.core.*`, run `sync_order.py --from-file … --dry-run` against the moved snapshot as the proof. Delete from the source repo with a commit that names the destination (history stays readable in the source repo's log; no filter-repo).~~ **Done 20 Oct** — `tests/test_replay.py` replays both syncs offline with stubbed clients; one de-duplication on the way (`BaseSyncContext`, one `dates` module, `soql` helpers). First live run from here still to do.
4. ~~**Move Entrust**: configs, generator, analysis, docs, snapshots, m3sh. Proof: `rc-config check --config-dir customers/entrust/revenue-cloud` and `build_config.py --check` pass; `pytest` here passes with `fake_org` from the tool.~~ **Done 20 Oct for the Revenue Cloud side** — `rc_config.testing` (simulated org + CLI harness) added to the tool; `tests/test_entrust.py` runs here (29 tests with the sync replays); all three generators (`build_config.py`, `build_setup_guide.py`, `build_billing_data_model.py`) reproduce their outputs from the new homes. Deviations from the table above: the two data-model pages and the billing-model generator travel with the doc set (the set's `index.html` links them), and `build_structure_chart.py` + `structure-chart/` go to `analysis/` with the YAML they draw. **4b, still to do:** the m3ter side — `m3ter-config/json/entrust/*.json` → `customers/entrust/m3ter/`, `json/entrust/m3sh/` + `workflows/entrust/` → `customers/entrust/m3sh/` (needs the m3ter tool's `create_config.py` to take a path).
5. **Move the words**: README/CLAUDE sections, then `DECISIONS.md`. Trim the two tool CLAUDE.md "Current state" blocks to tool state.
6. **Phase 2 code change** (after everything works in place): `--customer entrust` loads `customers/entrust/mapping.py` and `policy.py` instead of the module-level import, so a second customer is a folder, not a fork.
7. **Claude Project** "m3ter RC Config": instructions say the platform projects are the experts and this one owns the loop and the customers; add the repo; this plan and `DECISIONS.md` as project docs; skills here call across ("apply the Entrust m3ter config", "run the order sync", "read back the asset") rather than duplicate the platform skills.

## Not changing

Local Postgres `customerdb` / schema `entrust` (referenced from this repo's CLAUDE.md); the
Google Drive `Entrust / m3sh Workflows` folder; org alias `m3ter` and the m3ter org; the
GitHub token/bundle route for pushing from Claude sessions.
