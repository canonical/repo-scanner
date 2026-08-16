# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The composed reposcan CLI: the command tree and the `main` entry point."""

from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.commands.bootstrap import BootstrapCommand
from repo_scanner.cli.commands.config import ConfigGroup
from repo_scanner.cli.commands.exec import ExecCommand
from repo_scanner.cli.commands.image import ImageGroup
from repo_scanner.cli.commands.invoke import InvokeCommand
from repo_scanner.cli.commands.render import RenderCommand
from repo_scanner.cli.commands.scan import ScanGroup
from repo_scanner.cli.commands.tools import ToolsCommand
from repo_scanner.cli.spec import Cli, Group


class Reposcan(Group):
    name = "reposcan"
    help = "Run security scans against a locally-cloned repository."
    subcommands = (
        ExecCommand,
        ToolsCommand,
        BootstrapCommand,
        InvokeCommand,
        RenderCommand,
        ImageGroup,
        ConfigGroup,
        ScanGroup,
    )


APP = Cli(name="reposcan", root=Reposcan, base=Command)


def main(argv: list[str] | None = None) -> int:
    """The `reposcan` entry point."""
    return APP.run(argv)
