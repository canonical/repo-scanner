# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SAST scan: static application security testing with semgrep.

semgrep emits SARIF directly (`--sarif`), so this scan runs it over the target with
its default ruleset and passes the SARIF through as the artifact.
"""

from dataclasses import dataclass
from typing import ClassVar

from repo_scanner.execution.process import Failure
from repo_scanner.scans import sarif
from repo_scanner.scans.model import (
    NO_PARAMETERS,
    Parameter,
    ToolInvocation,
    ToolResult,
)


@dataclass(frozen=True)
class SastScan:
    """Scan a repository's source for security issues with semgrep."""

    name: ClassVar[str] = "sast"
    summary: ClassVar[str] = "Static analysis of source with semgrep."
    parameters: ClassVar[tuple[Parameter, ...]] = NO_PARAMETERS

    def invocations(self, target: str) -> list[ToolInvocation]:
        """The single semgrep invocation for `target`.

        Args:
            target: The repository path as seen in the execution context.

        Returns:
            One semgrep invocation producing SARIF on stdout.
        """
        # semgrep's curated default ruleset. `auto` would select rules per detected
        # language but requires metrics to be enabled, so it is not usable with
        # --metrics=off; p/default is the self-contained alternative. No --quiet, so
        # semgrep's scan progress streams live on stderr while the SARIF goes to
        # stdout. ok_codes allows a findings exit since findings are not an error.
        args = [
            "scan",
            "--sarif",
            "--metrics=off",
            "--disable-version-check",
            "--config",
            "p/default",
            target,
        ]
        return [ToolInvocation("semgrep", args, ok_codes=(0, 1))]

    def consolidate(self, results: list[ToolResult]) -> sarif.SarifDocument | Failure:
        """Merge each result's SARIF output into one annotated artifact.

        Args:
            results: The semgrep invocation results.

        Returns:
            A SARIF artifact, or a Failure if a result did not produce SARIF.
        """
        sources = []
        for result in results:
            document = sarif.parse(result.output.stdout)
            if document is None:
                return Failure(reason=f"{result.tool} did not produce SARIF output")
            sources.append((result.tool, document))
        return sarif.merge(sources)
