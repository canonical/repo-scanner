# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan bootstrap` subcommand: install tools onto the host or a container."""

import logging
import sys

from repo_scanner.backends import start_session
from repo_scanner.cli.nodes import Command
from repo_scanner.cli.options import Option, Values
from repo_scanner.commands import bootstrap_cmd
from repo_scanner.tools.install import current_platform
from repo_scanner.tools.registry import TOOLS

logger = logging.getLogger(__name__)


class BootstrapCommand(Command):
    name = "bootstrap"
    help = "Install tools onto the host. Runs locally unless --backend is given."
    options = (
        Option(
            ("tools",),
            "tools",
            positional=True,
            choices=tuple(str(t) for t in TOOLS),
            nargs="*",
            metavar="TOOL",
            help="Tools to install; their prerequisites are added automatically. "
            "Installs every tool when none are named.",
        ),
        Option(
            ("--confirm",),
            "confirm",
            store_true=True,
            help="Skip interactive confirmation before installing tools.",
        ),
    )

    def run(self, values: Values) -> int:
        """Install tools into a plain environment.

        Defaults to local. An explicit --backend installs into a plain container,
        not the image. A host install is confirmed first (unless --confirm).
        """
        backend = values["backend"] or "local"
        with start_session(backend, tool_image=False) as session:
            if not session.ok:
                return session.exit_code
            if (
                session.context.name == "local"
                and not values["confirm"]
                and not confirm_host_install()
            ):
                return 1
            return bootstrap_cmd.run_bootstrap(
                session.context,
                values["tools"],
                current_platform(),
                session.tool_root,
            )


def confirm_host_install() -> bool:
    """Confirm whether to install the scanning tools."""
    sys.stderr.write(
        "'bootstrap' installs the scanning tools directly onto this host.\n"
        "reposcan normally runs the tools inside an ephemeral container, so this is\n"
        "not the usual path and it changes this system.\n"
    )
    if not sys.stdin.isatty():
        logger.error(
            "cannot ask for confirmation on a non-interactive terminal; re-run with "
            "--confirm to install the tools on the host"
        )
        return False
    sys.stderr.write("Install the tools on this host anyway? [y/N] ")
    sys.stderr.flush()
    try:
        reply = input()
    except EOFError:
        return False
    return reply.strip().lower() in ("y", "yes")
