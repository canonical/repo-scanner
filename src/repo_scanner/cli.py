"""Command-line entry point for reposcan."""

import argparse
import logging

from repo_scanner.commands import (
    bootstrap_cmd,
    config_cmd,
    exec_cmd,
    invoke_cmd,
    tools_cmd,
)
from repo_scanner.execution.context import Failure
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.select import BACKENDS, select_context
from repo_scanner.paths import tools_root
from repo_scanner.tools.install import current_platform

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

    # SUBCOMMAND: TOOLS
    subcommands.add_parser(
        "tools", help="List the scanning tools and whether each is installed."
    )

    # SUBCOMMAND: BOOTSTRAP
    bootstrap_parser = subcommands.add_parser(
        "bootstrap",
        help="Install tools onto the host. Runs locally unless --backend is given.",
    )
    bootstrap_parser.add_argument(
        "tools",
        nargs="*",
        metavar="TOOL",
        help="Tools to install; their prerequisites are added automatically. "
        "Installs every tool when none are named.",
    )

    # SUBCOMMAND: INVOKE
    invoke_parser = subcommands.add_parser(
        "invoke",
        help="Run an installed tool, passing arguments through to it.",
    )
    invoke_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Kill the tool if it runs longer than this (default: no limit).",
    )
    invoke_parser.add_argument("tool", help="The installed tool to run.")
    invoke_parser.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="Arguments for the tool. Separate them from reposcan's own options with "
        "a double-hyphen, e.g. reposcan invoke semgrep -- --config auto .",
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
        case "tools":
            # A local catalog listing; no execution context needed.
            return tools_cmd.run_tools(str(tools_root()))
        case "bootstrap":
            # Tools install onto the host to be useful, so default to local; an
            # explicit --backend can still target a container.
            ctx = (
                LocalContext() if args.backend is None else select_context(args.backend)
            )
            if isinstance(ctx, Failure):
                logger.error(ctx.reason)
                return 2
            error = ctx.start()
            if error is not None:
                logger.error(error.reason)
                return 1
            try:
                return bootstrap_cmd.run_bootstrap(
                    ctx, args.tools, current_platform(), str(tools_root())
                )
            finally:
                ctx.stop()
        case "invoke":
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
                tool_args = (
                    args.argv[1:] if args.argv and args.argv[0] == "--" else args.argv
                )
                return invoke_cmd.run_invoke(
                    ctx, args.tool, tool_args, str(tools_root()), timeout=args.timeout
                )
            finally:
                ctx.stop()
        case _:
            logger.error("Unrecognized command; try '--help'")
            return 2
