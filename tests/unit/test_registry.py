"""Tests for the tool registry (repo_scanner.tools.registry).

These assert the registry is wired up and every tool actually carries pins; the
exact hash/URL values are data and are not re-asserted here.
"""

from repo_scanner.tools.install import install_plan
from repo_scanner.tools.model import GoTool, NativeBinary, Platform, PypiTool
from repo_scanner.tools.registry import (
    CDXGEN,
    GO_SDK,
    GOVULNCHECK,
    SEMGREP,
    TOOLS,
    TRUFFLEHOG,
    UV,
)

_LINUX = Platform("linux", "amd64")


def test_tools_lists_the_scanners_and_excludes_prerequisites() -> None:
    assert set(TOOLS) == {
        "semgrep",
        "checkov",
        "zizmor",
        "trufflehog",
        "syft",
        "grype",
        "trivy",
        "poutine",
        "cdxgen",
        "govulncheck",
    }
    # uv and the Go SDK are prerequisites, not user-facing tools.
    assert "uv" not in TOOLS
    assert "go" not in TOOLS


def test_lookup_by_name_finds_a_tool_and_misses_cleanly() -> None:
    found = TOOLS.get("semgrep")
    assert found is not None
    assert found.name == "semgrep"
    assert TOOLS.get("not-a-tool") is None


def test_every_tool_carries_its_pins() -> None:
    # install_plan pulls in the prerequisites (uv, the Go SDK), so this covers them.
    plan = install_plan(TOOLS.values(), _LINUX, "/opt/tools")
    for candidate in (step.tool for step in plan):
        if isinstance(candidate, NativeBinary):
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


def test_dependent_tools_name_their_concrete_prerequisites() -> None:
    assert SEMGREP.requires == (UV,)  # PyPI tool -> uv
    assert GOVULNCHECK.requires == (GO_SDK,)  # Go tool -> Go SDK
    assert TRUFFLEHOG.requires == ()  # native binary -> nothing
    assert UV.requires == ()


def test_bare_binary_installs_without_extraction() -> None:
    # cdxgen is a bare binary (no archive), so its install installs the download
    # directly rather than untarring it.
    lines = "\n".join(CDXGEN.install_commands(_LINUX, "/opt/tools"))
    assert "tar -xf" not in lines
    assert "install -m 0755" in lines
