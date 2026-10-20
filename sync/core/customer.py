"""Which customer a sync is running for, and that customer's bricks.

A customer is a folder, customers/<name>/, and the one piece of it the syncs import is
mapping.py — the catalog-specific lookups (which m3ter plan template a Salesforce product
maps to, which aggregation and segment a usage resource lands on, which rate card carries
the negotiated rate). Everything in sync/ is generic; a second customer is a second folder,
not a fork. The snapshots a sync writes and replays live in the same folder.
"""
import importlib.util
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]          # m3ter-rc-config
CUSTOMERS = REPO / 'customers'
DEFAULT_CUSTOMER = 'entrust'


def customer_dir(name: str) -> Path:
    path = CUSTOMERS / name
    if not path.is_dir():
        known = ', '.join(sorted(p.name for p in CUSTOMERS.iterdir() if p.is_dir()))
        raise FileNotFoundError(f'no customer folder {path} (known: {known})')
    return path


def snapshot_root(name: str) -> Path:
    return customer_dir(name) / 'snapshots'


def load_mapping(name: str) -> ModuleType:
    """Import customers/<name>/mapping.py as a module, without it needing to be a package."""
    path = customer_dir(name) / 'mapping.py'
    if not path.is_file():
        raise FileNotFoundError(f'{path} is missing — every customer the syncs run for needs one')
    spec = importlib.util.spec_from_file_location(f'customers.{name}.mapping', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
