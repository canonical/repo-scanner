# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan image` subcommand: build the tool image and manage the cache."""

import logging

from repo_scanner.backends import select_backend
from repo_scanner.cli.nodes import Command, CommandGroup
from repo_scanner.cli.options import Option, Values
from repo_scanner.commands import image_cmd
from repo_scanner.execution.process import Failure

logger = logging.getLogger(__name__)


class ImageBuildCommand(Command):
    name = "build"
    help = (
        "Build the tool image on demand for the selected backend (docker or "
        "lxd); reused if already built."
    )
    options = (
        Option(
            ("--force",),
            "force",
            store_true=True,
            help="Rebuild even if an image for this spec already exists.",
        ),
    )

    def run(self, values: Values) -> int:
        """Build the tool image. Needs a container backend (local cannot build)."""
        backend = select_backend(values["backend"])
        if isinstance(backend, Failure):
            logger.error(backend.reason)
            return 2
        builder = backend.image_builder()
        if builder is None:
            logger.error("the %s backend cannot build images", backend.name)
            return 2
        return image_cmd.run_image_build(builder, force=values["force"])


class CacheListCommand(Command):
    name = "list"
    help = "List the recorded image cache entries."
    options = ()

    def run(self, values: Values) -> int:
        return image_cmd.run_cache_list()


class CacheRemoveCommand(Command):
    name = "remove"
    help = "Remove one entry by its image reference."
    options = (Option(("reference",), "reference", positional=True),)

    def run(self, values: Values) -> int:
        return image_cmd.run_cache_remove(values["reference"])


class CacheClearCommand(Command):
    name = "clear"
    help = "Remove all image cache entries."
    options = ()

    def run(self, values: Values) -> int:
        return image_cmd.run_cache_clear()


class CacheGroup(CommandGroup):
    name = "cache"
    help = "View or manage reposcan's record of built and pulled images."
    options = ()
    subcommands = {
        "list": CacheListCommand,
        "remove": CacheRemoveCommand,
        "clear": CacheClearCommand,
    }


class ImageGroup(CommandGroup):
    name = "image"
    help = "Build the tool image and manage the image cache."
    options = ()
    subcommands = {
        "build": ImageBuildCommand,
        "cache": CacheGroup,
    }
