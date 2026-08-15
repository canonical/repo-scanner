# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SBOM scan: build a software bill of materials with trivy, syft, and cdxgen.

Each tool emits CycloneDX; the components are merged into one deduped SBOM,
annotated with which scanners reported each (see scans/cyclonedx.py `merge`).

cdxgen runs in a no-build, secure mode so it never executes the scanned repo's own
code (see the invocation), and writes its BOM to a file that run_scan reads back --
cdxgen interleaves progress logs on stdout, so stdout is not a reliable channel. It
stays optional: if it fails, trivy + syft still produce the SBOM.
"""

import logging
from dataclasses import dataclass
from typing import ClassVar

from repo_scanner.execution.process import Failure
from repo_scanner.scans import cyclonedx
from repo_scanner.scans.model import (
    NO_PARAMETERS,
    Parameter,
    ToolInvocation,
    ToolResult,
)

logger = logging.getLogger(__name__)

# Where cdxgen writes its BOM inside the (ephemeral) scan container; run_scan reads it.
_CDXGEN_OUTPUT = "/tmp/cdxgen-sbom.json"


@dataclass(frozen=True)
class SbomScan:
    """Build a software bill of materials for a repository's components."""

    name: ClassVar[str] = "sbom"
    summary: ClassVar[str] = "Software bill of materials (trivy, syft, cdxgen)."
    parameters: ClassVar[tuple[Parameter, ...]] = NO_PARAMETERS
    resolves_dependencies: ClassVar[bool] = True  # resolve transitive deps first

    def invocations(self, target: str) -> list[ToolInvocation]:
        """The trivy, syft, and cdxgen invocations for `target`.

        Args:
            target: The repository path as seen in the execution context.

        Returns:
            One invocation per tool. trivy and syft emit CycloneDX on stdout; cdxgen
            writes to a file (read back by run_scan) and runs in a no-build, secure
            mode. cdxgen is optional.
        """
        return [
            ToolInvocation("trivy", ["fs", "--format", "cyclonedx", target]),
            ToolInvocation(
                tool="syft",
                args=[
                    f"dir:{target}",
                    "-o",
                    "cyclonedx-json",
                    # Broaden beyond syft's default directory catalogers: costs some
                    # performance but can catch extra packages (e.g. a bare
                    # package.json, via an installed-only cataloger that is off on a
                    # directory scan by default). See
                    # docs/explanation/sbom-generation.md.
                    "--override-default-catalogers",
                    "all",
                ],
                env={
                    "SYFT_CHECK_FOR_APP_UPDATE": "false",
                    # Capture requirements.txt entries that carry a version constraint
                    # but no exact pin (e.g. "flask>=2.0"); syft drops them otherwise.
                    # Note: no SBOM tool reads pyproject.toml deps in our no-install
                    # mode -- see docs/explanation/sbom-generation.md.
                    "SYFT_PYTHON_GUESS_UNPINNED_REQUIREMENTS": "true",
                },
            ),
            ToolInvocation(
                "cdxgen",
                [
                    # Never build or install from the untrusted repo: --no-install-deps
                    # (and pre-build lifecycle) keep cdxgen to static manifest/lockfile
                    # parsing, so it does not execute the repo's setup.py/build backend.
                    "--no-install-deps",
                    "--lifecycle",
                    "pre-build",
                    "--no-banner",
                    "-o",
                    _CDXGEN_OUTPUT,
                    target,
                ],
                # CDXGEN_SECURE_MODE is defense-in-depth: if any code path still tried
                # to install, cdxgen would inject python -S and pip --only-binary.
                env={"CDXGEN_SECURE_MODE": "true"},
                output_file=_CDXGEN_OUTPUT,
                optional=True,
            ),
        ]

    def consolidate(
        self, results: list[ToolResult]
    ) -> cyclonedx.CycloneDxDocument | Failure:
        """Merge each tool's CycloneDX output into one deduped SBOM.

        Args:
            results: The results of the invocations that ran (cdxgen may be absent).

        Returns:
            A CycloneDX artifact, or a Failure if a tool produced no usable output.
        """
        sources = []
        tool_optional = {i.tool: i.optional for i in self.invocations("dummy-target")}
        for result in results:
            document = cyclonedx.parse(result.output.stdout)
            if document is None:
                if tool_optional[result.tool]:
                    logger.warning("%s did not produce CycloneDX output", result.tool)
                    continue
                return Failure(reason=f"{result.tool} did not produce CycloneDX output")
            sources.append((result.tool, document))
        return cyclonedx.merge(sources)
