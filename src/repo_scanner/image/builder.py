"""The ImageBuilder Protocol and the backend-agnostic ensure step.

An ImageBuilder turns a BuildSpec into a built image for one backend (Docker or LXD).
The backends differ only in how they name, check for, and build an image; the
"reuse it unless missing or forced" logic is the same for both and lives here, in
`ensure_image`, so each builder implements just the three varying operations.
"""

import logging
from typing import Protocol

from repo_scanner.execution.process import Failure
from repo_scanner.image.build_spec import BuildSpec

logger = logging.getLogger(__name__)


class ImageBuilder(Protocol):
    """Builds images for one backend. `name` labels it ("docker" | "lxd")."""

    name: str

    def reference(self, spec: BuildSpec) -> str:
        """The content-addressed image reference (tag or alias) `spec` builds to."""
        ...

    def exists(self, reference: str) -> bool:
        """Whether an image with `reference` is already present locally."""
        ...

    def build(self, spec: BuildSpec) -> str | Failure:
        """Build the image unconditionally, returning its reference or a Failure."""
        ...


def ensure_image(
    builder: ImageBuilder, spec: BuildSpec, *, force: bool = False
) -> str | Failure:
    """The reference of an image built from `spec`, building it only if it is not
    already present -- or always, when `force` is set. On-demand: an unchanged spec is
    a no-op unless forced."""
    reference = builder.reference(spec)
    if not force and builder.exists(reference):
        logger.info("%s image %s already built", builder.name, reference)
        return reference
    logger.info("building %s image %s ...", builder.name, reference)
    return builder.build(spec)
