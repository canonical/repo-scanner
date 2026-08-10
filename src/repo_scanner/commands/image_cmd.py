# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan image build` command: build the tool image on demand.

The backend (and so the image builder) is chosen by main; this just runs the build.
"""

import logging
import sys

from repo_scanner.execution.process import Failure
from repo_scanner.image.build_spec import build_spec
from repo_scanner.image.builder import ImageBuilder, ensure_image
from repo_scanner.tools.install import current_platform

logger = logging.getLogger(__name__)


def run_image_build(builder: ImageBuilder, *, force: bool) -> int:
    """Build (or reuse) the tool image with `builder`. Returns 0 with the image
    reference printed, or 1 if the build failed. `force` rebuilds even when the image
    already exists."""
    spec = build_spec(current_platform())
    result = ensure_image(builder, spec, force=force)
    if isinstance(result, Failure):
        logger.error(result.reason)
        return 1
    sys.stdout.write(f"{result}\n")
    return 0
