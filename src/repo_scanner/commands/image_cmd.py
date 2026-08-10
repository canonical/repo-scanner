# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan image` commands: build the tool image and manage the image cache."""

import logging
import sys

from repo_scanner.execution.process import Failure
from repo_scanner.image import cache
from repo_scanner.image.build_spec import build_spec
from repo_scanner.image.builder import ImageBuilder, ensure_image
from repo_scanner.tools.install import current_platform

logger = logging.getLogger(__name__)


def run_image_build(builder: ImageBuilder, *, force: bool) -> int:
    """Build (or reuse) the tool image with `builder`.

    Args:
        builder: The image builder for the selected backend.
        force: Rebuild even when an image for this spec already exists.

    Returns:
        0 with the image reference printed, or 1 if the build failed.
    """
    spec = build_spec(current_platform())
    result = ensure_image(builder, spec, force=force)
    if isinstance(result, Failure):
        logger.error(result.reason)
        return 1
    sys.stdout.write(f"{result}\n")
    return 0


def run_cache_list() -> int:
    """Print each recorded image cache entry as `reference  identity` to stdout."""
    entries = cache.entries()
    if not entries:
        logger.info("the image cache is empty")
        return 0
    width = max(len(reference) for reference in entries)
    for reference, identity in sorted(entries.items()):
        sys.stdout.write(f"{reference:<{width}}  {identity}\n")
    return 0


def run_cache_remove(reference: str) -> int:
    """Remove `reference` from the image cache.

    Returns:
        0 when removed, 1 when it was not in the cache or the cache could not be
        written.
    """
    result = cache.remove(reference)
    if isinstance(result, Failure):
        logger.error(result.reason)
        return 1
    if not result:
        logger.error("no image cache entry for %s", reference)
        return 1
    logger.info("removed %s from the image cache", reference)
    return 0


def run_cache_clear() -> int:
    """Remove every image cache entry.

    Returns:
        0 on success, 1 if the cache could not be written.
    """
    count = len(cache.entries())
    error = cache.clear()
    if error is not None:
        logger.error(error.reason)
        return 1
    noun = "entry" if count == 1 else "entries"
    logger.info("cleared the image cache (%d %s)", count, noun)
    return 0
