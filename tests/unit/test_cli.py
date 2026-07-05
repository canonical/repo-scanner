"""Tests for CLI argument parsing and dispatch (repo_scanner.cli)."""

import sys

import pytest

from repo_scanner.cli import build_parser, main


def test_backend_is_a_global_option_before_the_subcommand() -> None:
    args = build_parser().parse_args(["--backend", "local", "exec", "--", "echo", "hi"])
    assert args.backend == "local"
    assert args.command == "exec"
    assert args.argv == ["--", "echo", "hi"]  # REMAINDER keeps the -- separator


def test_main_dispatches_to_exec_and_returns_its_exit_code() -> None:
    code = main(["exec", "--", sys.executable, "-c", "import sys; sys.exit(5)"])
    assert code == 5


def test_no_subcommand_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        main([])
