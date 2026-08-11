# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Command-line entry point for reposcan."""

import argparse
import logging
import os
from typing import Any

from repo_scanner.backends import BACKEND_NAMES, select_backend, start_session
from repo_scanner.commands import (
    bootstrap_cmd,
    config_cmd,
    exec_cmd,
    image_cmd,
    invoke_cmd,
    scan_cmd,
    tools_cmd,
)
from repo_scanner.execution.process import Failure
from repo_scanner.paths import tools_root
from repo_scanner.scans.model import Scan, check_parameters
from repo_scanner.scans.registry import SCANS
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
        choices=BACKEND_NAMES,
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
    bootstrap_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip interactive confirmation before installing tools.",
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

    # SUBCOMMAND: IMAGE
    image_parser = subcommands.add_parser(
        "image", help="Build the tool image and manage the image cache."
    )
    image_sub = image_parser.add_subparsers(dest="image_command", required=True)
    image_build = image_sub.add_parser(
        "build",
        help="Build the tool image on demand for the selected backend (docker or "
        "lxd); reused if already built.",
    )
    image_build.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if an image for this spec already exists.",
    )
    image_cache = image_sub.add_parser(
        "cache",
        help="View or manage reposcan's record of built and pulled images.",
    )
    image_cache_sub = image_cache.add_subparsers(
        dest="image_cache_command", required=True
    )
    image_cache_sub.add_parser("list", help="List the recorded image cache entries.")
    image_cache_remove = image_cache_sub.add_parser(
        "remove", help="Remove one entry by its image reference."
    )
    image_cache_remove.add_argument("reference")
    image_cache_sub.add_parser("clear", help="Remove all image cache entries.")

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
    config_unset = config_sub.add_parser("unset", help="Remove a config value.")
    config_unset.add_argument("key")

    # SUBCOMMAND: SCAN -- one subcommand per registered scan, built from its
    # declared summary and parameters (see scans/registry.py and scans/model.py).
    scan_parser = subcommands.add_parser("scan", help="Scan a repository.")
    scan_subcmd = scan_parser.add_subparsers(dest="scan_command", required=True)
    for scan_cls in SCANS.values():
        _add_scan(scan_subcmd, scan_cls)

    return parser


def _add_scan(
    scan_sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
    scan_cls: type[Scan],
) -> None:
    """Add a `scan <name>` subcommand built from the scan's declared parameters."""
    parser = scan_sub.add_parser(scan_cls.name, help=scan_cls.summary)
    parser.add_argument("path", help="Path to the repository to scan.")
    for param in scan_cls.parameters:
        options: dict[str, Any] = {"help": param.help, "default": param.default}
        if param.choices is not None:
            options["choices"] = param.choices
        if param.type is not None:
            options["type"] = param.type
        parser.add_argument(f"--{param.name}", **options)
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="Write the report to FILE instead of stdout.",
    )


class _LevelFormatter(logging.Formatter):
    """Add the logger name to warnings and errors; keep info messages plain."""

    _plain = logging.Formatter("reposcan: %(message)s")
    _named = logging.Formatter("reposcan: %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        chosen = self._named if record.levelno >= logging.WARNING else self._plain
        return chosen.format(record)


def _command_argv(argv: list[str]) -> list[str]:
    """The passthrough command/args, dropping a leading '--' separator if present."""
    return argv[1:] if argv and argv[0] == "--" else argv


def _run_config(args: argparse.Namespace) -> int:
    """Get, set, or unset a config value."""
    if args.config_command == "set":
        return config_cmd.set_value(args.key, args.value)
    if args.config_command == "unset":
        return config_cmd.unset_value(args.key)
    return config_cmd.get_value(args.key)


def _run_tools(args: argparse.Namespace) -> int:
    """List the scanning tools and their install status on the host."""
    return tools_cmd.run_tools(str(tools_root()))


def _run_exec(args: argparse.Namespace) -> int:
    """Run a command where the tools are: the tool image on a container backend."""
    with start_session(args.backend, tool_image=True) as session:
        if not session.ok:
            return session.exit_code
        return exec_cmd.run_exec(
            session.context, _command_argv(args.argv), timeout=args.timeout
        )


def _run_invoke(args: argparse.Namespace) -> int:
    """Run an installed tool in the tool environment, passing arguments through."""
    with start_session(args.backend, tool_image=True) as session:
        if not session.ok:
            return session.exit_code
        return invoke_cmd.run_invoke(
            session.context,
            args.tool,
            _command_argv(args.argv),
            session.tool_root,
            timeout=args.timeout,
        )


def _run_bootstrap(args: argparse.Namespace) -> int:
    """Install tools into a plain environment.

    Defaults to local. An explicit --backend installs into a plain container, not
    the image. A host install is confirmed first (unless --confirm).
    """
    with start_session(args.backend or "local", tool_image=False) as session:
        if not session.ok:
            return session.exit_code
        if (
            session.context.name == "local"
            and not args.confirm
            and not bootstrap_cmd.confirm_host_install()
        ):
            return 1
        return bootstrap_cmd.run_bootstrap(
            session.context, args.tools, current_platform(), session.tool_root
        )


def _run_image(args: argparse.Namespace) -> int:
    """Build the tool image, or view/manage the image cache."""
    if args.image_command == "cache":
        return _run_image_cache(args)
    # build: needs a container backend (local cannot build images).
    backend = select_backend(args.backend)
    if isinstance(backend, Failure):
        logger.error(backend.reason)
        return 2
    builder = backend.image_builder()
    if builder is None:
        logger.error("the %s backend cannot build images", backend.name)
        return 2
    return image_cmd.run_image_build(builder, force=args.force)


def _run_image_cache(args: argparse.Namespace) -> int:
    """List or manage the image cache. Reads/writes the cache file only; no backend."""
    if args.image_cache_command == "list":
        return image_cmd.run_cache_list()
    if args.image_cache_command == "remove":
        return image_cmd.run_cache_remove(args.reference)
    return image_cmd.run_cache_clear()  # clear


def _run_scan(args: argparse.Namespace) -> int:
    """Scan a repository: mount it into the tool image and run the scan's tools."""
    path = os.path.abspath(args.path)
    if not os.path.isdir(path):
        logger.error("not a directory: %s", args.path)
        return 2
    scan_cls = SCANS[args.scan_command]
    values = {param.name: getattr(args, param.name) for param in scan_cls.parameters}
    invalid = check_parameters(scan_cls.parameters, values)
    if invalid is not None:
        logger.error("%s", invalid)
        return 2
    with start_session(args.backend, tool_image=True, mount_source=path) as session:
        if not session.ok:
            return session.exit_code
        assert session.target is not None  # a source was given, so target is set
        return scan_cmd.run_scan_command(
            scan_cls(**values),
            session.context,
            session.target,
            session.tool_root,
            output=args.output,
        )


def main(argv: list[str] | None = None) -> int:
    handler = logging.StreamHandler()
    handler.setFormatter(_LevelFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    args = build_parser().parse_args(argv)

    # The parser guarantees args.command is one of these subcommands.
    match args.command:
        case "config":
            return _run_config(args)
        case "tools":
            return _run_tools(args)
        case "exec":
            return _run_exec(args)
        case "invoke":
            return _run_invoke(args)
        case "bootstrap":
            return _run_bootstrap(args)
        case "image":
            return _run_image(args)
        case "scan":
            return _run_scan(args)
        case _:  # unreachable: the parser rejects any other command
            return 2
