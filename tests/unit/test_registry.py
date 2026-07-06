"""Tests for the tool registry (repo_scanner.tools.registry).

These assert the registry is wired up and every tool actually carries pins; the
exact hash/URL values are data and are not re-asserted here.
"""

from repo_scanner.tools.model import GoSdk, GoTool, NativeBinary, Platform, PypiTool
from repo_scanner.tools.registry import ALL_TOOLS, CDXGEN

_LINUX = Platform("linux", "amd64")


def test_lookup_by_name_finds_a_tool_and_misses_cleanly() -> None:
    found = ALL_TOOLS.get("semgrep")
    assert found is not None
    assert found.name == "semgrep"
    assert ALL_TOOLS.get("not-a-tool") is None


def test_every_tool_carries_its_pins() -> None:
    for candidate in ALL_TOOLS.values():
        if isinstance(candidate, NativeBinary | GoSdk):
            assert candidate.downloads, f"{candidate.name} has no downloads"
            for download in candidate.downloads:
                assert len(download.sha256) == 64  # a full sha256, not a placeholder
        elif isinstance(candidate, PypiTool):
            assert "--hash=sha256:" in candidate.requirements
        elif isinstance(candidate, GoTool):
            assert candidate.module_sum.startswith("h1:")
            assert candidate.gomod_sum.startswith("h1:")
        else:
            raise ValueError(f"Unknown tool type {type(candidate).__name__}")


def test_bare_binary_installs_without_extraction() -> None:
    # cdxgen is a bare binary (no archive), so its install installs the download
    # directly rather than untarring it.
    lines = "\n".join(CDXGEN.install_commands(_LINUX, "/opt/tools"))
    assert "tar -xf" not in lines
    assert "install -m 0755" in lines
