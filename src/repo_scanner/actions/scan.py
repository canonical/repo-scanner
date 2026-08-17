# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan scan` group: one action per scan, built from the registry.

Scans are data (`SCANS`, each declaring its `parameters`). A factory turns each into
a real `ScanAction` subclass, so every scan flows through the same parse/resolve/help
engine as any other action -- and each scan option (a `--<name>` flag or value)
resolves CLI > env > config > default like everything else.
"""

import logging
import os
from pathlib import Path
from typing import ClassVar

from repo_scanner.actions.base import Action
from repo_scanner.backends import start_session
from repo_scanner.clikit import Group, flag, option, positional
from repo_scanner.execution.context import SCAN_UID, ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.scans import output
from repo_scanner.scans.model import (
    ArtifactKind,
    Parameter,
    Scan,
    check_parameters,
    run_scan,
)
from repo_scanner.scans.output import DEFAULT_ROW_LIMIT, Format
from repo_scanner.scans.registry import SCANS
from repo_scanner.scans.resolve import resolve_dependencies

logger = logging.getLogger(__name__)

FORMATS = tuple(f.value for f in Format)

# Exit code when a scan completes and reports one or more findings.
FINDINGS_EXIT_CODE = 3


class ScanAction(Action):
    """Base for every scan leaf: the shared target and report options, and the run."""

    path: str = positional(help="Path to the repository to scan.")
    output: str | None = option(
        "-o", help="Write the report to FILE instead of stdout."
    )
    format: str | None = option("-f", choices=FORMATS, help="Output format.")
    limit: int = option(
        "-n",
        default=DEFAULT_ROW_LIMIT,
        convert=int,
        help="Maximum rows shown in the table.",
    )
    wrap: bool = flag(help="Wrap long table cells instead of truncating.")

    scan_cls: ClassVar[type[Scan]]  # set per scan by the factory

    def run(self) -> int:
        kwargs = {p.name: getattr(self, p.name) for p in self.scan_cls.parameters}
        invalid = check_parameters(self.scan_cls.parameters, kwargs)
        if invalid is not None:
            logger.error("%s", invalid)
            return 2
        path = os.path.abspath(self.path)
        if not os.path.isdir(path):
            logger.error("not a directory: %s", self.path)
            return 2
        allow_code_execution = getattr(self, "allow_code_execution", False)
        fmt = Format(self.format) if self.format else None
        uid = SCAN_UID if self.uid is None else self.uid
        with start_session(
            self.backend, tool_image=True, mount_source=path, image=self.image
        ) as session:
            if not session.ok:
                return session.exit_code
            assert session.target is not None  # a source was given, so target is set
            return scan(
                self.scan_cls(**kwargs),
                session.context,
                session.target,
                session.tool_root,
                output_file=self.output,
                fmt=fmt,
                limit=self.limit,
                wrap=self.wrap,
                uid=uid,
                resolved_parent=session.resolved_parent,
                allow_code_execution=allow_code_execution,
            )


def scan(
    scan: Scan,
    ctx: ExecutionContext,
    target: str,
    tool_root: str,
    *,
    output_file: str | None,
    fmt: Format | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
    wrap: bool = False,
    uid: int = SCAN_UID,
    resolved_parent: str = "",
    allow_code_execution: bool = False,
) -> int:
    """Run `scan` against `target`, emit the artifact, and return an exit code.

    For a findings scan (SARIF): 0 when it found nothing, 3 when it found something.
    For an inventory scan (SBOM/CycloneDX): 0. 2 when `output_file` already exists (it
    is not overwritten). 1 on a scan or tool error, or if the report could not be
    written.
    """
    # Fail fast before the (slow) scan if the report file already exists. This is only
    # a courtesy check: emit refuses to overwrite atomically at write time, so a file
    # appearing during the scan is still caught (as a write Failure below).
    if output_file is not None and Path(output_file).exists():
        logger.error(
            "output file already exists, refusing to overwrite: %s", output_file
        )
        return 2

    if scan.resolves_dependencies:
        target = resolve_dependencies(
            ctx,
            target,
            tool_root,
            resolved_parent,
            uid=uid,
            allow_code_execution=allow_code_execution,
        )
    artifact = run_scan(scan, ctx, target, tool_root, stream=True, uid=uid)
    if isinstance(artifact, Failure):
        logger.error(artifact.reason)
        return 1

    failure = output.emit(artifact, output=output_file, fmt=fmt, limit=limit, wrap=wrap)
    if isinstance(failure, Failure):
        logger.error(failure.reason)
        return 1

    if artifact.kind is ArtifactKind.CYCLONEDX:
        # An SBOM is an inventory, not pass/fail: report the size, always exit 0.
        logger.info("%s scan complete: %d component(s)", scan.name, artifact.count())
        return 0
    count = artifact.count()
    logger.info("%s scan complete: %d finding(s)", scan.name, count)
    return FINDINGS_EXIT_CODE if count else 0


def _field(parameter: Parameter):
    """A scan's declared `Parameter` as a CLI spec field (its `--<name>` inferred)."""
    if parameter.flag:
        return flag(help=parameter.help)
    return option(
        default=parameter.default,
        choices=parameter.choices,
        convert=parameter.type,
        help=parameter.help,
    )


def _scan_command(scan_cls: type[Scan]) -> type[ScanAction]:
    """A real `ScanAction` subclass for one scan, with its parameters as fields."""
    namespace: dict = {
        "name": scan_cls.name,
        "help": scan_cls.summary,
        "scan_cls": scan_cls,
    }
    for parameter in scan_cls.parameters:
        namespace[parameter.name] = _field(parameter)
    if scan_cls.resolves_dependencies:
        namespace["allow_code_execution"] = flag(
            help="Let dependency resolution build source packages when needed "
            "(runs untrusted repository code). Off by default.",
        )
    return type(f"{scan_cls.name.title()}Scan", (ScanAction,), namespace)


class ScanGroup(Group):
    name = "scan"
    help = "Scan a repository."
    subcommands = tuple(_scan_command(s) for s in SCANS.values())
