# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Execution/build backends: lxd, docker, local."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from repo_scanner.execution.context import (
    RESOLVED_PARENT,
    ExecutionContext,
    RunUser,
    mounted_target,
)
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.lxd import LxdContext
from repo_scanner.execution.process import Failure, run_process
from repo_scanner.image.build_spec import BASE_IMAGE, INSTALL_ROOT, build_spec
from repo_scanner.image.builder import ImageBuilder, ensure_image
from repo_scanner.image.docker import DockerImageBuilder
from repo_scanner.image.lxd import LxdImageBuilder
from repo_scanner.image.remote import (
    DockerRemote,
    ImagePuller,
    ensure_pulled,
    resolve_remote_ref,
)
from repo_scanner.paths import resolve_cache, tools_root
from repo_scanner.tools.install import current_platform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Availability:
    """Whether a backend is usable on this host, with a reason to show the user."""

    ok: bool
    reason: str = ""


def _probe(command: list[str]) -> Availability:
    """Report availability from a quick liveness command such as `docker info`.

    The command is ok on exit 0, otherwise not, carrying the reason.
    """
    result = run_process(command, timeout=10)
    if isinstance(result, Failure):
        return Availability(ok=False, reason=result.reason)
    if result.exit_code != 0:
        return Availability(
            ok=False, reason=result.stderr.strip() or f"{command[0]} is not available"
        )
    return Availability(ok=True)


class Backend(Protocol):
    """A place reposcan can work, reporting availability and producing a context.

    It produces a context to run in (optionally from a specific `image`) and the
    image builder to build for. `image_builder` is None for a backend that cannot
    build images (local).
    """

    name: str

    def availability(self) -> Availability: ...

    def context(
        self,
        image: str | None = None,
        *,
        mount_source: str | None = None,
        user: RunUser | None = None,
    ) -> ExecutionContext:
        """A context to run in, optionally from `image`, with `mount_source` mounted.

        Args:
            image: The image to run, or None for the backend's default base.
            mount_source: A host directory to make available for scanning, or None.
            user: The identity in-container processes run as by default (container
                backends only); None runs as root.

        Returns:
            An unstarted execution context.
        """
        ...

    def image_builder(self) -> ImageBuilder | None: ...

    def image_puller(self) -> ImagePuller | None:
        """The puller to retrieve a remote image on this backend, or None.

        None for a backend that cannot (local, and lxd for now), which builds
        locally.
        """
        ...

    def tool_root(self) -> str:
        """Where tools live for this backend.

        The host tools dir for local, the image install root for a container.
        """
        ...

    def get_resolved_parent(self) -> str:
        """The directory dependency resolution copies a repo under for this backend.

        A user-writable cache dir for local, the in-image RESOLVED_PARENT for a
        container. Parallels `tool_root`: a host path locally, an image path in a
        container.
        """
        ...


class LxdBackend:
    name = "lxd"

    def availability(self) -> Availability:
        return _probe(["lxc", "info"])

    def context(
        self,
        image: str | None = None,
        *,
        mount_source: str | None = None,
        user: RunUser | None = None,
    ) -> ExecutionContext:
        return LxdContext(image or BASE_IMAGE, mount_source=mount_source, user=user)

    def image_builder(self) -> ImageBuilder:
        return LxdImageBuilder()

    def image_puller(self) -> None:
        return None  # LXD consumes OCI images differently; not supported yet

    def tool_root(self) -> str:
        return INSTALL_ROOT

    def get_resolved_parent(self) -> str:
        return RESOLVED_PARENT


class DockerBackend:
    name = "docker"

    def availability(self) -> Availability:
        return _probe(["docker", "info"])

    def context(
        self,
        image: str | None = None,
        *,
        mount_source: str | None = None,
        user: RunUser | None = None,
    ) -> ExecutionContext:
        return DockerContext(image or BASE_IMAGE, mount_source=mount_source, user=user)

    def image_builder(self) -> ImageBuilder:
        return DockerImageBuilder()

    def image_puller(self) -> ImagePuller:
        return DockerRemote()

    def tool_root(self) -> str:
        return INSTALL_ROOT

    def get_resolved_parent(self) -> str:
        return RESOLVED_PARENT


class LocalBackend:
    name = "local"

    def availability(self) -> Availability:
        return Availability(ok=True, reason="runs on the host")

    def context(
        self,
        image: str | None = None,
        *,
        mount_source: str | None = None,
        user: RunUser | None = None,
    ) -> ExecutionContext:
        return LocalContext()

    def image_builder(self) -> None:
        return None  # tools install onto the host, not into an image

    def image_puller(self) -> None:
        return None  # tools run on the host; there is no image to pull

    def tool_root(self) -> str:
        return str(tools_root())

    def get_resolved_parent(self) -> str:
        # A user-writable cache dir: the host has no root-provisioned scratch dir,
        # and resolution must not mutate the user's actual repo.
        return str(resolve_cache())


# Backends in selection-precedence order: containers preferred, local last.
_BACKENDS: tuple[Backend, ...] = (LxdBackend(), DockerBackend(), LocalBackend())
_BY_NAME = {backend.name: backend for backend in _BACKENDS}

# Values accepted for --backend and the `backend` config key.
BACKEND_NAMES = ("auto", *_BY_NAME)


def select_backend(requested: str | None) -> Backend | Failure:
    """Choose a backend.

    Args:
        requested: The resolved backend name, or None for 'auto'. (Env and config
            fallback happens during parameter resolution, upstream of here.)

    Returns:
        The selected backend; 'auto' picks the first available of lxd, docker,
        then local. A Failure if the requested backend is unknown or
        unavailable, or if none is available.
    """
    backend = requested or "auto"

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


def context_for(
    backend: Backend,
    mount_source: str | None = None,
    *,
    tool_image: bool = True,
    image: str | None = None,
    user: RunUser | None = None,
) -> ExecutionContext | Failure:
    """The execution context to run in.

    A local backend runs on the host (images do not apply). A container backend runs,
    in order of preference:

      - the given/configured remote `image`, whenever one is set and the backend can
        pull it -- honored regardless of `tool_image`;
      - otherwise the tool image, built on demand and hash-verified, when `tool_image`
        is set;
      - otherwise a plain base container.

    Args:
        backend: The backend to produce a context for.
        mount_source: A host directory to make available for scanning, or None.
        tool_image: Prefer the verified tool image (built on demand) when no explicit
            `image` is given; else a plain base container.
        image: A resolved remote image reference to pull and run. When set (and the
            backend can pull), it is used whether or not `tool_image` is set.
        user: The identity in-container processes run as by default (container
            backends only); None runs as root.

    Returns:
        A ready context, or a Failure if a pull or build failed.
    """
    builder = backend.image_builder()
    if builder is None:
        if image:
            logger.warning(
                "the %s backend runs on the host; the configured image %r is ignored",
                backend.name,
                image,
            )
        return backend.context(mount_source=mount_source, user=user)  # local: the host

    if image:
        puller = backend.image_puller()
        if puller is not None:
            reference = ensure_pulled(puller, resolve_remote_ref(image))
            if isinstance(reference, Failure):
                return reference
            return backend.context(reference, mount_source=mount_source, user=user)
        logger.warning(
            "the %s backend cannot pull the configured image %r; %s",
            backend.name,
            image,
            "building the tool image" if tool_image else "using a plain container",
        )

    if tool_image:
        reference = ensure_image(builder, build_spec(current_platform()))
        if isinstance(reference, Failure):
            return reference
        return backend.context(reference, mount_source=mount_source, user=user)

    return backend.context(mount_source=mount_source, user=user)  # plain base container


@dataclass(frozen=True)
class Session:
    """A started place to run a command in.

    It carries its context and where its tools live, or -- when not `ok` -- a
    failure exit code. `context` is valid only when `ok`; it is stopped when the
    `start_session` block exits.
    """

    _context: ExecutionContext | None
    tool_root: str
    exit_code: int
    target: str | None = None  # where the scanned source is reachable in the context
    resolved_parent: str = ""  # where dependency resolution copies the repo

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def context(self) -> ExecutionContext:
        assert self._context is not None  # valid only when ok
        return self._context


@contextmanager
def start_session(
    requested_backend: str | None,
    *,
    tool_image: bool,
    mount_source: str | None = None,
    image: str | None = None,
    user: RunUser | None = None,
) -> Generator[Session]:
    """Select a backend and start a context in it.

    Yields a session and stops it on exit. A failed step yields a not-`ok`
    Session carrying the exit code: 2 when no backend could be selected, 1 when
    the context could not be built or started.

    Args:
        requested_backend: The backend to select, or None for 'auto'.
        tool_image: Use the verified tool image (built on demand) when True,
            else a plain container.
        mount_source: A host directory to make available for scanning, or None. The
            session's `target` reports where it is reachable in the context.
        image: A resolved remote image to pull and run instead of building the tool
            image locally, or None to build it.
        user: The identity in-container processes run as by default (container backends
            only); None runs as root. A backend that shifts uids (LXD) maps it before
            the rootfs is shifted.
    """
    backend = select_backend(requested_backend)
    if isinstance(backend, Failure):
        logger.error(backend.reason)
        yield Session(None, "", 2)
        return
    ctx = context_for(
        backend, mount_source, tool_image=tool_image, image=image, user=user
    )
    if isinstance(ctx, Failure):
        logger.error(ctx.reason)
        yield Session(None, "", 1)
        return
    error = ctx.start()
    if error is not None:
        logger.error(error.reason)
        yield Session(None, "", 1)
        return
    # Local runs the source in place; a container mounts it under MOUNT_PARENT.
    target = None
    if mount_source is not None:
        if backend.image_builder() is None:
            target = mount_source
        else:
            target = mounted_target(mount_source)
    try:
        yield Session(
            ctx, backend.tool_root(), 0, target, backend.get_resolved_parent()
        )
    finally:
        ctx.stop()
