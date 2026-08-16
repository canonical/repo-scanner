# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan tools` command: list tools and their install status."""

from repo_scanner.actions.tools import list_tools
from repo_scanner.cli.commands.base import Command
from repo_scanner.paths import tools_root


class ToolsCommand(Command):
    name = "tools"
    help = "List the scanning tools and whether each is installed."

    def run(self) -> int:
        return list_tools(str(tools_root()))
