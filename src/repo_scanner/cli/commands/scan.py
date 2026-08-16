# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan scan` group: one subcommand per scan, built from the registry.

Scans are data (`SCANS`, each declaring its `parameters`). A factory turns each into
a real `Command` subclass, so every scan flows through the same parse/resolve/help
engine as any other command -- and each scan option (a `--<name>` flag or value)
resolves CLI > env > config > default like everything else.
"""

import logging
import os
from typing import ClassVar

from repo_scanner.actions.scan import scan as run_scan
from repo_scanner.backends import start_session
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import Group, flag, option, positional
from repo_scanner.execution.context import SCAN_UID
from repo_scanner.scans.model import Parameter, Scan, check_parameters
from repo_scanner.scans.output import DEFAULT_ROW_LIMIT, Format
from repo_scanner.scans.registry import SCANS

logger = logging.getLogger(__name__)

FORMATS = tuple(f.value for f in Format)


class ScanCommand(Command):
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
            return run_scan(
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


def _scan_command(scan_cls: type[Scan]) -> type[ScanCommand]:
    """A real `Command` subclass for one scan, with its parameters as fields."""
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
    return type(f"{scan_cls.name.title()}Scan", (ScanCommand,), namespace)


class ScanGroup(Group):
    name = "scan"
    help = "Scan a repository."
    subcommands = tuple(_scan_command(s) for s in SCANS.values())
