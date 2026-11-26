"""f24: `optscan history` runs the history command, not another one."""

from optscan import cli


def test_history_runs_history(clean_env, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPTSCAN_DATA_DIR", str(tmp_path))
    called = []
    monkeypatch.setattr(cli, "_cmd_history", lambda s, a: called.append("history") or 0)
    monkeypatch.setattr(cli, "_cmd_trades", lambda s, a: called.append("trades") or 0)
    assert cli.main(["history"]) == 0
    assert called == ["history"]
