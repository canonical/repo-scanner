# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Render a concise, terminal-fit text table from headers and rows.

A generic utility with no domain knowledge: it takes column headers and string rows
and produces aligned columns under a dashed header, shrunk to fit the terminal.
"""

import shutil
import textwrap

# Cap on a single table cell's width; longer text is truncated (or wrapped).
_MAX_CELL_WIDTH = 60

# With `wrap`, the most lines a single cell may span before it is truncated.
_MAX_WRAP_LINES = 6


def render_table(
    headers: list[str], rows: list[list[str]], *, wrap: bool = False
) -> str:
    """A concise text table: aligned columns under a dashed header, fit to the terminal.

    Cells are clipped to fit the terminal width unless `wrap` is set, in which case a
    long cell spans several lines (up to a cap) instead of being truncated.
    """
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], min(len(cell), _MAX_CELL_WIDTH))
    _fit_to_terminal(widths)

    lines = _render_row(headers, widths, wrap=False)
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
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
