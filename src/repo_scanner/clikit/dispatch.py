# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The run loop: parse argv, resolve parameters, configure logging, and dispatch."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

from repo_scanner.clikit.help import render as render_help
from repo_scanner.clikit.parse import parse
from repo_scanner.clikit.resolve import LOG_LEVELS, resolve
from repo_scanner.clikit.spec import Action, Param

if TYPE_CHECKING:
    from collections.abc import Sequence

    from repo_scanner.clikit.spec import Cli


class _LevelFormatter(logging.Formatter):
    """Name warnings and errors with their logger; keep info messages plain."""

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


def dispatch(cli: Cli, argv: Sequence[str] | None = None) -> int:
    """Parse, resolve, and run; return the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = parse(cli.root, cli.base, args, cli.name)

    if parsed.error is not None:
        print(f"{parsed.prog}: {parsed.error}", file=sys.stderr)
        return 2
    if parsed.help:
        print(render_help(parsed.node, parsed.scope, parsed.prog))
        return 0
    if parsed.command is None:  # stopped at a group; a subcommand is required
        print(render_help(parsed.node, parsed.scope, parsed.prog), file=sys.stderr)
        return 2

    # Resolve the log level first so logging is configured before the rest resolve
    # (their override/validation messages then appear at the chosen level).
    configure_logging(_log_level(cli, parsed.scope, parsed.raw))
    values, error = resolve(parsed.scope, parsed.raw)
    if error is not None:  # a bad value is a usage error, like a parse error
        print(f"{parsed.prog}: {error}", file=sys.stderr)
        return 2
    return _build(parsed.command, values).run()


def _log_level(cli: Cli, scope: list[Param], raw: dict[str, Any]) -> str:
    """Resolve just the log-level parameter, falling back to its default on error."""
    param = next((p for p in scope if p.name == cli.log_level), None)
    if param is None:
        return "info"
    values, error = resolve([param], raw)
    if error is not None:
        return str(param.default or "info")
    return values[param.name]


def _build(command: type[Action], values: dict[str, Any]) -> Action:
    """Construct the command from its resolved parameter values."""
    return command(**values)
