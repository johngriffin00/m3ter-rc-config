# The m3ter config

Applied with the m3ter tool's `create_config.py`, which takes the file path(s) as arguments
(run from the `m3ter-config` checkout, with that org's `parameters/<org>.env` loaded):

```bash
uv run demoscripts/create_config.py ../m3ter-rc-config/customers/entrust/m3ter/document-check-config-vertical-slice.json
```

| File | What |
| --- | --- |
| `document-check-config-vertical-slice.json` | the Document Check slice the order sync attaches to: product `verification_check`, the three meters and aggregations (segmented on country), plan template `usd_default_pricing` with its list-price pricings |
| `foris-config.json` | the Foris account's full config |
| `test.json` | a one-product smoke test |

Dumps of accounts as they stand in m3ter (`generate_json_from_existing_org.py`) and their
structure charts are in `../snapshots/m3ter/`, not here: they are what the org held, not what
to apply.
