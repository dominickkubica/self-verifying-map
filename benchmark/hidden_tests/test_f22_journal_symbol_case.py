"""f22: the journal's symbol filter ignores case and surrounding spaces."""

from types import SimpleNamespace

from optscan.analytics.positions import filter_positions


def test_lower_case_symbol_matches() -> None:
    spy, qqq = SimpleNamespace(symbol="SPY"), SimpleNamespace(symbol="QQQ")
    assert filter_positions([spy, qqq], symbol="spy") == [spy]
    assert filter_positions([spy, qqq], symbol=" SPY ") == [spy]
