# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan exec` subcommand: run a command in the selected context."""

from repo_scanner.actions.exec import execute
from repo_scanner.backends import start_session
from repo_scanner.cli.nodes import Command
from repo_scanner.cli.options import Option, Values
from repo_scanner.cli.parsing import command_argv


class ExecCommand(Command):
    name = "exec"
    help = "Run a command within the selected execution context."
    options = (
        Option(
            ("--timeout",),
            "timeout",
            default=None,
            type=float,
            metavar="SECONDS",
            help="Kill the command if it runs longer than this (default: no limit).",
        ),
        Option(
            ("argv",),
            "argv",
            positional=True,
            remainder=True,
            help="The command to run. Separate it from reposcan's own options with "
            "a double-hyphen, e.g. reposcan exec -- semgrep --version.",
        ),
    )

    def run(self, values: Values) -> int:
        """Run a command where the tools are: the tool image on a container backend."""
        with start_session(values["backend"], tool_image=True) as session:
            if not session.ok:
                return session.exit_code
            return execute(
                session.context,
                command_argv(values["argv"]),
                timeout=values["timeout"],
            )
