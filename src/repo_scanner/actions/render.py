# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan render` action: convert a saved report between formats.

Reads a report -- SARIF/CycloneDX JSON, or a reposcan sqlite database -- and renders
it as a table, as JSON, or as a sqlite database.
"""

import logging

from repo_scanner.execution.process import Failure
from repo_scanner.scans import cyclonedx, output, sarif, sqlitedb
from repo_scanner.scans.model import Artifact

logger = logging.getLogger(__name__)


def render(
    input_path: str,
    *,
    fmt: str | None = None,
    output_path: str | None = None,
    limit: int = output.DEFAULT_ROW_LIMIT,
    wrap: bool = False,
) -> int:
    """Render the report at `input_path` in the chosen format.

    Args:
        input_path: A saved report: SARIF/CycloneDX JSON or a sqlite database.
        fmt: "table", "json", or "sqlite"; None renders the default table.
        output_path: A file to write to, or None for stdout. Required for "sqlite".
        limit: The maximum number of rows to show in a table.
        wrap: When True, wrap long table cells across multiple lines.

    Returns:
        0 on success; 2 on a bad input or an unrecognized report; 1 if it could not be
        written (including a missing or existing sqlite output file).
    """
    artifact = _load(input_path)
    if artifact is None:
        return 2
    failure = output.emit(
        artifact,
        output=output_path,
        fmt=output.Format(fmt) if fmt else None,
        limit=limit,
        wrap=wrap,
    )
    if isinstance(failure, Failure):
        logger.error(failure.reason)
        return 1
    return 0


def _load(input_path: str) -> Artifact | None:
    """The artifact at `input_path` (sqlite or JSON), or None (logging why)."""
    try:
        with open(input_path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        logger.error("could not read %s: %s", input_path, exc)
        return None
    if sqlitedb.is_sqlite(data):
        artifact = sqlitedb.read(input_path)
    else:
        text = data.decode("utf-8", "replace")
        artifact = sarif.parse(text) or cyclonedx.parse(text)
    if artifact is None:
        logger.error("%s is not a SARIF, CycloneDX, or sqlite report", input_path)
    return artifact
