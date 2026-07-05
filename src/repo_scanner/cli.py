"""Command-line entry point for reposcan."""

import argparse
import logging

from repo_scanner.commands import config_cmd, exec_cmd
from repo_scanner.execution.context import Failure
from repo_scanner.execution.select import BACKENDS, select_context

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reposcan",
        description="Run security scans against a locally-cloned repository.",
    )

    # GLOBAL OPTIONS
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default=None,
        help="Execution backend to run in. Overrides $REPOSCAN_BACKEND and the "
        "saved config; if unset, falls back to those, then to auto.",
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

    # SUBCOMMAND: CONFIG
    config_parser = subcommands.add_parser(
        "config", help="Get or set persistent configuration."
    )
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_set = config_sub.add_parser("set", help="Set a config value.")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_get = config_sub.add_parser(
        "get", help="Get a config value, or all values when no key is given."
    )
    config_get.add_argument("key", nargs="?", default=None)

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

    match args.command:
        case "config":
            # config reads/writes a file only; it needs no execution context.
            if args.config_command == "set":
                return config_cmd.set_value(args.key, args.value)
            return config_cmd.get_value(args.key)
        case "exec":
            # main owns the context lifecycle; the command only runs in it.
            ctx = select_context(args.backend)
            if isinstance(ctx, Failure):
                logger.error(ctx.reason)
                return 2
            error = ctx.start()
            if error is not None:
                logger.error(error.reason)
                return 1
            try:
                # Drop the leading '--', if present.
                cmd = args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv
                return exec_cmd.run_exec(ctx, cmd, timeout=args.timeout)
            finally:
                ctx.stop()
        case _:
            logger.error("Unrecognized command; try '--help'")
            return 2
