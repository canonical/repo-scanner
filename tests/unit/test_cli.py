# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for CLI argument parsing and dispatch (repo_scanner.cli)."""

import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar

import repo_scanner.cli as cli
from repo_scanner.cli import build_parser, main
from repo_scanner.execution.process import Failure
from repo_scanner.scans import sarif
from repo_scanner.scans.model import (
    Artifact,
    Parameter,
    Scan,
    ToolInvocation,
    ToolResult,
)


def test_backend_is_a_global_option_before_the_subcommand() -> None:
    args = build_parser().parse_args(["--backend", "local", "exec", "--", "echo", "hi"])
    assert args.backend == "local"
    assert args.command == "exec"
    assert args.argv == ["--", "echo", "hi"]  # REMAINDER keeps the -- separator


def test_main_dispatches_to_the_command_and_returns_its_exit_code() -> None:
    prog = [sys.executable, "-c", "raise SystemExit(5)"]
    assert main(["--backend", "local", "exec", "--", *prog]) == 5


@dataclass(frozen=True)
class _FakeScan:
    """A test-only scan whose declared parameters exercise the CLI generically."""

    name: ClassVar[str] = "faux"
    summary: ClassVar[str] = "A fake scan for testing the CLI."
    parameters: ClassVar[tuple[Parameter, ...]] = (
        Parameter("flavor", "the flavor", choices=("plain", "rich"), default="plain"),
        Parameter("level", "detail level", type=int, requires={"flavor": "rich"}),
    )
    flavor: str = "plain"
    level: int | None = None

    def invocations(self, target: str) -> list[ToolInvocation]:
        return []

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        return sarif.SarifDocument({"runs": []})


@contextmanager
def _only_fake_scan() -> Iterator[None]:
    """Point the CLI's scan registry at just the fake scan for the duration."""
    saved = cli.SCANS
    registry: dict[str, type[Scan]] = {_FakeScan.name: _FakeScan}
    cli.SCANS = registry
    try:
        yield
    finally:
        cli.SCANS = saved


def test_scan_subcommands_are_built_from_declared_parameters() -> None:
    with _only_fake_scan():
        parser = build_parser()
        # the scan's declared options parse into args.
        args = parser.parse_args(["scan", "faux", "/repo", "--flavor", "rich"])
        assert args.scan_command == "faux" and args.flavor == "rich"
        # a parameter's default is applied when the option is omitted.
        args = parser.parse_args(["scan", "faux", "/repo"])
        assert args.flavor == "plain" and args.level is None


def test_scan_accepts_output_format_and_limit_options() -> None:
    with _only_fake_scan():
        parser = build_parser()
        args = parser.parse_args(
            ["scan", "faux", "/repo", "--format", "json", "--limit", "5", "--wrap"]
        )
        assert args.format == "json" and args.limit == 5 and args.wrap is True


def test_scan_parameter_requirement_is_enforced() -> None:
    with _only_fake_scan(), tempfile.TemporaryDirectory() as repo:
        # --level requires --flavor rich; with the default flavor it is rejected,
        # before any backend is selected.
        code = main(["scan", "faux", repo, "--level", "3"])
    assert code == 2
