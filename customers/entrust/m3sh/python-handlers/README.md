# The Python half of the m3sh usage-data sync (reference, not run)

`handlerRC.py`, `handlerSalesforce.py` and `handlerSalesforceMethod2.py` are the
`on_bill_change` webhook handlers that fed the m3sh "m3ter -> SF RCA Usage Data"
workflows: they read the bill, netted grants and commitments (`apply_grants`,
`apply_commitments`) and posted one entry per USAGE line to the m3sh trigger.
`sync/billsync/` is their port (see `docs/bill-sync-design.html` once the docs
move, and `entrust-usage-data-structure.html`). They were lifted unchanged from
`m3ter-config/webhooks/handlers/` on 20 Oct 2026 and still import that repo's
`google.test_google_email` for the email step, so they do not import here.
