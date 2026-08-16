# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan bootstrap` command: install tools onto the host or a container."""

import logging
import sys

from repo_scanner.actions.bootstrap import bootstrap
from repo_scanner.backends import start_session
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import flag, positional
from repo_scanner.tools.install import current_platform

logger = logging.getLogger(__name__)


class BootstrapCommand(Command):
    name = "bootstrap"
    help = "Install tools onto the host. Runs locally unless --backend is given."

    tools: list[str] = positional(
        many=True,
        help="Tools to install; prerequisites are added. Empty installs every tool.",
    )
    confirm: bool = flag(help="Skip interactive confirmation before installing tools.")

    def run(self) -> int:
        backend = self.backend if self.backend != "auto" else "local"
        with start_session(backend, tool_image=False, image=self.image) as session:
            if not session.ok:
                return session.exit_code
            if (
                session.context.name == "local"
                and not self.confirm
                and not _confirm_host_install()
            ):
                return 1
            return bootstrap(
                session.context, self.tools, current_platform(), session.tool_root
            )


def _confirm_host_install() -> bool:
    """Confirm whether to install the scanning tools directly onto this host."""
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
