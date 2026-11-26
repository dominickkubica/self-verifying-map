"""f21: `optscan forward-test` includes closed positions, not only open ones."""

from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

from optscan.jobs import forward_test as ft
from optscan.models.position import PositionStatus


def test_closed_trades_are_included(monkeypatch) -> None:
    closed = SimpleNamespace(
        plan={"mid": 1.0},
        strategy=None,
        status=PositionStatus.CLOSED,
        opened_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    still_open = SimpleNamespace(
        plan={"mid": 1.0},
        strategy=None,
        status=PositionStatus.OPEN,
        opened_at=datetime(2026, 7, 2, tzinfo=UTC),
    )

    def list_positions(conn, *, status=PositionStatus.OPEN, symbol=None):
        return [p for p in (still_open, closed) if status is None or p.status == status]

    monkeypatch.setattr(ft.store, "list_positions", list_positions)
    monkeypatch.setattr(ft.db, "session", lambda path: nullcontext(None))
    monkeypatch.setattr(ft, "trade", lambda p: p)
    got = ft.forward_trades(SimpleNamespace(sqlite_path=":memory:"))
    assert closed in got and still_open in got
