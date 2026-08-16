# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan image` group: build the tool image and manage the cache."""

import logging

from repo_scanner.actions.image import (
    build_image,
    clear_cache,
    list_cache,
    remove_cache_entry,
)
from repo_scanner.backends import select_backend
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import Group, flag, positional
from repo_scanner.execution.process import Failure

logger = logging.getLogger(__name__)


class ImageBuild(Command):
    name = "build"
    help = "Build the tool image on demand for the selected backend; reused if built."

    force: bool = flag(help="Rebuild even if an image for this spec exists.")

    def run(self) -> int:
        backend = select_backend(self.backend)
        if isinstance(backend, Failure):
            logger.error(backend.reason)
            return 2
        builder = backend.image_builder()
        if builder is None:
            logger.error("the %s backend cannot build images", backend.name)
            return 2
        return build_image(builder, force=self.force)


class CacheList(Command):
    name = "list"
    help = "List the recorded image cache entries."

    def run(self) -> int:
        return list_cache()


class CacheRemove(Command):
    name = "remove"
    help = "Remove one entry by its image reference."

    reference: str = positional(help="The image reference to forget.")

    def run(self) -> int:
        return remove_cache_entry(self.reference)


class CacheClear(Command):
    name = "clear"
    help = "Remove all image cache entries."

    def run(self) -> int:
        return clear_cache()


class CacheGroup(Group):
    name = "cache"
    help = "View or manage reposcan's record of built and pulled images."
    subcommands = (CacheList, CacheRemove, CacheClear)


class ImageGroup(Group):
    name = "image"
    help = "Build the tool image and manage the image cache."
    subcommands = (ImageBuild, CacheGroup)
