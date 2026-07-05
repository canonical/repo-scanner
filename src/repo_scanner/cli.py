"""Command-line entry point for reposcan."""

import argparse
import logging

from repo_scanner.commands import exec_
from repo_scanner.execution.context import Failure
from repo_scanner.execution.select import select_context

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reposcan",
        description="Run security scans against a locally-cloned repository.",
    )

    # GLOBAL OPTIONS
    parser.add_argument(
        "--backend",
        choices=["auto", "local"],
        default="auto",
        help="Execution backend to run in (default: auto).",
    )

    # SUBCOMMANDS
    subcommands = parser.add_subparsers(dest="command", required=True)

    # SUBCOMMAND: EXEC
    exec_parser = subcommands.add_parser(
        "exec",
        help="Run a command within the selected execution context.",
    )
    exec_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Kill the command if it runs longer than this (default: no limit).",
    )
    exec_parser.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="The command to run. Separate it from reposcan's own options with a "
        "double-hyphen, e.g. reposcan exec -- semgrep --version.",
    )
    return parser


class _LevelFormatter(logging.Formatter):
    """Add the logger name to warnings and errors; keep info messages plain."""

    _plain = logging.Formatter("reposcan: %(message)s")
    _named = logging.Formatter("reposcan: %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        chosen = self._named if record.levelno >= logging.WARNING else self._plain
        return chosen.format(record)


def main(argv: list[str] | None = None) -> int:
    handler = logging.StreamHandler()
    handler.setFormatter(_LevelFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    args = build_parser().parse_args(argv)

    ctx = select_context(args.backend)
    if isinstance(ctx, Failure):
        logger.error(ctx.reason)
        return 2

    error = ctx.start()
    if error is not None:
        logger.error(error.reason)
        return 1
    try:
        match args.command:
            case "exec":
                # Drop the leading '--', if present
                cmd = args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv
                return exec_.run_exec(ctx, cmd, timeout=args.timeout)
            case _:
                logger.error("Unrecognized command; try '--help'")
                return 2
    finally:
        ctx.stop()
