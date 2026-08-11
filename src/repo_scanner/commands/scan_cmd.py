# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan scan` command: run a scan and emit its artifact.

Runs the scan in the started context, writes the SARIF report (to a file or
stdout), and maps the outcome to an exit code: 0 when the scan ran and found
nothing, 3 when it found something, 1 on a scan or tool error.
"""

import json
import logging
import sys
from pathlib import Path

from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.scans.model import ArtifactKind, Scan, run_scan

logger = logging.getLogger(__name__)

# Exit code when a scan completes and reports one or more findings.
FINDINGS_EXIT_CODE = 3


def run_scan_command(
    scan: Scan,
    ctx: ExecutionContext,
    target: str,
    tool_root: str,
    *,
    output: str | None,
) -> int:
    """Run `scan` against `target`, emit the artifact, and return an exit code.

    Args:
        scan: The scan to run.
        ctx: The started context the scan's tools run in.
        target: The repository path as seen in the context.
        tool_root: Where the tools are installed in the context.
        output: A file to write the report to, or None for stdout.

    Returns:
        For a findings scan (SARIF): 0 when it found nothing, 3 when it found
        something. For an inventory scan (SBOM/CycloneDX): 0. 2 when `output`
        already exists (it is not overwritten). 1 on a scan or tool error, or if
        the report could not be written.
    """
    # Refuse to clobber an existing report, and check before the (slow) scan runs.
    if output is not None and Path(output).exists():
        logger.error("output file already exists, refusing to overwrite: %s", output)
        return 2

    artifact = run_scan(scan, ctx, target, tool_root)
    if isinstance(artifact, Failure):
        logger.error(artifact.reason)
        return 1

    report = json.dumps(artifact.to_dict(), indent=2) + "\n"
    if output is not None:
        try:
            Path(output).write_text(report)
        except OSError as exc:
            logger.error("could not write %s: %s", output, exc)
            return 1
    else:
        # The report is the command's output; diagnostics go to the log (stderr).
        sys.stdout.write(report)

    if artifact.kind is ArtifactKind.CYCLONEDX:
        # An SBOM is an inventory, not pass/fail: report the size, always exit 0.
        logger.info("%s scan complete: %d component(s)", scan.name, artifact.count())
        return 0
    count = artifact.count()
    logger.info("%s scan complete: %d finding(s)", scan.name, count)
    return FINDINGS_EXIT_CODE if count else 0
