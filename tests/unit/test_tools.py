"""Tests for the tool model and install shape (repo_scanner.tools)."""

from repo_scanner.tools.install import install_plan
from repo_scanner.tools.model import (
    Download,
    GoSdk,
    GoTool,
    NativeBinary,
    Platform,
    PypiTool,
    ToolKind,
    Uv,
)

_LINUX = Platform("linux", "amd64")
_ROOT = "/opt/tools"

_TRUFFLEHOG = NativeBinary(
    name="trufflehog",
    version="3.95.6",
    binary_name="trufflehog",
    downloads=(
        Download("linux", "amd64", "https://example/trufflehog.tar.gz", "abc123"),
    ),
)
_SEMGREP = PypiTool(
    name="semgrep",
    version="1.168.0",
    requirements="semgrep==1.168.0 --hash=sha256:deadbeef",
    entrypoints=("semgrep",),
)
_GOVULNCHECK = GoTool(
    name="govulncheck",
    version="1.5.0",
    module="golang.org/x/vuln",
    module_sum="h1:modhash=",
    gomod_sum="h1:gomodhash=",
    package="golang.org/x/vuln/cmd/govulncheck",
)
_GO_SDK = GoSdk(
    version="1.26.4",
    downloads=(Download("linux", "amd64", "https://go.dev/dl/go.tar.gz", "def456"),),
)
_UV = Uv(
    version="0.11.25",
    downloads=(Download("linux", "amd64", "https://example/uv.tar.gz", "uv-hash"),),
)


def test_kinds() -> None:
    assert _SEMGREP.kind is ToolKind.PYPI
    assert _TRUFFLEHOG.kind is ToolKind.NATIVE_BINARY
    assert _GOVULNCHECK.kind is ToolKind.GO
    assert _GO_SDK.kind is ToolKind.GO_SDK
    assert _GO_SDK.name == "go"
    assert _UV.kind is ToolKind.UV
    assert _UV.name == "uv"


def test_uv_installs_as_a_pinned_native_binary() -> None:
    lines = "\n".join(_UV.install_commands(_LINUX, _ROOT))
    assert "https://example/uv.tar.gz" in lines
    assert "uv-hash" in lines  # sha256 verification
    assert "/opt/tools/bin/uv" in lines


def test_native_binary_install_downloads_verifies_and_installs() -> None:
    lines = "\n".join(_TRUFFLEHOG.install_commands(_LINUX, _ROOT))
    assert "https://example/trufflehog.tar.gz" in lines
    assert "abc123" in lines  # sha256 verification
    assert "/opt/tools/bin/trufflehog" in lines
    # A tar archive is extracted and the binary located by name (it may be nested).
    assert "tar -xf" in lines
    assert "find" in lines and '-name "trufflehog"' in lines


def test_missing_download_fails_loudly() -> None:
    commands = _TRUFFLEHOG.install_commands(Platform("linux", "arm64"), _ROOT)
    assert any("exit 1" in line for line in commands)


def test_pypi_install_writes_the_lock_inline_then_installs_with_hashes() -> None:
    lines = "\n".join(_SEMGREP.install_commands(_LINUX, _ROOT))
    assert "--hash=sha256:deadbeef" in lines  # lock contents written inline
    assert "--require-hashes" in lines
    assert "/opt/tools/pypi/semgrep.txt" in lines  # written, then installed from
    assert "/opt/tools/bin/uv" in lines  # uses the uv we installed, not a PATH uv


def test_go_install_pins_the_module_hash_and_disables_the_public_db() -> None:
    lines = "\n".join(_GOVULNCHECK.install_commands(_LINUX, _ROOT))
    assert "h1:modhash=" in lines  # the stored go.sum hash
    assert "GOSUMDB=off" in lines  # verified against our pin, not sum.golang.org
    assert "golang.org/x/vuln/cmd/govulncheck@v1.5.0" in lines


def test_install_plan_orders_prerequisites_before_dependents() -> None:
    plan = install_plan([_SEMGREP, _GOVULNCHECK, _GO_SDK, _UV], _LINUX, _ROOT)
    names = [step.tool.name for step in plan]
    assert all(isinstance(step.commands, list) for step in plan)
    assert names.index("go") < names.index("govulncheck")  # Go SDK before Go tools
    assert names.index("uv") < names.index("semgrep")  # uv before PyPI tools
