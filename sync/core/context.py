"""What every sync's context shares: the two lazy API clients and the log.

In the m3sh workflows every function reads and writes a shared *state*. Each
sync has its own context dataclass (ordersync.SyncContext, billsync.BillSyncContext)
with the same three parts — snapshot (what the source platform said, read once and
frozen), state (what later steps found or created), log — and the same two lazy
clients. The clients live here so that the rule is written once:

  * a step that only needs Salesforce never forces m3ter credentials to be present;
  * a replay from a saved snapshot never touches the source platform at all.
"""
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from m3sdk import M3terAuth, M3terAuthGamma, M3terClient, M3terClientGamma

from salesforcesdk import SalesforceCliAuth

SF_API_VERSION = 'v66.0'   # pinned alongside revenue-cloud-config's catalog.toml

# Where ReadOrder / ReadBill save what they read, and what --from-file replays.
# One customer for now; becomes customers/<name>/snapshots with --customer (plan phase 6).
SNAPSHOT_ROOT = Path('customers/entrust/snapshots')


@dataclass(kw_only=True)
class BaseSyncContext:
    sf_alias: str = 'm3ter'             # `sf` CLI org alias
    dry_run: bool = False               # writing steps print payloads instead of posting
    snapshot: dict = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    _sf_auth: object = None
    _m3: object = None

    # ---- Salesforce -------------------------------------------------------
    @property
    def sf_auth(self):
        if self._sf_auth is None:
            self._sf_auth = SalesforceCliAuth(self.sf_alias).authenticate()
            self.say(f'Salesforce: {self._sf_auth.username} @ {self._sf_auth.instance_url}')
        return self._sf_auth

    # ---- m3ter ------------------------------------------------------------
    @property
    def m3(self) -> M3terClient:
        """Authenticate exactly the way create_config.py does: ENVIRONMENT,
        ORGANIZATION, apiKey and apiSecret from parameters/<org>.env."""
        if self._m3 is None:
            gamma = os.getenv('ENVIRONMENT') == 'gamma'
            auth = (M3terAuthGamma if gamma else M3terAuth)(
                api_key=os.getenv('apiKey'), api_secret=os.getenv('apiSecret'))  # noqa: SIM112  (the .env files' spelling)
            auth.authenticate()
            self._m3 = (M3terClientGamma if gamma else M3terClient)(
                org_id=os.getenv('ORGANIZATION'), token=auth.token)
            self.say(f"m3ter: org {os.getenv('ORGANIZATION')} ({os.getenv('ENVIRONMENT')})")
        return self._m3

    # ---- bookkeeping ------------------------------------------------------
    def say(self, message: str):
        stamp = datetime.now(UTC).strftime('%H:%M:%S')
        line = f'[{stamp}] {message}'
        self.log.append(line)
        print(line)
