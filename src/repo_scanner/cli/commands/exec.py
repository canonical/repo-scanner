# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan exec` command: run a command in the selected execution context."""

from repo_scanner.actions.exec import execute
from repo_scanner.backends import start_session
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import option, remainder


class ExecCommand(Command):
    name = "exec"
    help = "Run a command within the selected execution context."

    timeout: float | None = option(
        convert=float,
        help="Kill the command if it runs longer than this (default: no limit).",
    )
    argv: list[str] = remainder(
        help="The command to run, after a double-hyphen (reposcan exec -- semgrep -h)."
    )

    def run(self) -> int:
        with start_session(self.backend, tool_image=True, image=self.image) as session:
            if not session.ok:
                return session.exit_code
            return execute(session.context, self.argv, timeout=self.timeout)
