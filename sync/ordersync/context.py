"""The state that travels through the order-sync steps.

  snapshot  what Salesforce said — read once by the ReadOrder step, then frozen.
            Later steps only read from it, never query Salesforce again.
  state     what the m3ter steps created or found (ids, objects) — each step
            writes under its own key so the next step can pick it up.
  log       what happened, in order, so a run can be explained afterwards.

The clients and the log are the shared BaseSyncContext; this adds the order
reference and the snapshot file naming.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from sync.core.context import SF_API_VERSION, SNAPSHOT_ROOT, BaseSyncContext  # noqa: F401  (SF_API_VERSION re-exported)


@dataclass(kw_only=True)
class SyncContext(BaseSyncContext):
    order_ref: str                      # OrderNumber (e.g. 00000102) or an Order Id

    def save_snapshot(self, directory=SNAPSHOT_ROOT / 'orders') -> Path:
        """Write the Salesforce snapshot to <snapshots>/orders/<order>.json so a
        later run (or a dry run) can replay it without Salesforce."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        number = self.snapshot.get('order', {}).get('OrderNumber', self.order_ref)
        path = Path(directory) / f'{number}.json'
        path.write_text(json.dumps(self.snapshot, indent=2))
        self.say(f'snapshot written to {path}')
        return path

    @classmethod
    def from_snapshot(cls, path, **kwargs):
        snapshot = json.loads(Path(path).read_text())
        ctx = cls(order_ref=snapshot['order']['OrderNumber'], snapshot=snapshot, **kwargs)
        ctx.say(f'snapshot loaded from {path}')
        return ctx
