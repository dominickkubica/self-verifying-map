"""c14: `optscan forward-test --limit N` parses and caps the trades shown."""

from optscan import cli


def test_limit_is_accepted() -> None:
    args = cli.build_parser().parse_args(["forward-test", "--limit", "2"])
    assert args.limit == 2


def test_no_limit_still_parses() -> None:
    cli.build_parser().parse_args(["forward-test"])
