# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Scan model: run one or more tools over a target and produce an artifact.

A Scan translates its own parameters into tool invocations (`invocations`), and
consolidates the tools' outputs into a single artifact (`consolidate`). The
relationship between scans and tools is many-to-many: a scan may invoke several
tools, and a tool may serve several scans. `run_scan` is the backend-agnostic
driver: it runs each invocation in an execution context and hands the results to
the scan to consolidate.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Protocol, runtime_checkable

from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.tools.registry import TOOLS

logger = logging.getLogger(__name__)


class ArtifactKind(str, Enum):
    """The kind of document a scan produces."""

    SARIF = "sarif"
    CYCLONEDX = "cyclonedx"


class Artifact(Protocol):
    """A consolidated scan result: a JSON-serialisable document of a known kind."""

    kind: ClassVar[ArtifactKind]

    def to_dict(self) -> dict[str, Any]:
        """The artifact rendered as a dictionary for JSON serialization."""
        ...

    def count(self) -> int:
        """The number of entries the artifact holds (findings, or components)."""
        ...


@dataclass(frozen=True)
class ToolInvocation:
    """One tool run a scan needs: the tool, its args, and how to run/judge it.

    Some tools exit non-zero to signal findings rather than an error (e.g.
    govulncheck exits 3); `ok_codes` lists the exit codes that mean success, so
    run_scan does not mistake findings for a failure. `cwd` runs the tool in that
    directory (some analysers must run inside the target). `optional` marks a tool
    that may not apply to every repo (e.g. govulncheck on a non-Go repo): its
    failure is logged and skipped rather than failing the whole scan.
    """

    tool: str
    args: list[str]
    ok_codes: tuple[int, ...] = (0,)
    cwd: str | None = None
    optional: bool = False


@dataclass(frozen=True)
class ToolResult:
    """The outcome of one tool invocation, paired with the tool's name."""

    tool: str
    output: ExecResult


@dataclass(frozen=True)
class Parameter:
    """A scan-specific CLI option, declared as data by the scan.

    The CLI builds `--<name>` from this and passes the parsed value to the scan's
    `<name>` constructor argument, so a scan owns its own options.

    Attributes:
        name: The option and constructor-argument name (e.g. "mode").
        help: The option's help text.
        choices: The allowed values, or None for any.
        default: The value used when the option is omitted.
        type: A converter for the raw string (e.g. int), or None for a string.
        requires: A mapping of other parameter -> required value this option depends
            on, or None. When set, the option is valid only if each named parameter
            has the given value, e.g. depth `requires={"mode": "history"}`. Checked
            by `check_parameters`.
    """

    name: str
    help: str
    choices: tuple[str, ...] | None = None
    default: Any = None
    type: Callable[[str], Any] | None = None
    requires: dict[str, str] | None = None


# A scan with no scan-specific options declares this for its `parameters`.
NO_PARAMETERS: tuple[Parameter, ...] = ()


def check_parameters(
    parameters: tuple[Parameter, ...], values: dict[str, Any]
) -> str | None:
    """Check parameter values against requirements.

    A parameter's `requires` is checked only when the parameter is set (its value
    differs from its default), so a scan expresses cross-option rules as data rather
    than the caller hard-coding them.

    Args:
        parameters: The scan's parameters.
        values: The resolved value for each parameter, keyed by name.

    Returns:
        An error message for the first violated requirement, or None if all hold.
    """
    for parameter in parameters:
        if not parameter.requires:
            continue
        if values.get(parameter.name) == parameter.default:
            continue  # the option is not set, so its requirements do not apply
        for required_name, required_value in parameter.requires.items():
            if values.get(required_name) != required_value:
                return (
                    f"--{parameter.name} requires '--{required_name}={required_value}'"
                )
    return None


@runtime_checkable
class Scan(Protocol):
    """A scan: a set of tool invocations over a target plus how to consolidate them.

    Class attributes declare the scan as data: `name` labels it ("secrets", ...),
    `summary` is its CLI help, and `parameters` are its scan-specific CLI options.
    Runtime-checkable so scan classes can be discovered with `isinstance`.
    """

    name: ClassVar[str]
    summary: ClassVar[str]
    parameters: ClassVar[tuple[Parameter, ...]]

    def invocations(self, target: str) -> list[ToolInvocation]:
        """The tool invocations to run against `target`.

        Args:
            target: The path to the repository as seen in the execution context.

        Returns:
            The tool invocations, in the order they should run.
        """
        ...

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        """Merge the tool outputs into one artifact.

        Args:
            results: The outcome of each invocation, in invocation order.

        Returns:
            The consolidated artifact, or a Failure if the outputs could not be
            interpreted.
        """
        ...


def run_scan(
    scan: Scan, ctx: ExecutionContext, target: str, tool_root: str
) -> Artifact | Failure:
    """Run `scan`'s tool invocations in `ctx` and consolidate their outputs.

    Each tool is looked up in the registry and run at its installed path. A tool
    that cannot be started, or exits non-zero, aborts the scan as a Failure -- a
    scan sets its tools' flags so a non-zero exit means a real error, not findings.

    Args:
        scan: The scan to run.
        ctx: The started context to run the tools in.
        target: The repository path as seen in the context.
        tool_root: Where the tools are installed in the context.

    Returns:
        The scan's consolidated artifact, or the first Failure encountered.
    """
    results: list[ToolResult] = []
    for invocation in scan.invocations(target):
        tool = TOOLS.get(invocation.tool)
        if tool is None:
            return Failure(reason=f"unknown tool: {invocation.tool}")
        executable = tool.installed_path(tool_root)
        result = ctx.run([executable, *invocation.args], cwd=invocation.cwd)
        if isinstance(result, Failure):
            if invocation.optional:
                logger.warning("%s did not run: %s", invocation.tool, result.reason)
                continue
            return result
        if result.exit_code not in invocation.ok_codes:
            reason = result.stderr.strip() or f"exit code {result.exit_code}"
            if invocation.optional:
                logger.warning("skipping %s: %s", invocation.tool, reason)
                continue
            return Failure(reason=f"{invocation.tool} failed: {reason}")
        results.append(ToolResult(invocation.tool, result))
    return scan.consolidate(results)
