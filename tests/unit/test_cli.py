# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for CLI argument parsing and dispatch (repo_scanner.cli)."""

import sys

from repo_scanner.cli import build_parser, main


def test_backend_is_a_global_option_before_the_subcommand() -> None:
    args = build_parser().parse_args(["--backend", "local", "exec", "--", "echo", "hi"])
    assert args.backend == "local"
    assert args.command == "exec"
    assert args.argv == ["--", "echo", "hi"]  # REMAINDER keeps the -- separator


def test_main_dispatches_to_the_command_and_returns_its_exit_code() -> None:
    prog = [sys.executable, "-c", "raise SystemExit(5)"]
    assert main(["--backend", "local", "exec", "--", *prog]) == 5
