"""Shared fixtures: revenue-cloud-config's simulated org and a way to run its CLI against a customer's config."""
from __future__ import annotations

from pathlib import Path

import pytest
from rc_config import index as product_index
from rc_config.testing.fake_org import FakeOrg
from rc_config.testing.harness import run_cli


@pytest.fixture(autouse=True)
def _no_index_sleep(monkeypatch):
    """The index poll sleeps between checks; the simulated org finishes a build on the first look."""
    monkeypatch.setattr(product_index.time, "sleep", lambda _s: None)


@pytest.fixture
def org() -> FakeOrg:
    return FakeOrg()


@pytest.fixture
def run(org: FakeOrg, capsys, caplog):
    """run("check", config_dir=<path>) -> (exit code, everything printed or logged)."""
    def _run(*argv: str, config_dir: Path) -> tuple[int, str]:
        return run_cli(org, argv, config_dir, capsys, caplog)
    return _run
