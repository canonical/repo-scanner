# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan invoke` subcommand: run an installed tool, passing args through."""

from repo_scanner.backends import start_session
from repo_scanner.cli.nodes import Command
from repo_scanner.cli.options import Option, Values
from repo_scanner.cli.parsing import command_argv
from repo_scanner.commands import invoke_cmd


class InvokeCommand(Command):
    name = "invoke"
    help = "Run an installed tool, passing arguments through to it."
    options = (
        Option(
            ("--timeout",),
            "timeout",
            default=None,
            type=float,
            metavar="SECONDS",
            help="Kill the tool if it runs longer than this (default: no limit).",
        ),
        Option(("tool",), "tool", positional=True, help="The installed tool to run."),
        Option(
            ("argv",),
            "argv",
            positional=True,
            remainder=True,
            help="Arguments for the tool. Separate them from reposcan's own options "
            "with a double-hyphen, e.g. reposcan invoke semgrep -- --config auto .",
        ),
    )

    def run(self, values: Values) -> int:
        """Run an installed tool in the tool environment, passing arguments through."""
        with start_session(values["backend"], tool_image=True) as session:
            if not session.ok:
                return session.exit_code
            return invoke_cmd.run_invoke(
                session.context,
                values["tool"],
                command_argv(values["argv"]),
                session.tool_root,
                timeout=values["timeout"],
            )
