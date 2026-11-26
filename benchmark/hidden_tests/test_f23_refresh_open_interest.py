"""f23: the dashboard's refresh drops cached open interest chains too."""

from optscan.api import deps


def test_refresh_drops_cached_open_interest() -> None:
    key = ("SPY", "2026-08-21")
    deps._OI_CHAINS.put(key, "cached", None)
    deps.clear_live_caches()
    assert deps._OI_CHAINS.get(key, 0.0) is None
