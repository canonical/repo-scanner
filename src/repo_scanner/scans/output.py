# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Render and emit a scan's consolidated artifact.

Every scan result reposcan prints goes through here. On stdout the default is a
concise, human-readable table; to a file the default is the artifact's native JSON
document (SARIF or CycloneDX). `--format` overrides either default, and `--limit`
caps how many rows a table shows.
"""

import json
import logging
import shutil
import sys
import textwrap
from enum import Enum

from repo_scanner.execution.process import Failure
from repo_scanner.scans.model import Artifact

logger = logging.getLogger(__name__)

# Default maximum number of rows shown in a table.
DEFAULT_ROW_LIMIT = 20

# Cap on a single table cell's width; longer text is truncated (or wrapped).
_MAX_CELL_WIDTH = 60

# With --wrap, the most lines a single cell may span before it is truncated.
_MAX_WRAP_LINES = 6


class Format(str, Enum):
    """A way to render a scan artifact for output."""

    TABLE = "table"
    JSON = "json"


def emit(
    artifact: Artifact,
    *,
    output: str | None = None,
    fmt: Format | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
    wrap: bool = False,
) -> Failure | None:
    """Render `artifact` and write it to `output` (a file) or stdout.

    The format defaults to a table on stdout and the native JSON document in a
    file; `fmt` overrides that. `limit` caps the table's rows (ignored for JSON).

    Args:
        artifact: The consolidated scan result to render.
        output: A file to write to, or None for stdout.
        fmt: The chosen format, or None to use the destination's default.
        limit: The maximum number of rows to show in a table.
        wrap: When True, wrap long table cells across multiple lines (up to a cap)
            instead of truncating them.

    Returns:
        None on success, or a Failure if the output file already exists (it is not
        overwritten) or could not be written.
    """
    chosen = fmt or (Format.JSON if output is not None else Format.TABLE)
    if chosen is Format.JSON:
        text = json.dumps(artifact.to_dict(), indent=2) + "\n"
    else:
        text = _table(artifact, limit, wrap)
    if output is None:
        sys.stdout.write(text)
        return None
    try:
        # Exclusive create ("x"): refuse to overwrite an existing file atomically,
        # with no time-of-check/time-of-use gap between checking and writing.
        with open(output, "x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError:
        return Failure(
            reason=f"output file already exists, refusing to overwrite: {output}"
        )
    except OSError as exc:
        return Failure(reason=f"could not write {output}: {exc}")
    return None


def _table(artifact: Artifact, limit: int, wrap: bool) -> str:
    """A concise text table of the artifact's entries, capped at `limit` rows."""
    headers, rows = artifact.rows()
    shown = rows[:limit] if limit >= 0 else rows
    if len(shown) < len(rows):
        logger.info(
            "showing %d of %d results; use --limit or --format json for all",
            len(shown),
            len(rows),
        )
    widths = [len(header) for header in headers]
    for row in shown:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], min(len(cell), _MAX_CELL_WIDTH))
    _fit_to_terminal(widths)

    lines = _render_row(headers, widths, wrap=False)
    lines.append("  ".join("-" * width for width in widths))
    for row in shown:
        lines.extend(_render_row(row, widths, wrap))
    return "\n".join(lines) + "\n"


def _fit_to_terminal(widths: list[int]) -> None:
    """Shrink the widest columns in place until a row fits the terminal width.

    Columns are separated by two spaces, so a rendered line is `sum(widths)` plus
    two per gap. The widest column is trimmed one char at a time (never below one)
    until the total fits, so no line is ever wider than the terminal.
    """
    gaps = 2 * (len(widths) - 1)
    available = shutil.get_terminal_size(fallback=(80, 24)).columns - gaps
    while sum(widths) > available and any(width > 1 for width in widths):
        widest = max(range(len(widths)), key=lambda index: widths[index])
        widths[widest] -= 1


def _render_row(cells: list[str], widths: list[int], wrap: bool) -> list[str]:
    """The physical lines for one row: one line, or several when a cell wraps."""
    columns = [
        _cell_lines(cell, widths[index], wrap) for index, cell in enumerate(cells)
    ]
    height = max((len(column) for column in columns), default=1)
    lines = []
    for line in range(height):
        parts = [
            (column[line] if line < len(column) else "").ljust(widths[index])
            for index, column in enumerate(columns)
        ]
        lines.append("  ".join(parts).rstrip())
    return lines


def _cell_lines(cell: str, width: int, wrap: bool) -> list[str]:
    """A cell rendered as one clipped line, or several wrapped lines under `wrap`."""
    if not wrap:
        return [_clip(cell, width)]
    wrapped = textwrap.wrap(cell, width) or [""]
    if len(wrapped) > _MAX_WRAP_LINES:
        wrapped = wrapped[:_MAX_WRAP_LINES]
        wrapped[-1] = _clip(wrapped[-1] + " ...", width)
    return wrapped


def _clip(text: str, width: int) -> str:
    """`text` truncated to `width`, with an ellipsis if it was too long."""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."
