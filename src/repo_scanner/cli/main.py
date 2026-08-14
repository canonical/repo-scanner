# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI entry point.

Parses global options, configures logging, parses and dispatches the subcommand.
"""

import logging
import sys

from repo_scanner.cli.commands import (
    BootstrapCommand,
    ConfigGroup,
    ExecCommand,
    ImageGroup,
    InvokeCommand,
    RenderCommand,
    ScanGroup,
    ToolsCommand,
)
from repo_scanner.cli.nodes import Context, Step
from repo_scanner.cli.options import GLOBAL_OPTIONS, LOG_LEVELS
from repo_scanner.cli.parsing import print_help, unknown_command

ROOT_SUBCOMMANDS: dict[str, type[Step]] = {
    s.name: s
    for s in (
        ExecCommand,
        ToolsCommand,
        BootstrapCommand,
        InvokeCommand,
        RenderCommand,
        ImageGroup,
        ConfigGroup,
        ScanGroup,
    )
}

ROOT_DESCRIPTION = "Run security scans against a locally-cloned repository."


class _LevelFormatter(logging.Formatter):
    """Add the logger name to warnings and errors; keep info messages plain."""

    _plain = logging.Formatter("reposcan: %(message)s")
    _named = logging.Formatter("reposcan: %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        chosen = self._named if record.levelno >= logging.WARNING else self._plain
        return chosen.format(record)


def configure_logging(verbosity: str) -> None:
    """Configure root logging at the level named by `verbosity`."""
    handler = logging.StreamHandler()
    handler.setFormatter(_LevelFormatter())
    logging.basicConfig(level=LOG_LEVELS[verbosity], handlers=[handler])


def main(argv: list[str] | None = None) -> int:
    """Parse args, configure logging, and dispatch to the selected subcommand."""
    root_argv = sys.argv[1:] if argv is None else list(argv)
    ctx = Context({}, GLOBAL_OPTIONS, "reposcan")
    remaining = ctx.parse("", (), root_argv)  # parse globals (no name to append)
    if not remaining:
        print_help(
            "reposcan",
            GLOBAL_OPTIONS,
            {n: s.help for n, s in ROOT_SUBCOMMANDS.items()},
            description=ROOT_DESCRIPTION,
            to_stderr=True,
        )
        return 2  # a subcommand is required
    if remaining[0] in ("-h", "--help"):
        print_help(
            "reposcan",
            GLOBAL_OPTIONS,
            {n: s.help for n, s in ROOT_SUBCOMMANDS.items()},
            description=ROOT_DESCRIPTION,
        )
        return 0
    configure_logging(ctx.values["verbosity"])
    subcmd_cls = ROOT_SUBCOMMANDS.get(remaining[0])
    if subcmd_cls is None:
        return unknown_command("reposcan", remaining[0], ROOT_SUBCOMMANDS)
    return subcmd_cls().dispatch(remaining[1:], ctx)
