# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for CLI parsing, resolution, and dispatch (repo_scanner.clikit and app)."""

import logging
import sys
import tempfile
from typing import Any

from repo_scanner.actions.base import Action
from repo_scanner.app import Reposcan, main
from repo_scanner.clikit import LOG_LEVELS, Cli, Group, option, parse, resolve
from repo_scanner.execution.process import Failure
from repo_scanner.scans import sarif
from repo_scanner.scans.base import ScanAction
from repo_scanner.scans.model import Artifact, ToolInvocation, ToolResult


def _resolved(argv: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    """Parse `argv` against the real tree and resolve, with no env/config by default."""
    parsed = parse(Reposcan, Action, argv, "reposcan")
    assert parsed.error is None, parsed.error
    values, error = resolve(parsed.scope, parsed.raw, env=env or {}, config={})
    assert error is None, error
    return values


# --- dispatch (end to end through main) --------------------------------------


def test_dispatch_forwards_the_command_exit_code() -> None:
    prog = [sys.executable, "-c", "raise SystemExit(5)"]
    assert main(["--backend", "local", "exec", "--", *prog]) == 5


def test_a_global_is_accepted_after_the_subcommand() -> None:
    prog = [sys.executable, "-c", "raise SystemExit(6)"]
    assert main(["exec", "--backend", "local", "--", *prog]) == 6


def test_verbosity_configures_root_logging_before_dispatch() -> None:
    saved = logging.getLogger().level
    try:
        prog = [sys.executable, "-c", ""]
        main(["--verbosity", "warning", "--backend", "local", "exec", "--", *prog])
        assert logging.getLogger().level == LOG_LEVELS["warning"]
    finally:
        logging.getLogger().setLevel(saved)


def test_usage_errors_return_2() -> None:
    assert main(["frobnicate"]) == 2  # unknown command
    assert main(["--nope", "exec"]) == 2  # unknown option
    assert main(["--uid", "-1", "exec", "--", "true"]) == 2  # invalid value


# --- flow-down: a global resolves anywhere, at any depth ----------------------


def test_a_global_resolves_from_the_middle_of_a_deep_command() -> None:
    values = _resolved(["image", "cache", "--backend", "local", "remove", "r1"])
    assert values["backend"] == "local"
    assert values["reference"] == "r1"


def test_cli_beats_env_beats_default_for_a_global() -> None:
    assert _resolved(["exec", "--", "x"])["backend"] == "auto"  # default
    with_env = _resolved(["exec", "--", "x"], {"REPOSCAN_BACKEND": "docker"})
    assert with_env["backend"] == "docker"  # env over default
    with_cli = _resolved(
        ["--backend", "local", "exec", "--", "x"], {"REPOSCAN_BACKEND": "docker"}
    )
    assert with_cli["backend"] == "local"  # cli over env


# --- scan options resolve like any other --------------------------------------


class _FauxScan(ScanAction):
    """A test-only scan whose options exercise resolution and the requires rule."""

    name = "faux"
    help = "A fake scan for testing the CLI."

    flavor: str = option(choices=("plain", "rich"), default="plain", help="the flavor")
    level: int | None = option(
        convert=int, requires={"flavor": "rich"}, help="detail level"
    )

    def invocations(self, target: str) -> list[ToolInvocation]:
        return []

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        return sarif.SarifDocument({"runs": []})


def _fake_scan_tree() -> type[Group]:
    return type(
        "Root", (Group,), {"name": "reposcan", "help": "", "subcommands": (_FauxScan,)}
    )


def _resolved_scan(argv: list[str]) -> dict[str, Any]:
    parsed = parse(_fake_scan_tree(), Action, argv, "reposcan")
    assert parsed.error is None, parsed.error
    values, error = resolve(parsed.scope, parsed.raw, env={}, config={})
    assert error is None, error
    return values


def test_scan_parameters_become_options_that_resolve() -> None:
    assert _resolved_scan(["faux", "/repo"])["flavor"] == "plain"  # default
    assert _resolved_scan(["faux", "/repo", "--flavor", "rich"])["flavor"] == "rich"
    assert _resolved_scan(["faux", "/repo", "--level", "3"])["level"] == 3  # converted


def test_scan_requirement_is_enforced_before_any_backend() -> None:
    # --level requires --flavor rich; with the default flavor (plain) it is rejected.
    app = Cli("reposcan", root=_fake_scan_tree(), base=Action)
    with tempfile.TemporaryDirectory() as repo:
        assert app.run(["faux", repo, "--level", "3"]) == 2


def test_a_boolean_scan_flag_resolves_from_cli_env_and_default() -> None:
    # --include-dev-dependencies is a real, env-settable flag on both sbom and sca.
    for scan in ("sbom", "sca"):
        assert _resolved(["scan", scan, "."])["include_dev_dependencies"] is False
        with_cli = _resolved(["scan", scan, ".", "--include-dev-dependencies"])
        assert with_cli["include_dev_dependencies"] is True
        with_env = _resolved(
            ["scan", scan, "."], {"REPOSCAN_INCLUDE_DEV_DEPENDENCIES": "1"}
        )
        assert with_env["include_dev_dependencies"] is True
