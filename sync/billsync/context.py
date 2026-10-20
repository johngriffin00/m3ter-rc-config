"""The state that travels through the bill-sync steps — the order sync's idea in
the other direction.

  snapshot  what m3ter said — the bill header and ALL of its line items, read once
            by ReadBill and frozen. Every type of line is kept (USAGE_CREDIT,
            OVERAGE_USAGE, BALANCE_CONSUMED, ...) because the netting needs them,
            even though only USAGE lines ever reach Revenue Cloud.
  state     what later steps resolved or created on the Salesforce side.
  log       what happened, in order.

The clients and the log are the shared BaseSyncContext; this adds the bill
reference and the snapshot file naming.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from sync.core.context import SF_API_VERSION, SNAPSHOT_ROOT, BaseSyncContext  # noqa: F401  (SF_API_VERSION re-exported)


@dataclass(kw_only=True)
class BillSyncContext(BaseSyncContext):
    bill_ref: str                       # a Bill id, or an account code/id when latest=True
    latest: bool = False                # bill_ref is an account: take its latest bill

    def save_snapshot(self, directory=SNAPSHOT_ROOT / 'bills') -> Path:
        """<snapshots>/bills/<accountCode>-<billDate>-<bill id>.json — readable
        name first, the id for uniqueness, so a later run can replay it without m3ter."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        bill = self.snapshot['bill']
        path = Path(directory) / f"{bill['accountCode']}-{bill['billDate']}-{bill['id']}.json"
        path.write_text(json.dumps(self.snapshot, indent=2, default=str))
        self.say(f'snapshot written to {path}')
        return path

    @classmethod
    def from_snapshot(cls, path, **kwargs):
        snapshot = json.loads(Path(path).read_text())
        ctx = cls(bill_ref=snapshot['bill']['id'], snapshot=snapshot, **kwargs)
        ctx.say(f'snapshot loaded from {path}')
        return ctx
