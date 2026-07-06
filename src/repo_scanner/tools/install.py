"""reposcan tool installation.

`reposcan bootstrap` and image generation consume the same per-tool
`install_commands`. Bootstrap runs each command through an ExecutionContext, so the
same commands install onto the host or into a Docker/LXD container. Image generation
writes them into a build/install script baked into the image. This module is the
single point that orders and groups them, so there is one definition of how each
tool installs.

The commands are grouped per tool (`ToolInstall`) rather than flattened, so each
tool is an independent failure domain: bootstrap runs each group and continues past
a failure, and image generation emits each group as its own build step. Installing
9 of 10 tools beats installing 0.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from repo_scanner.tools.model import Platform, Tool, ToolKind

# Prerequisites install before the tools that depend on them: the Go SDK before Go
# tools, and uv (the PyPI installer) before PyPI tools. Order is otherwise irrelevant.
_ORDER = {
    ToolKind.GO_SDK: 0,
    ToolKind.UV: 0,
    ToolKind.GO: 2,
    ToolKind.PYPI: 2,
}


@dataclass(frozen=True)
class ToolInstall:
    """One tool's install commands, kept as a self-contained group."""

    tool: Tool
    commands: list[str]


def install_plan(
    tools: Iterable[Tool], platform: Platform, install_root: str
) -> list[ToolInstall]:
    """Per-tool install groups for `tools`, ordered so the Go SDK precedes the Go
    tools that build against it. Each group installs independently."""
    ordered = sorted(tools, key=lambda tool: _ORDER.get(tool.kind, 1))
    return [
        ToolInstall(tool, tool.install_commands(platform, install_root))
        for tool in ordered
    ]
