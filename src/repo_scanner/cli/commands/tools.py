# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan tools` subcommand: list tools and their install status."""

from repo_scanner.cli.nodes import Command
from repo_scanner.cli.options import Values
from repo_scanner.commands import tools_cmd
from repo_scanner.paths import tools_root


class ToolsCommand(Command):
    name = "tools"
    help = "List the scanning tools and whether each is installed."
    options = ()

    def run(self, values: Values) -> int:
        """List the scanning tools and their install status on the host."""
        return tools_cmd.run_tools(str(tools_root()))
