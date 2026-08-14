# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for CLI argument parsing and dispatch (repo_scanner.cli)."""

import argparse
import logging
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar

import repo_scanner.cli.commands.scan as scan_cmd_module
from repo_scanner.cli.commands.scan import build_scan_parser
from repo_scanner.cli.main import main
from repo_scanner.cli.nodes import Context
from repo_scanner.cli.options import GLOBAL_OPTIONS, LOG_LEVELS
from repo_scanner.execution.process import Failure
from repo_scanner.scans import sarif
from repo_scanner.scans.model import (
    Artifact,
    Parameter,
    Scan,
    ToolInvocation,
    ToolResult,
)


def test_main_dispatches_and_returns_its_exit_code() -> None:
    """`exec` runs the given command and forwards its exit code (local backend)."""
    prog = [sys.executable, "-c", "raise SystemExit(5)"]
    assert main(["--backend", "local", "exec", "--", *prog]) == 5


def test_global_option_flows_down_after_the_subcommand() -> None:
    """A global option placed after the subcommand is accepted (flow-down)."""
    prog = [sys.executable, "-c", "raise SystemExit(5)"]
    assert main(["exec", "--backend", "local", "--", *prog]) == 5


def test_verbosity_sets_the_root_log_level() -> None:
    """`--verbosity` configures root logging before the subcommand runs."""
    saved = logging.getLogger().level
    try:
        prog = [sys.executable, "-c", ""]
        main(["--verbosity", "warning", "--backend", "local", "exec", "--", *prog])
        assert logging.getLogger().level == LOG_LEVELS["warning"]
    finally:
        logging.getLogger().setLevel(saved)


@dataclass(frozen=True)
class _FakeScan:
    """A test-only scan whose declared parameters exercise the CLI generically."""

    name: ClassVar[str] = "faux"
    summary: ClassVar[str] = "A fake scan for testing the CLI."
    parameters: ClassVar[tuple[Parameter, ...]] = (
        Parameter("flavor", "the flavor", choices=("plain", "rich"), default="plain"),
        Parameter("level", "detail level", type=int, requires={"flavor": "rich"}),
    )
    resolves_dependencies: ClassVar[bool] = False
    flavor: str = "plain"
    level: int | None = None

    def invocations(self, target: str) -> list[ToolInvocation]:
        return []

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        return sarif.SarifDocument({"runs": []})


@dataclass(frozen=True)
class _FakeResolvingScan:
    """A fake scan that resolves dependencies (so it gets --allow-code-execution)."""

    name: ClassVar[str] = "resolving"
    summary: ClassVar[str] = "A fake dependency-resolving scan."
    parameters: ClassVar[tuple[Parameter, ...]] = ()
    resolves_dependencies: ClassVar[bool] = True

    def invocations(self, target: str) -> list[ToolInvocation]:
        return []

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        return sarif.SarifDocument({"runs": []})


@contextmanager
def _only_fake_scan() -> Iterator[None]:
    """Point the scan group's registry at just the fake scan for the duration.

    Patches `SCANS` on the module that reads it (`repo_scanner.cli.commands.scan`),
    not a re-export -- there is no test seam in the real code for this.
    """
    saved = scan_cmd_module.SCANS
    registry: dict[str, type[Scan]] = {_FakeScan.name: _FakeScan}
    scan_cmd_module.SCANS = registry
    try:
        yield
    finally:
        scan_cmd_module.SCANS = saved


def _parser() -> argparse.ArgumentParser:
    return build_scan_parser(_FakeScan, Context({}, GLOBAL_OPTIONS))


def test_scan_options_are_built_from_declared_parameters() -> None:
    args = _parser().parse_args(["/repo", "--flavor", "rich"])
    assert args.flavor == "rich"
    # a parameter's default is applied when the option is omitted.
    args = _parser().parse_args(["/repo"])
    assert args.flavor == "plain" and args.level is None


def test_scan_accepts_output_format_and_limit_options() -> None:
    args = _parser().parse_args(["/repo", "--format", "json", "--limit", "5", "--wrap"])
    assert args.format == "json" and args.limit == 5 and args.wrap is True


def test_allow_code_execution_only_on_dependency_resolving_scans() -> None:
    ctx = Context({}, GLOBAL_OPTIONS)
    resolving = build_scan_parser(_FakeResolvingScan, ctx)
    nonresolving = build_scan_parser(_FakeScan, ctx)
    # the resolving scan declares --allow-code-execution (default False) ...
    assert resolving.parse_args(["/repo"]).allow_code_execution is False
    # ... and the non-resolving scan does not declare it at all.
    assert not hasattr(nonresolving.parse_args(["/repo"]), "allow_code_execution")


def test_scan_parameter_requirement_is_enforced_before_any_backend() -> None:
    """--level requires --flavor rich; with the default flavor it is rejected."""
    with _only_fake_scan(), tempfile.TemporaryDirectory() as repo:
        code = main(["scan", "faux", repo, "--level", "3"])
    assert code == 2
