# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan tools` action: list tools and their install status."""

import os
import sys

from repo_scanner.actions.base import Action
from repo_scanner.paths import tools_root
from repo_scanner.tools.registry import TOOLS


class ToolsAction(Action):
    name = "tools"
    help = "List the scanning tools and whether each is installed."

    def run(self) -> int:
        return list_tools(str(tools_root()))


def list_tools(install_root: str) -> int:
    """List every scanning tool with its version, kind, and install status.

    Shows whether each tool is installed under `install_root`. Always returns 0.
    """
    rows = []
    for tool in TOOLS.values():
        installed = os.path.exists(tool.installed_path(install_root))
        status = "installed" if installed else "missing"
        rows.append((tool.name, tool.version, tool.kind.value, status))

    name_width, version_width, kind_width = 0, 0, 0
    for name, version, kind, _ in rows:
        name_width = max(len(name), name_width)
        version_width = max(len(version), version_width)
        kind_width = max(len(kind), kind_width)

    for name, version, kind, status in rows:
        sys.stdout.write(
            f"{name:<{name_width}}  {version:<{version_width}}  "
            f"{kind:<{kind_width}}  {status}\n"
        )
    return 0
