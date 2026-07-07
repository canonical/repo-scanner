"""Execution/build backends: lxd, docker, local."""

import os
from dataclasses import dataclass
from typing import Protocol

from repo_scanner import config
from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.lxd import LxdContext
from repo_scanner.execution.process import Failure, run_process
from repo_scanner.image.build_spec import BASE_IMAGE, build_spec
from repo_scanner.image.builder import ImageBuilder, ensure_image
from repo_scanner.image.docker import DockerImageBuilder
from repo_scanner.image.lxd import LxdImageBuilder
from repo_scanner.tools.install import current_platform


@dataclass(frozen=True)
class Availability:
    """Whether a backend is usable on this host, with a reason to show the user."""

    ok: bool
    reason: str = ""


def _probe(command: list[str]) -> Availability:
    """Availability from a quick liveness command (e.g. `docker info`): ok on exit 0,
    otherwise not, carrying the reason."""
    result = run_process(command, timeout=10)
    if isinstance(result, Failure):
        return Availability(ok=False, reason=result.reason)
    if result.exit_code != 0:
        return Availability(
            ok=False, reason=result.stderr.strip() or f"{command[0]} is not available"
        )
    return Availability(ok=True)


class Backend(Protocol):
    """A place reposcan can work: it reports its availability and produces a context to
    run in (optionally from a specific `image`) and the image builder to build for.
    `image_builder` is None for a backend that cannot build images (local)."""

    name: str

    def availability(self) -> Availability: ...

    def context(self, image: str | None = None) -> ExecutionContext: ...

    def image_builder(self) -> ImageBuilder | None: ...


class LxdBackend:
    name = "lxd"

    def availability(self) -> Availability:
        return _probe(["lxc", "info"])

    def context(self, image: str | None = None) -> ExecutionContext:
        return LxdContext(image or BASE_IMAGE)

    def image_builder(self) -> ImageBuilder:
        return LxdImageBuilder()


class DockerBackend:
    name = "docker"

    def availability(self) -> Availability:
        return _probe(["docker", "info"])

    def context(self, image: str | None = None) -> ExecutionContext:
        return DockerContext(image or BASE_IMAGE)

    def image_builder(self) -> ImageBuilder:
        return DockerImageBuilder()


class LocalBackend:
    name = "local"

    def availability(self) -> Availability:
        return Availability(ok=True, reason="runs on the host")

    def context(self, image: str | None = None) -> ExecutionContext:
        return LocalContext()  # runs on the host; there is no image

    def image_builder(self) -> None:
        return None  # tools install onto the host, not into an image


# Backends in selection-precedence order: containers preferred, local last.
_BACKENDS: tuple[Backend, ...] = (LxdBackend(), DockerBackend(), LocalBackend())
_BY_NAME = {backend.name: backend for backend in _BACKENDS}

# Values accepted for --backend and the `backend` config key.
BACKEND_NAMES = ("auto", *_BY_NAME)


def select_backend(requested: str | None) -> Backend | Failure:
    """Choose a backend. `requested` is the command-line choice, or None to fall back
    to $REPOSCAN_BACKEND, then saved config, then 'auto'. 'auto' returns the first
    available of lxd, docker, then local."""
    backend = requested or os.environ.get("REPOSCAN_BACKEND")
    if not backend:
        saved = config.load().get("backend")
        backend = saved if isinstance(saved, str) else "auto"

    if backend != "auto" and backend not in _BY_NAME:
        return Failure(reason=f"unknown backend {backend}")

    for candidate in _BACKENDS:
        if not (backend == candidate.name or backend == "auto"):
            continue
        availability = candidate.availability()
        if availability.ok:
            return candidate
        if backend == candidate.name:
            return Failure(
                f"selected backend ({candidate.name}) not available: "
                f"{availability.reason}"
            )
    return Failure(reason="no execution backend is available")


def tool_context(backend: Backend) -> ExecutionContext | Failure:
    """A context with the tools available. For local that is the host (tools live
    there, installed by `bootstrap`). For a container backend it is a container
    running the tool image, which is built on demand and hash-verified before use; a
    build failure is returned as a Failure."""
    builder = backend.image_builder()
    if builder is None:
        return backend.context()
    reference = ensure_image(builder, build_spec(current_platform()))
    if isinstance(reference, Failure):
        return reference
    return backend.context(reference)
