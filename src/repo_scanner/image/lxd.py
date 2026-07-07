"""Build an LXD image from a BuildSpec, via the lxc CLI.

LXD has no build file, so the image is produced by launching a build container from
the base, pushing the spec's install script in, running it, then publishing the
stopped container as an image aliased by the spec digest. See image/builder.py for
the shared ensure step.
"""

import os
import tempfile

from repo_scanner.execution.process import ExecResult, Failure, run_process
from repo_scanner.image.build_spec import NAME, BuildSpec


class LxdImageBuilder:
    """Builds LXD images (an ImageBuilder). Aliases them `reposcan-<digest>` -- an
    LXD alias cannot use a colon, which separates a remote from an image."""

    name = "lxd"

    def reference(self, spec: BuildSpec) -> str:
        return f"{NAME}-{spec.short_digest}"

    def identity(self, reference: str) -> str | None:
        # The image fingerprint (a sha256) is LXD's content hash of the image.
        result = run_process(["lxc", "image", "info", reference], timeout=30)
        if not (isinstance(result, ExecResult) and result.exit_code == 0):
            return None
        for line in result.stdout.splitlines():
            if line.strip().startswith("Fingerprint:"):
                return line.split(":", 1)[1].strip() or None
        return None

    def build(self, spec: BuildSpec) -> str | Failure:
        # A build container is always deleted afterwards, success or not.
        alias = self.reference(spec)
        handle = f"{NAME}-build-{os.getpid()}"
        launched = run_process(["lxc", "launch", spec.base_image, handle], check=True)
        if isinstance(launched, Failure):
            return launched
        error = self._provision(handle, spec, alias)
        run_process(["lxc", "delete", handle, "--force"])  # remove the builder
        return error if error is not None else alias

    def _provision(self, handle: str, spec: BuildSpec, alias: str) -> Failure | None:
        """Wait for the build container's network, install the tools into it, then
        stop and publish it under `alias`. Returns None or the first Failure."""
        with tempfile.NamedTemporaryFile("w", suffix=".sh") as script:
            script.write(spec.script)
            script.flush()
            steps = [
                ["lxc", "exec", handle, "--", "cloud-init", "status", "--wait"],
                ["lxc", "file", "push", script.name, f"{handle}/root/install.sh"],
                ["lxc", "exec", handle, "--", "sh", "/root/install.sh"],
                ["lxc", "stop", handle],
                ["lxc", "publish", handle, "--alias", alias],
            ]
            for argv in steps:
                result = run_process(argv, check=True)
                if isinstance(result, Failure):
                    return result
        return None
