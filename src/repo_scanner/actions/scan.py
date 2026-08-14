# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan scan` action: run a scan and emit its artifact.

Runs the scan in the started context, emits the result through the output module,
and maps the outcome to an exit code: 0 when the scan ran and found nothing,
3 when it found something, 1 on a scan or tool error.
"""

import logging
from pathlib import Path

from repo_scanner.execution.context import SCAN_UID, ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.scans import output
from repo_scanner.scans.model import ArtifactKind, Scan, run_scan
from repo_scanner.scans.resolve import resolve_dependencies

logger = logging.getLogger(__name__)

# Exit code when a scan completes and reports one or more findings.
FINDINGS_EXIT_CODE = 3


def scan(
    scan: Scan,
    ctx: ExecutionContext,
    target: str,
    tool_root: str,
    *,
    output_file: str | None,
    fmt: output.Format | None = None,
    limit: int = output.DEFAULT_ROW_LIMIT,
    wrap: bool = False,
    uid: int = SCAN_UID,
    resolved_parent: str = "",
    allow_code_execution: bool = False,
) -> int:
    """Run `scan` against `target`, emit the artifact, and return an exit code.

    Args:
        scan: The scan to run.
        ctx: The started context the scan's tools run in.
        target: The repository path as seen in the context.
        tool_root: Where the tools are installed in the context.
        output_file: A file to write the report to, or None for stdout.
        fmt: The output format, or None for the default.
        limit: The maximum number of rows to show in a table.
        wrap: When True, wrap long table cells across multiple lines.
        uid: The user id each tool runs as (container backends only).
        resolved_parent: The backend's directory to copy the repo under for
            dependency resolution (SBOM/SCA scans).
        allow_code_execution: Passed to dependency resolution (SBOM/SCA scans): permit
            building source packages, which runs untrusted code.

    Returns:
        For a findings scan (SARIF): 0 when it found nothing, 3 when it found
        something. For an inventory scan (SBOM/CycloneDX): 0. 2 when `output_file`
        already exists (it is not overwritten). 1 on a scan or tool error, or if
        the report could not be written.
    """
    # Fail fast before the (slow) scan if the report file already exists. This is
    # only a courtesy check: emit refuses to overwrite atomically at write time, so
    # a file appearing during the scan is still caught (as a write Failure below).
    if output_file is not None and Path(output_file).exists():
        logger.error(
            "output file already exists, refusing to overwrite: %s", output_file
        )
        return 2

    if scan.resolves_dependencies:
        target = resolve_dependencies(
            ctx,
            target,
            tool_root,
            resolved_parent,
            uid=uid,
            allow_code_execution=allow_code_execution,
        )
    artifact = run_scan(scan, ctx, target, tool_root, stream=True, uid=uid)
    if isinstance(artifact, Failure):
        logger.error(artifact.reason)
        return 1

    failure = output.emit(artifact, output=output_file, fmt=fmt, limit=limit, wrap=wrap)
    if isinstance(failure, Failure):
        logger.error(failure.reason)
        return 1

    if artifact.kind is ArtifactKind.CYCLONEDX:
        # An SBOM is an inventory, not pass/fail: report the size, always exit 0.
        logger.info("%s scan complete: %d component(s)", scan.name, artifact.count())
        return 0
    count = artifact.count()
    logger.info("%s scan complete: %d finding(s)", scan.name, count)
    return FINDINGS_EXIT_CODE if count else 0
