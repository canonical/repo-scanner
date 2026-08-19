# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The composed reposcan CLI: the command tree and the `main` entry point."""

from repo_scanner.actions.base import Action
from repo_scanner.actions.bootstrap import BootstrapAction
from repo_scanner.actions.config import ConfigGroup
from repo_scanner.actions.exec import ExecAction
from repo_scanner.actions.image import ImageGroup
from repo_scanner.actions.render import RenderAction
from repo_scanner.actions.tools import ToolsAction
from repo_scanner.clikit import Cli, Group
from repo_scanner.scans.registry import ScanGroup


class Reposcan(Group):
    name = "reposcan"
    help = "Run security scans against a locally-cloned repository."
    subcommands = (
        ExecAction,
        ToolsAction,
        BootstrapAction,
        RenderAction,
        ImageGroup,
        ConfigGroup,
        ScanGroup,
    )


APP = Cli(name="reposcan", root=Reposcan, base=Action)


def main(argv: list[str] | None = None) -> int:
    """The `reposcan` entry point."""
    return APP.run(argv)
