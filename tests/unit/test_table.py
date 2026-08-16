# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the generic table renderer (repo_scanner.table)."""

from repo_scanner.table import render_table


def test_columns_align_under_a_dashed_header() -> None:
    out = render_table(["key", "value"], [["backend", "docker"], ["uid", "4000"]])
    lines = out.splitlines()
    assert lines[0] == "key      value"  # header padded to the widest cell per column
    assert lines[1] == "-------  ------"  # a dashed separator sized to each column
    assert lines[2] == "backend  docker"
    assert lines[3] == "uid      4000"


def test_a_long_cell_is_clipped_with_an_ellipsis() -> None:
    long = "x" * 200
    row = render_table(["c"], [[long]]).splitlines()[2]
    assert row.endswith("...")
    assert len(row) < len(long)
