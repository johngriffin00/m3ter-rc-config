# CLAUDE.md

Working instructions for Claude sessions on `m3ter-rc-config`.

**`README.md` is the single source of truth.** This file is short: how to behave in
this repo, not how the project works. If the two disagree, the README wins and this
file gets fixed.

---

## Start of every session

1. Ask for access to the three repo folders on John's Mac (and delete permission, which
   git needs for its lock files): `~/PycharmProjects/m3ter-rc-config`,
   `~/PycharmProjects/m3ter-config`, `~/PycharmProjects/revenue-cloud-config`.
2. `git status` in all three; report anything uncommitted or out of sync. Pushing goes
   through the bundle route in `m3ter-config/README.md` § "How Claude gets access":
   commit on the Mac, bundle, push from the cloud session's clone, `git update-ref` on
   the Mac.
3. Read this README's "Status". The platform knowledge lives in the tool repos' READMEs
   (`revenue-cloud-config` for anything Salesforce, `m3ter-config` for anything m3ter) —
   read the relevant one before touching that side; don't re-derive it here.

Work in the Mac shell directly on the repos; stage files into the cloud container only
for a step the Mac shell can't do. Never create a `.venv` inside a mounted repo from the
Linux shell (it would be the wrong platform for the Mac) — use `UV_PROJECT_ENVIRONMENT`
pointing outside the mount.

---

## Non-negotiable rules

**This repo owns the loop and the customers; the tools own the platforms.** A fix the
tools need is made in the tool repo, with its tests, and used from here. Customer-specific
anything (config, mapping, docs, snapshots) goes under `customers/<name>/`, never into a
tool repo.

**Never commit secrets.** `parameters/` and anything `*.env`, `token.json`, `*.pickle`.
Snapshots of org dumps are checked before commit for keys.

**Teaching mode for the syncs.** John wants to understand the script, not receive it.
Plan together first, agree the step list, build one brick at a time, explain the m3ter and
Revenue Cloud objects involved and why the order matters, dry-run, run, re-run, then
commit. Ask before moving to the next brick.

**Never guess an identifier** on either platform — Salesforce field names, picklist values
and Ids, or m3ter codes and ids. Look them up (SOQL/describe via the RC tool, `m3sdk` list
calls, or the local Postgres).

**Commit and push as you go.** Small commits that say what and why. Author is
`John Griffin <43268018+johngriffin00@users.noreply.github.com>`. Don't rewrite history
without asking.

**Say what was tested and how.** "Passes offline against the snapshot" and "verified
against the org" are different claims.

**Update the README before closing a session.** Anything left only in a transcript is lost.

---

## Environment

| | |
|---|---|
| Python | ≥ 3.14, `uv`; `uv sync --extra dev` installs both tools editable from the sibling checkouts |
| m3ter creds | `parameters/<org>.env` → `ENVIRONMENT`, `ORGANIZATION`, `apiKey`, `apiSecret` |
| Salesforce | org alias `m3ter` (`admin@m3ter-arm.260`), REST API v66.0 |
| Postgres | local `customerdb`, schema `entrust` (camelCase columns, quote them) |

---

## Current state

**20 Oct 2026.** Phases 1–3 of `docs/restructure-plan.md` done: the syncs live and
run here (`sync/ordersync`, `sync/billsync`, shared bricks in `sync/core`), with the
Salesforce SDK and the Entrust snapshots; `uv run pytest` replays both offline. They
have not yet been run live from this repo. The Entrust catalog, docs and analysis still
live in `revenue-cloud-config` (phase 4 next); `mapping.py` is still module-level
(phase 6). Parked work on the syncs, carried over unchanged: commitment as a m3ter
Balance, the Commit card's tiers, amendments, the Flask front doors, a granted
entitlement, the null `GrantBindingTargetId` on the six first UsageSummaries — all in
`customers/entrust/DECISIONS.md`.
