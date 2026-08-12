# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The CI/workflow scan: audit CI/CD definitions with zizmor and poutine.

Both tools emit SARIF; their results are merged into one document, annotated with
which scanner reported each finding (see scans/sarif.py `merge`).
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
class WorkflowScan:
    """Audit a repository's CI/CD workflow definitions with zizmor and poutine."""

    name: ClassVar[str] = "workflow"
    summary: ClassVar[str] = "Audit CI/CD workflows with zizmor and poutine."
    parameters: ClassVar[tuple[Parameter, ...]] = NO_PARAMETERS

    def invocations(self, target: str) -> list[ToolInvocation]:
        """The zizmor and poutine invocations for `target`.

        Args:
            target: The repository path as seen in the execution context.

        Returns:
            One invocation per tool, each producing SARIF on stdout. ok_codes
            allows a findings exit (commonly 1) since findings are not an error.
        """
        return [
            ToolInvocation("zizmor", ["--format", "sarif", target], ok_codes=(0, 1)),
            ToolInvocation(
                "poutine",
                ["analyze_local", target, "--format", "sarif"],
                ok_codes=(0, 1),
            ),
        ]

    def consolidate(self, results: list[ToolResult]) -> sarif.SarifDocument | Failure:
        """Merge each tool's SARIF into one annotated, deduped document.

        Args:
            results: The zizmor and poutine invocation results.

        Returns:
            A merged SARIF artifact, or a Failure if any tool did not emit SARIF.
        """
        sources = []
        for result in results:
            document = sarif.parse(result.output.stdout)
            if document is None:
                return Failure(reason=f"{result.tool} did not produce SARIF output")
            sources.append((result.tool, document))
        return sarif.merge(sources)
