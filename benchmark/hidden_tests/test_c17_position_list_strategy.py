"""c17: `optscan position list` prints each position's strategy."""

from datetime import UTC, date, datetime

from optscan import cli, config
from optscan.models import Right
from optscan.models.opportunity import Action, Strategy
from optscan.models.position import Position, PositionLeg
from optscan.storage import db
from optscan.storage import positions as store


def test_strategy_is_listed(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPTSCAN_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    settings = config.get_settings()
    settings.ensure_dirs()
    leg = PositionLeg(
        action=Action.SELL, right=Right.PUT, strike=100, expiry=date(2030, 1, 18), fill_price=2.0
    )
    with db.session(settings.sqlite_path) as conn:
        store.add_position(
            conn,
            Position(
                symbol="SPY",
                legs=(leg,),
                opened_at=datetime(2026, 1, 2, tzinfo=UTC),
                strategy=Strategy.CASH_SECURED_PUT,
            ),
        )
    try:
        cli.main(["position", "list"])
    finally:
        config.get_settings.cache_clear()
    assert "cash_secured_put" in capsys.readouterr().out
