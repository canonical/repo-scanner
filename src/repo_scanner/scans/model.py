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
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar, NamedTuple, Protocol, runtime_checkable

from repo_scanner.execution.context import SCAN_UID, ExecutionContext, read_file
from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.exclude import (
    EXCLUDABLE_TOOLS,
    IgnoredPaths,
    build_exclude_flags,
)
from repo_scanner.tools.registry import TOOLS

logger = logging.getLogger(__name__)


class ArtifactKind(str, Enum):
    """The kind of document a scan produces."""

    SARIF = "sarif"
    CYCLONEDX = "cyclonedx"


class Table(NamedTuple):
    """A named database table for an artifact: its name, columns, and string rows."""

    name: str
    columns: tuple[str, ...]
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class ToolInvocation:
    """One tool run a scan needs: the tool, its args, and how to run/judge it.

    Some tools exit non-zero to signal findings rather than an error (e.g.
    govulncheck exits 3); `ok_codes` lists the exit codes that mean success, so
    run_scan does not mistake findings for a failure. `cwd` overrides the working
    directory the tool runs in; when None it defaults to the target repo.
    `env` adds environment variables for the run. `output_file` names a file the tool
    writes its result to, for tools whose stdout is unreliable: run_scan reads that
    file and uses its content as the tool's output instead of the tool's stdout.
    `optional` marks a tool that may not apply to every repo (e.g. govulncheck on a
    non-Go repo): its failure is logged and skipped rather than failing the whole scan.
    """

    tool: str
    args: list[str]
    ok_codes: tuple[int, ...] = (0,)
    cwd: str | None = None
    env: Mapping[str, str] | None = None
    output_file: str | None = None
    optional: bool = False


@dataclass(frozen=True)
class ToolInvocationRecord(ToolInvocation):
    """Provenance for one executed tool command, recorded in a report's metadata.

    `command` is the full argv as run (executable and every argument). `environment`
    holds only the variables reposcan set for the run, never the inherited process
    environment, so no ambient secrets are written into a shareable report.
    """

    version: str = ""
    command: tuple[str, ...] = ()
    working_directory: str = ""
    environment: Mapping[str, str] = field(default_factory=dict)
    exit_code: int = -1
    successful: bool = False


class Artifact(Protocol):
    """A consolidated scan result: a JSON-serialisable document of a known kind."""

    kind: ClassVar[ArtifactKind]

    def to_dict(self) -> dict[str, Any]:
        """The artifact rendered as a dictionary for JSON serialization."""
        ...

    def count(self) -> int:
        """The number of entries the artifact holds (findings, or components)."""
        ...

    def rows(self) -> tuple[list[str], list[list[str]]]:
        """A table view of the artifact: column headers and one row per entry."""
        ...

    def records(self) -> Table:
        """The artifact's entries as a named database table with parsed columns."""
        ...

    def record_invocations(self, invocations: list[ToolInvocationRecord]) -> None:
        """Record the tool commands that produced this artifact, as provenance."""
        ...


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
    resolves_dependencies: ClassVar[bool] = False

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
    scan: Scan,
    ctx: ExecutionContext,
    target: str,
    tool_root: str,
    *,
    stream: bool = False,
    uid: int = SCAN_UID,
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
        stream: When True, echo each tool's live progress (its stderr) to the console
            as it runs. Each tool's stdout (its results) is captured but not echoed,
            so streaming never dumps the report to the console.
        uid: The user id for all in-container processes. Must exist in the image.

    Returns:
        The scan's consolidated artifact, or the first Failure encountered.
    """
    invocations = scan.invocations(target)
    # identify gitignore'd paths
    ignored = (
        IgnoredPaths.from_context(ctx, target)
        if any(invocation.tool in EXCLUDABLE_TOOLS for invocation in invocations)
        else IgnoredPaths()
    )
    results: list[ToolResult] = []
    provenance: list[ToolInvocationRecord] = []
    for invocation in invocations:
        tool = TOOLS.get(invocation.tool)
        if tool is None:
            return Failure(reason=f"unknown tool: {invocation.tool}")
        executable = tool.installed_path(tool_root)
        cmd = [
            executable,
            *invocation.args,
            *build_exclude_flags(invocation.tool, ignored),
        ]
        logger.debug("Running scan command:\n%s", " ".join(cmd))
        result = ctx.run(
            cmd,
            cwd=invocation.cwd or target,
            env=invocation.env,
            uid=uid,
            stream_stdout=False,
            stream_stderr=stream,
        )
        if isinstance(result, Failure):
            if invocation.optional:
                logger.warning("%s did not run: %s", invocation.tool, result.reason)
                continue
            return result
        provenance.append(
            ToolInvocationRecord(
                **asdict(invocation),
                version=tool.version,
                command=tuple(cmd),
                working_directory=invocation.cwd or target,
                environment=dict(invocation.env or {}),
                exit_code=result.exit_code,
                successful=result.exit_code in invocation.ok_codes,
            )
        )
        if result.exit_code not in invocation.ok_codes:
            reason = result.stderr.strip() or f"exit code {result.exit_code}"
            if invocation.optional:
                logger.warning("skipping %s: %s", invocation.tool, reason)
                continue
            return Failure(reason=f"{invocation.tool} failed: {reason}")
        if invocation.output_file is not None:
            content = read_file(
                ctx, invocation.output_file, cwd=invocation.cwd or target
            )
            if content is None:
                note = f"{invocation.tool} wrote no output to {invocation.output_file}"
                if invocation.optional:
                    logger.warning("%s", note)
                    continue
                return Failure(reason=note)
            result = ExecResult(result.exit_code, content, result.stderr)
        results.append(ToolResult(invocation.tool, result))
    artifact = scan.consolidate(results)
    if isinstance(artifact, Failure):
        return artifact
    artifact.record_invocations(provenance)
    return artifact
