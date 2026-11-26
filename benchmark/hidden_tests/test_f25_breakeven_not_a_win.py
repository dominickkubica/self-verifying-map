"""f25: the forward test's win rate counts only trades that made money."""

from types import SimpleNamespace

from optscan.jobs.forward_test import summarize


def closed(ret: float) -> SimpleNamespace:
    # realized dollars consistent with the return, so a fix may judge a win by either
    return SimpleNamespace(
        return_on_debit=ret,
        slippage=None,
        exit_status="closed on plan",
        entered_late=False,
        position=SimpleNamespace(realized=ret * 200.0),
    )


def test_breakeven_is_not_a_win() -> None:
    assert summarize([closed(0.0), closed(0.5)]).win_rate == 0.5
    assert summarize([closed(0.0)]).win_rate == 0.0
