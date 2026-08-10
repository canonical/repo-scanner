# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for working with remote images."""

import logging
from typing import Protocol

from repo_scanner.execution.process import ExecResult, Failure, run_process
from repo_scanner.image import cache

logger = logging.getLogger(__name__)

# The `canonical` shorthand: the image reposcan publishes to GHCR (see the
# publish-image workflow). A user can configure `canonical` instead of the full ref.
CANONICAL_SHORTHAND = "canonical"
CANONICAL_REF = "ghcr.io/canonical/repo-scanner:latest"


def resolve_remote_ref(value: str) -> str:
    """The image reference for a configured `image` value.

    Returns:
        The canonical published image for the `canonical` shorthand, otherwise the value
        unchanged.
    """
    return CANONICAL_REF if value == CANONICAL_SHORTHAND else value


def is_digest_pinned(ref: str) -> bool:
    """True if `ref` pins a specific image content by digest (name@sha256:...).

    Returns:
        The docker client verifies such a ref on pull, so it needs no trust-on-first-use
        record.
    """
    return "@sha256:" in ref


class ImagePuller(Protocol):
    """Pulls a published image for one backend and reports its content id."""

    name: str

    def pull(self, ref: str) -> Failure | None:
        """Fetch `ref` from its registry. None on success, or a Failure."""
        ...

    def identity(self, ref: str) -> str | None:
        """The content id of the pulled image `ref`, or None if it is not present."""
        ...


class DockerRemote:
    """Pulls published images with the docker CLI."""

    name = "docker"

    def pull(self, ref: str) -> Failure | None:
        result = run_process(["docker", "pull", ref], check=True, stream=True)
        return result if isinstance(result, Failure) else None

    def identity(self, ref: str) -> str | None:
        argv = ["docker", "image", "inspect", "--format", "{{.Id}}", ref]
        result = run_process(argv, timeout=30)
        if isinstance(result, ExecResult) and result.exit_code == 0:
            return result.stdout.strip() or None
        return None


def ensure_pulled(puller: ImagePuller, ref: str) -> str | Failure:
    """Pull `ref` and return the reference to run, or a Failure.

    A digest-pinned ref is trusted directly. A tag-only ref is pinned on first use
    and, on later pulls, refused if its content id no longer matches what was first
    recorded.

    Args:
        puller: The backend puller that fetches the image and reports its content id.
        ref: The image reference to pull.

    Returns:
        The reference to run, or a Failure if the pull failed, the image is absent
        after pulling, or a tag-only ref's content id no longer matches its record.
    """
    error = puller.pull(ref)
    if error is not None:
        return error
    identity = puller.identity(ref)
    if identity is None:
        return Failure(reason=f"{ref} is not present after pull")

    if is_digest_pinned(ref):
        return ref

    recorded = cache.recorded(ref)
    if recorded is None:
        cache.record(ref, identity)
        logger.info("pinned remote image %s to %s on first use", ref, identity)
        return ref
    if recorded == identity:
        logger.info("remote image %s verified against its recorded id; reusing", ref)
        return ref
    return Failure(
        reason=(
            f"remote image {ref} has changed since first use (recorded {recorded}, "
            f"now {identity}): the tag has moved. Pin a specific image by digest "
            f"(name@sha256:...) to accept it, or remove {ref} from the image cache."
        )
    )
