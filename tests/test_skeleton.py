"""The dependency wiring works: both platform tools import from their sibling checkouts."""


def test_m3ter_tool_importable():
    import m3sdk
    import m3shsdk
    import m3utils

    assert m3sdk and m3shsdk and m3utils


def test_revenue_cloud_tool_importable():
    import rc_config

    assert rc_config


def test_this_repo_importable():
    import salesforcesdk
    import sync
    import webhooks

    assert sync and salesforcesdk and webhooks
