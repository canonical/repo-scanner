# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan scan` subcommand: scan a repository.

Unlike the static groups (`image`, `config`), the set of scans is data -- the
`SCANS` registry -- so this group is not a `CommandGroup` instance with a fixed
`subcommands` dict. Its `dispatch` looks the selected scan up in the registry by
name and builds that scan's leaf parser on the spot, then runs it.

A scan's own options come from its declared `parameters` (see scans/model.py);
`--allow-code-execution` is added only for scans that resolve transitive dependencies
(`resolves_dependencies`).
"""

import argparse
import logging
import os
from typing import Any

from repo_scanner.backends import start_session
from repo_scanner.cli.nodes import CommandGroup, Context
from repo_scanner.cli.options import REPORT_FORMAT_OPTIONS, Option
from repo_scanner.cli.parsing import (
    add_option,
    print_help,
    unknown_command,
)
from repo_scanner.commands import scan_cmd
from repo_scanner.scans import output
from repo_scanner.scans.model import Scan, check_parameters
from repo_scanner.scans.registry import SCANS

logger = logging.getLogger(__name__)


def build_scan_parser(scan_cls: type[Scan], ctx: Context) -> argparse.ArgumentParser:
    """The argument parser for one scan's leaf, built from its declared parameters.

    Cumulative: ancestor specs (flowed down via `ctx.specs`) are added first, then
    the scan's positional `path`, its declared `--<parameter>` options, the
    `--allow-code-execution` flag (only when the scan resolves dependencies), and
    the shared report-format options.
    """
    parser = argparse.ArgumentParser(prog=f"{ctx.prog} {scan_cls.name}")
    for opt in ctx.specs:
        add_option(parser, opt)
    parser.add_argument("path", help="Path to the repository to scan.")
    for param in scan_cls.parameters:
        kwargs: dict[str, Any] = {"help": param.help, "default": param.default}
        if param.choices is not None:
            kwargs["choices"] = param.choices
        if param.type is not None:
            kwargs["type"] = param.type
        parser.add_argument(f"--{param.name}", **kwargs)
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="Write the report to FILE instead of stdout.",
    )
    if scan_cls.resolves_dependencies:
        parser.add_argument(
            "--allow-code-execution",
            action="store_true",
            help="Let dependency resolution build source packages when needed "
            "(e.g. sdist-only Python packages), which runs untrusted repository "
            "code. Off by default.",
        )
    for opt in REPORT_FORMAT_OPTIONS:
        add_option(parser, opt)
    return parser


class ScanGroup(CommandGroup):
    """The `scan` group: dispatch via the scan registry."""

    name = "scan"
    help = "Scan a repository."
    options: tuple[Option, ...] = ()

    def dispatch(self, argv: list[str], ctx: Context) -> int:
        remaining = ctx.parse(self.name, self.options, argv)
        prog = ctx.prog
        cumulative = ctx.specs
        if not remaining:
            print_help(
                prog,
                cumulative,
                {n: cls.summary for n, cls in SCANS.items()},
                description=self.help,
                to_stderr=True,
            )
            return 2  # a scan type is required
        if remaining[0] in ("-h", "--help"):
            print_help(
                prog,
                cumulative,
                {n: cls.summary for n, cls in SCANS.items()},
                description=self.help,
            )
            return 0
        scan_cls = SCANS.get(remaining[0])
        if scan_cls is None:
            return unknown_command(prog, remaining[0], SCANS)
        return _run_scan(scan_cls, remaining[1:], ctx)


def _run_scan(scan_cls: type[Scan], argv: list[str], ctx: Context) -> int:
    """Parse one scan's args and run the scan against the repository."""
    parser = build_scan_parser(scan_cls, ctx)
    values = vars(parser.parse_args(argv, namespace=argparse.Namespace(**ctx.values)))

    path = os.path.abspath(values["path"])
    if not os.path.isdir(path):
        logger.error("not a directory: %s", values["path"])
        return 2
    scan_kwargs = {param.name: values[param.name] for param in scan_cls.parameters}
    invalid = check_parameters(scan_cls.parameters, scan_kwargs)
    if invalid is not None:
        logger.error("%s", invalid)
        return 2

    allow_code_execution = (
        values["allow_code_execution"] if scan_cls.resolves_dependencies else False
    )
    with start_session(
        values["backend"], tool_image=True, mount_source=path
    ) as session:
        if not session.ok:
            return session.exit_code
        assert session.target is not None  # a source was given, so target is set
        fmt = output.Format(values["format"]) if values["format"] else None
        return scan_cmd.run_scan_command(
            scan_cls(**scan_kwargs),
            session.context,
            session.target,
            session.tool_root,
            output_file=values["output"],
            fmt=fmt,
            limit=values["limit"],
            wrap=values["wrap"],
            uid=values["uid"],
            resolved_parent=session.resolved_parent,
            allow_code_execution=allow_code_execution,
        )
