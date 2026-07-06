"""Tests for the tool model and install shape (repo_scanner.tools)."""

from repo_scanner.tools.install import install_plan
from repo_scanner.tools.model import (
    Download,
    GoTool,
    NativeBinary,
    Platform,
    PypiTool,
    ToolKind,
)

_LINUX = Platform("linux", "amd64")
_ROOT = "/opt/tools"

# Prerequisites first, so the dependent tools below can name them in `requires`.
_GO_SDK = NativeBinary(
    name="go",
    version="1.26.4",
    downloads=(Download("linux", "amd64", "https://go.dev/dl/go.tar.gz", "def456"),),
)
_UV = NativeBinary(
    name="uv",
    version="0.11.25",
    downloads=(Download("linux", "amd64", "https://example/uv.tar.gz", "uv-hash"),),
)
_TRUFFLEHOG = NativeBinary(
    name="trufflehog",
    version="3.95.6",
    downloads=(
        Download("linux", "amd64", "https://example/trufflehog.tar.gz", "abc123"),
    ),
)
_SEMGREP = PypiTool(
    name="semgrep",
    version="1.168.0",
    requirements="semgrep==1.168.0 --hash=sha256:deadbeef",
    entrypoints=("semgrep",),
    requires=(_UV,),
)
_GOVULNCHECK = GoTool(
    name="govulncheck",
    version="1.5.0",
    module="golang.org/x/vuln",
    module_sum="h1:modhash=",
    gomod_sum="h1:gomodhash=",
    package="golang.org/x/vuln/cmd/govulncheck",
    requires=(_GO_SDK,),
)


def test_kinds() -> None:
    assert _SEMGREP.kind is ToolKind.PYPI
    assert _TRUFFLEHOG.kind is ToolKind.NATIVE_BINARY
    assert _GOVULNCHECK.kind is ToolKind.GO
    # uv and the Go SDK are both pinned prebuilt downloads.
    assert _GO_SDK.kind is ToolKind.NATIVE_BINARY
    assert _GO_SDK.name == "go"
    assert _UV.kind is ToolKind.NATIVE_BINARY
    assert _UV.name == "uv"


def test_requires_names_each_tools_concrete_dependencies() -> None:
    assert _SEMGREP.requires == (_UV,)  # PyPI tools depend on uv
    assert _GOVULNCHECK.requires == (_GO_SDK,)  # Go tools depend on the Go SDK
    assert _TRUFFLEHOG.requires == ()
    assert _UV.requires == ()
    assert _GO_SDK.requires == ()


def test_installed_path_points_at_the_executable() -> None:
    assert _TRUFFLEHOG.installed_path(_ROOT) == "/opt/tools/bin/trufflehog"
    assert _GOVULNCHECK.installed_path(_ROOT) == "/opt/tools/bin/govulncheck"
    assert _UV.installed_path(_ROOT) == "/opt/tools/bin/uv"
    assert _SEMGREP.installed_path(_ROOT) == "/opt/tools/bin/semgrep"  # entrypoint
    assert _GO_SDK.installed_path(_ROOT) == "/opt/tools/bin/go"


def test_uv_installs_as_a_pinned_native_binary() -> None:
    lines = "\n".join(_UV.install_commands(_LINUX, _ROOT))
    assert "https://example/uv.tar.gz" in lines
    assert "uv-hash" in lines  # sha256 verification
    assert "/opt/tools/bin/uv" in lines


def test_native_binary_install_downloads_verifies_and_symlinks() -> None:
    lines = "\n".join(_TRUFFLEHOG.install_commands(_LINUX, _ROOT))
    assert "https://example/trufflehog.tar.gz" in lines
    assert "abc123" in lines  # sha256 verification
    # The archive is extracted whole under opt/, the executable located by name
    # (it may be nested), and symlinked into bin/.
    assert "tar -xf" in lines and "/opt/tools/opt/trufflehog" in lines
    assert "find" in lines and '-name "trufflehog"' in lines
    assert "ln -sf" in lines and "/opt/tools/bin/trufflehog" in lines


def test_missing_download_fails_loudly() -> None:
    commands = _TRUFFLEHOG.install_commands(Platform("linux", "arm64"), _ROOT)
    assert any("exit 1" in line for line in commands)


def test_pypi_install_writes_the_lock_inline_then_installs_with_hashes() -> None:
    lines = "\n".join(_SEMGREP.install_commands(_LINUX, _ROOT))
    assert "--hash=sha256:deadbeef" in lines  # lock contents written inline
    assert "--require-hashes" in lines
    assert "/opt/tools/pypi/semgrep.txt" in lines  # written, then installed from
    assert "/opt/tools/bin/uv" in lines  # uses the uv we installed, not a PATH uv


def test_multi_file_download_is_kept_whole_and_symlinked() -> None:
    # The Go toolchain is a multi-file download: it is extracted whole and its go
    # executable is symlinked into bin/, never copied out as a lone binary (that would
    # strand it from its GOROOT). Its install uses the same path as any native binary.
    lines = "\n".join(_GO_SDK.install_commands(_LINUX, _ROOT))
    assert "tar -xf" in lines and "/opt/tools/opt/go" in lines
    assert "ln -sf" in lines and "/opt/tools/bin/go" in lines
    assert "install -m 0755" not in lines  # not copied out as a single binary


def test_go_install_pins_the_module_hash_and_disables_the_public_db() -> None:
    lines = "\n".join(_GOVULNCHECK.install_commands(_LINUX, _ROOT))
    assert "h1:modhash=" in lines  # the stored go.sum hash
    assert "GOSUMDB=off" in lines  # verified against our pin, not sum.golang.org
    assert "golang.org/x/vuln/cmd/govulncheck@v1.5.0" in lines
    # It builds with the go binary from the SDK it depends on.
    assert "/opt/tools/bin/go" in lines


def test_install_plan_includes_prerequisites_ordered_and_deduped() -> None:
    # Request the dependents plus one explicit prerequisite; install_plan pulls in the
    # missing prerequisites, de-dupes, and orders each tool after what it requires.
    plan = install_plan([_SEMGREP, _GOVULNCHECK, _UV], _LINUX, _ROOT)
    names = [step.tool.name for step in plan]
    assert all(isinstance(step.commands, list) for step in plan)
    assert set(names) == {"uv", "semgrep", "go", "govulncheck"}  # go pulled in
    assert names.count("uv") == 1  # requested and required by semgrep, listed once
    assert names.index("go") < names.index("govulncheck")  # Go SDK before Go tools
    assert names.index("uv") < names.index("semgrep")  # uv before PyPI tools
