"""The image build spec: the single build script that installs every tool, plus the
content-addressed identity used to name and reuse the built image.

The same script installs the tools whichever way an image is built -- baked into a
Docker image with a RUN, or provisioned into an LXD image by pushing and exec'ing it
-- so there is one definition of what an image contains. It is the same per-tool
`install_commands` that `bootstrap` runs on the host, aggregated. See image/docker.py
and image/lxd.py.
"""

import hashlib
from dataclasses import dataclass

from repo_scanner.tools.install import install_plan
from repo_scanner.tools.model import Platform
from repo_scanner.tools.registry import TOOLS

# The image name that built images are tagged/aliased under (with the spec digest).
NAME = "reposcan"

# The base image and in-image install location. Both feed the spec digest, so a
# change to either yields a new image identity.
BASE_IMAGE = "ubuntu:24.04"
INSTALL_ROOT = "/opt/reposcan"

# Packages needed by the install commands that may not be in the base image
_BASE_PACKAGES = ("curl", "ca-certificates")


def build_script(platform: Platform, install_root: str = INSTALL_ROOT) -> str:
    """The shell script that installs every tool into `install_root`, for `platform`.
    It runs under `set -eu`, so any failure aborts the build: a half-built image is
    worse than none. Each tool's own install commands are reused verbatim."""
    lines = [
        "#!/bin/sh",
        "set -eu",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update",
        f"apt-get install -y --no-install-recommends {' '.join(_BASE_PACKAGES)}",
        "rm -rf /var/lib/apt/lists/*",
    ]
    for step in install_plan(TOOLS.values(), platform, install_root):
        lines.append(f"# {step.tool.name} {step.tool.version}")
        lines.extend(step.commands)
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BuildSpec:
    """A build script plus the inputs that define the built image's identity. The
    `digest` content-addresses the image: an unchanged spec reuses the built image,
    and any change (a tool version or hash, the base image, the install root) produces
    a new digest and so a new image."""

    base_image: str
    install_root: str
    script: str

    @property
    def digest(self) -> str:
        material = "\n".join([self.base_image, self.install_root, self.script])
        return hashlib.sha256(material.encode()).hexdigest()

    @property
    def short_digest(self) -> str:
        return self.digest[:12]


def build_spec(
    platform: Platform,
    base_image: str = BASE_IMAGE,
    install_root: str = INSTALL_ROOT,
) -> BuildSpec:
    """The build spec for an image containing every tool, built for `platform`."""
    return BuildSpec(base_image, install_root, build_script(platform, install_root))
