# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan invoke` command: run an installed tool, passing args through."""

from repo_scanner.actions.invoke import invoke
from repo_scanner.backends import start_session
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import option, positional, remainder


class InvokeCommand(Command):
    name = "invoke"
    help = "Run an installed tool, passing arguments through to it."

    timeout: float | None = option(
        convert=float,
        help="Kill the tool if it runs longer than this (default: no limit).",
    )
    tool: str = positional(help="The installed tool to run.")
    argv: list[str] = remainder(
        help="Arguments for the tool, after a double-hyphen (invoke semgrep -- --help)."
    )

    def run(self) -> int:
        with start_session(self.backend, tool_image=True, image=self.image) as session:
            if not session.ok:
                return session.exit_code
            return invoke(
                session.context,
                self.tool,
                self.argv,
                session.tool_root,
                timeout=self.timeout,
            )
