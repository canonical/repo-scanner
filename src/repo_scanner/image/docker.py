"""Build a Docker image from a BuildSpec, via the docker CLI.

The image is a stock base plus the spec's install script run once at build time,
tagged by the spec digest. See image/builder.py for the shared ensure step.
"""

import tempfile
from pathlib import Path

from repo_scanner.execution.process import ExecResult, Failure, run_process
from repo_scanner.image.build_spec import NAME, BuildSpec


class DockerImageBuilder:
    """Builds Docker images (an ImageBuilder). Tags them `reposcan:<digest>`."""

    name = "docker"

    def reference(self, spec: BuildSpec) -> str:
        return f"{NAME}:{spec.short_digest}"

    def exists(self, reference: str) -> bool:
        result = run_process(["docker", "image", "inspect", reference], timeout=30)
        return isinstance(result, ExecResult) and result.exit_code == 0

    def build(self, spec: BuildSpec) -> str | Failure:
        # Build context: a temp dir with the install script and a Dockerfile that
        # runs it, then puts the tools' bin dir on PATH.
        tag = self.reference(spec)
        dockerfile = (
            f"FROM {spec.base_image}\n"
            "COPY install.sh /tmp/install.sh\n"
            "RUN sh /tmp/install.sh && rm -f /tmp/install.sh\n"
            f'ENV PATH="{spec.install_root}/bin:$PATH"\n'
        )
        with tempfile.TemporaryDirectory() as context:
            Path(context, "install.sh").write_text(spec.script)
            Path(context, "Dockerfile").write_text(dockerfile)
            result = run_process(["docker", "build", "-t", tag, context], check=True)
        return result if isinstance(result, Failure) else tag
