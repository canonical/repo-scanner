"""The Tool model: reposcan's external tools, defined in code.

Every tool is one of a few kinds: a PyPI package, a prebuilt native binary, a Go
module built with `go install`, or the pinned Go toolchain used to build the Go
tools. A tool carries its own supply-chain pins so the whole set of tools and their
pins is auditable in one place rather than split across a separate manifest:

  - native binaries and the Go SDK pin each per-platform download by sha256;
  - Go tools pin the module by its go.sum h1 hashes, verified at build;
  - PyPI tools install from a hash-pinned requirements lock (--require-hashes).

Each tool also knows how to install itself: `install_commands(platform, install_root)`
returns the shell lines that install it, for a platform, under an install root. Those
lines are the single definition that both `reposcan bootstrap` (run through an
execution context) and image generation (a build script) consume; see
tools/install.py.
"""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Protocol


class ToolKind(str, Enum):
    PYPI = "pypi"
    NATIVE_BINARY = "native_binary"
    GO = "go"
    GO_SDK = "go_sdk"
    UV = "uv"


@dataclass(frozen=True)
class Download:
    """A downloadable artifact for one OS/arch, pinned by sha256."""

    os: str
    arch: str
    url: str
    sha256: str


@dataclass(frozen=True)
class Platform:
    """An OS/arch that tools are installed for."""

    os: str  # e.g. "linux"
    arch: str  # e.g. "amd64"


# Shell command that visibly fails the install when a tool has no build for the target
_NO_DOWNLOAD = "echo 'no {name} {version} build for {os}/{arch}' >&2; exit 1"


class Tool(Protocol):
    """Common identity and install behavior of every tool, whatever its kind."""

    kind: ClassVar[ToolKind]

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def install_commands(self, platform: Platform, install_root: str) -> list[str]:
        """Shell lines that install this tool, for `platform`, under `install_root`.
        Each line is run via the execution context (bootstrap) or concatenated into
        an image build script (image generation)."""
        ...


@dataclass(frozen=True)
class PypiTool:
    """A tool distributed on PyPI, installed into an isolated venv from a hash-pinned
    requirements lock. `requirements` is the lock's contents (a --generate-hashes
    file); install writes it into place first, like the Go go.sum, so nothing needs
    to pre-exist in the container. `entrypoints` are the console scripts it provides,
    linked onto the tool bin dir."""

    name: str
    version: str
    requirements: str
    entrypoints: tuple[str, ...] = ()
    kind: ClassVar[ToolKind] = ToolKind.PYPI

    def install_commands(self, platform: Platform, install_root: str) -> list[str]:
        uv = f"{install_root}/bin/uv"  # provided by Uv, installed first
        pypi = f"{install_root}/pypi"
        venv = f"{pypi}/{self.name}"
        lock = f"{pypi}/{self.name}.txt"
        # Write the pinned lock into place first (a quoted heredoc keeps the contents
        # literal), so the install needs no file to pre-exist in the container.
        write_lock = (
            f'mkdir -p "{pypi}" && cat > "{lock}" <<\'REPOSCAN_LOCK\'\n'
            f"{self.requirements}\n"
            f"REPOSCAN_LOCK"
        )
        lines = [
            write_lock,
            f'"{uv}" venv "{venv}"',
            f'"{uv}" pip install --python "{venv}" --require-hashes -r "{lock}"',
        ]
        lines += [
            f'ln -sf "{venv}/bin/{entrypoint}" "{install_root}/bin/{entrypoint}"'
            for entrypoint in self.entrypoints
        ]
        return lines


@dataclass(frozen=True, kw_only=True)
class DownloadableTool:
    """Base for tools installed from a pinned per-platform Download: it owns the
    downloads and the shared download-and-verify step. Subclasses add how the
    downloaded artifact is placed. Not a Tool on its own (it has no name/version)."""

    downloads: tuple[Download, ...] = ()

    def _download_for(self, platform: Platform) -> Download | None:
        for download in self.downloads:
            if download.os == platform.os and download.arch == platform.arch:
                return download
        return None

    def _fetch(self, download: Download, archive: str) -> list[str]:
        """Download `download` to `archive` and verify its sha256."""
        return [
            f'curl -fsSL "{download.url}" -o "{archive}"',
            f'echo "{download.sha256}  {archive}" | sha256sum -c -',
        ]


@dataclass(frozen=True, kw_only=True)
class NativeBinary(DownloadableTool):
    """A tool shipped as a prebuilt binary, one Download per platform. `binary_name`
    is the executable's name inside the downloaded archive; it is installed as
    `bin/<name>`."""

    name: str
    version: str
    binary_name: str
    kind: ClassVar[ToolKind] = ToolKind.NATIVE_BINARY

    def install_commands(self, platform: Platform, install_root: str) -> list[str]:
        download = self._download_for(platform)
        if download is None:
            return [
                _NO_DOWNLOAD.format(
                    name=self.name,
                    version=self.version,
                    os=platform.os,
                    arch=platform.arch,
                )
            ]
        cache = f"{install_root}/cache"
        archive = f"{cache}/{self.name}-{self.version}"
        # assumes a tar archive containing `binary_name`; zip/bare-binary not handled
        return [
            f'mkdir -p "{cache}" "{install_root}/bin"',
            *self._fetch(download, archive),
            f'tar -xf "{archive}" -C "{cache}"',
            f'install -m 0755 "{cache}/{self.binary_name}" '
            f'"{install_root}/bin/{self.name}"',
        ]


@dataclass(frozen=True, kw_only=True)
class Uv(NativeBinary):
    """uv, the PyPI installer: a prerequisite for every PyPI tool, first-class
    alongside GoSdk. It installs exactly as a native binary (inherited); only its
    kind differs, so install_plan orders it before PyPI tools."""

    name: str = "uv"
    binary_name: str = "uv"
    kind: ClassVar[ToolKind] = ToolKind.UV


@dataclass(frozen=True)
class GoTool:
    """A tool built with `go install`, using the Go toolchain from GoSdk. Pinned by
    its go.sum h1 hashes (`module_sum`, the module zip; `gomod_sum`, its go.mod),
    verified at build against a written go.sum with the public checksum DB off.
    `package` is the go install target (defaults to `module` when it is the module
    root); `module` is the module path the go.sum entries are keyed on."""

    name: str
    version: str
    module: str
    module_sum: str
    gomod_sum: str
    package: str = ""
    kind: ClassVar[ToolKind] = ToolKind.GO

    def install_commands(self, platform: Platform, install_root: str) -> list[str]:
        go = f"{install_root}/go-sdk/go/bin/go"
        work = f"{install_root}/cache/go-build/{self.name}"
        package = self.package or self.module
        write_go_sum = (
            f"printf '%s v%s %s\\n%s v%s/go.mod %s\\n' "
            f'"{self.module}" "{self.version}" "{self.module_sum}" '
            f'"{self.module}" "{self.version}" "{self.gomod_sum}" > go.sum'
        )
        # One compound command (shared cwd): pin the module via a throwaway module's
        # go.sum and disable the public checksum DB, so the download is verified
        # against our stored hashes rather than sum.golang.org, then build from the
        # verified module cache.
        steps = [
            f'mkdir -p "{work}"',
            f'cd "{work}"',
            f'"{go}" mod init reposcan-build >/dev/null 2>&1 || true',
            f'"{go}" mod edit -require="{self.module}@v{self.version}"',
            write_go_sum,
            f'GOSUMDB=off GOFLAGS=-mod=mod "{go}" mod download "{self.module}"',
            f'GOBIN="{install_root}/bin" GOSUMDB=off GOFLAGS=-mod=mod '
            f'"{go}" install "{package}@v{self.version}"',
        ]
        return [" && ".join(steps)]


@dataclass(frozen=True, kw_only=True)
class GoSdk(DownloadableTool):
    """The pinned Go toolchain, used to build GoTools when the host lacks Go. A build
    prerequisite, not a scanning tool."""

    version: str
    kind: ClassVar[ToolKind] = ToolKind.GO_SDK

    @property
    def name(self) -> str:
        return "go"

    def install_commands(self, platform: Platform, install_root: str) -> list[str]:
        download = self._download_for(platform)
        if download is None:
            return [
                _NO_DOWNLOAD.format(
                    name=self.name,
                    version=self.version,
                    os=platform.os,
                    arch=platform.arch,
                )
            ]
        cache = f"{install_root}/cache"
        archive = f"{cache}/go-{self.version}"
        return [
            f'mkdir -p "{cache}" "{install_root}/go-sdk"',
            *self._fetch(download, archive),
            f'tar -xf "{archive}" -C "{install_root}/go-sdk"',
        ]
