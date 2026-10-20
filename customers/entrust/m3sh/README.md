# The m3sh workflows

| Folder | What |
| --- | --- |
| `exports/` | the twelve workflow JSON exports from the m3sh console (Google Drive `Entrust / m3sh Workflows`): the Order Handler set (`Order_Handler.json` + seven `Order_Step-*.json`) and the "m3ter -> SF RCA Usage Data" set (`m3ter-sf-rca-usage-data*.json`); `exports/README.md` is the Drive folder's note |
| `dsl/` | the Order Handler set decompiled to the `m3shsdk` DSL (`m3ter-config/demoscripts/m3sh/decompile_workflow.py`); `emit_workflow.py` turns them back into JSON |
| `python-handlers/` | the pre-m3sh Python half (`on_bill_change`) that fed the usage-data workflows |

The read-outs of these workflows are `../docs/entrust-order-handler-structure.html` and
`../docs/entrust-usage-data-structure.html`; the Python ports are `sync/ordersync` and
`sync/billsync`. A frozen copy of `exports/` is the m3sh SDK's test corpus in
`m3ter-config/tests/fixtures/m3sh/`.

Round trip, from the `m3ter-config` checkout:

```bash
uv run demoscripts/m3sh/decompile_workflow.py ../m3ter-rc-config/customers/entrust/m3sh/exports/*.json -o ../m3ter-rc-config/customers/entrust/m3sh/dsl
uv run demoscripts/m3sh/emit_workflow.py ../m3ter-rc-config/customers/entrust/m3sh/dsl/order_step_init.py -o out/
```
