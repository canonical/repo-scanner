# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the `reposcan render` action (repo_scanner.actions.render)."""

import io
import json
import os
import tempfile
from contextlib import redirect_stdout

from repo_scanner.actions.render import render
from repo_scanner.scans import sarif


def _write(directory: str, name: str, content: str) -> str:
    path = os.path.join(directory, name)
    with open(path, "w") as handle:
        handle.write(content)
    return path


def _sarif_doc() -> dict:
    return sarif.SarifDocument.from_results(
        "tool", "1.0", [sarif.SarifResult("X", "boom", "a.py", 3, level="error")]
    ).to_dict()


def test_renders_json_input_as_a_table() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = _write(directory, "r.sarif", json.dumps(_sarif_doc()))
        out = io.StringIO()
        with redirect_stdout(out):
            assert render(path) == 0
    text = out.getvalue()
    assert "LEVEL" in text and "X" in text and "a.py:3" in text


def test_round_trips_json_through_sqlite() -> None:
    doc = _sarif_doc()
    with tempfile.TemporaryDirectory() as directory:
        src = _write(directory, "r.sarif", json.dumps(doc))
        db = os.path.join(directory, "r.db")
        assert render(src, fmt="sqlite", output_path=db) == 0

        table = io.StringIO()
        with redirect_stdout(table):
            assert render(db, fmt="table") == 0  # sqlite input -> table
        assert "a.py:3" in table.getvalue()

        rendered = io.StringIO()
        with redirect_stdout(rendered):
            assert render(db, fmt="json") == 0  # sqlite input -> json
        assert json.loads(rendered.getvalue()) == doc  # faithful round-trip


def test_sqlite_output_requires_an_output_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        src = _write(directory, "r.sarif", json.dumps(_sarif_doc()))
        assert render(src, fmt="sqlite") == 1  # emit fails: no -o FILE


def test_missing_or_unrecognized_input_is_a_usage_error() -> None:
    assert render("/no/such/file.json") == 2
    with tempfile.TemporaryDirectory() as directory:
        path = _write(directory, "junk.txt", "not a report")
        assert render(path) == 2
