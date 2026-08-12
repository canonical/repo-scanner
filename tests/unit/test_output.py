# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for scan-result output rendering (repo_scanner.scans.output)."""

import io
import json
import os
import shutil
import tempfile
from contextlib import redirect_stdout

from repo_scanner.execution.process import Failure
from repo_scanner.scans import cyclonedx, output, sarif
from repo_scanner.scans.output import Format, emit


def _sarif(*levels: str) -> sarif.SarifDocument:
    findings = [
        sarif.SarifResult(f"R{i}", f"message {i}", "app.py", i + 1, level=level)
        for i, level in enumerate(levels)
    ]
    return sarif.SarifDocument.from_results("tool", "1.0", findings)


def test_stdout_gets_a_sorted_table_a_file_gets_json_and_format_overrides() -> None:
    doc = _sarif("note", "error")  # deliberately out of severity order
    out = io.StringIO()
    with redirect_stdout(out):
        assert emit(doc) is None  # stdout default is a table
    text = out.getvalue()
    assert "LEVEL" in text and "app.py:1" in text  # its columns and finding data
    rows = [line.split()[0] for line in text.splitlines() if ".py:" in line]
    assert rows == ["error", "note"]  # sorted most-severe-first

    out = io.StringIO()
    with redirect_stdout(out):
        emit(doc, fmt=Format.JSON)  # --format overrides the stdout default
    assert json.loads(out.getvalue())["version"] == "2.1.0"

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "r.sarif")
        assert emit(doc, output=path) is None  # a file defaults to JSON
        with open(path) as handle:
            assert json.loads(handle.read())["version"] == "2.1.0"


def test_sbom_renders_a_component_table() -> None:
    doc = cyclonedx.CycloneDxDocument(
        {"components": [{"name": "flask", "version": "3.0.0", "type": "library"}]}
    )
    out = io.StringIO()
    with redirect_stdout(out):
        emit(doc)
    assert "COMPONENT" in out.getvalue() and "flask" in out.getvalue()


def test_limit_truncates_wrap_expands_and_neither_exceeds_the_terminal() -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        emit(_sarif(*["warning"] * 5), limit=2)
    assert len([line for line in out.getvalue().splitlines() if "app.py:" in line]) == 2

    long = " ".join(f"word{i}" for i in range(300))
    doc = sarif.SarifDocument.from_results(
        "tool", "1.0", [sarif.SarifResult("R", long, "a.py", 1)]
    )
    plain, wrapped = io.StringIO(), io.StringIO()
    with redirect_stdout(plain):
        emit(doc)
    with redirect_stdout(wrapped):
        emit(doc, wrap=True)
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    plain_rows, wrapped_rows = (
        plain.getvalue().splitlines(),
        wrapped.getvalue().splitlines(),
    )
    assert len(plain_rows[2:]) == 1  # default clips the message to one line
    assert 1 < len(wrapped_rows[2:]) <= output._MAX_WRAP_LINES  # --wrap spans, capped
    for line in plain_rows + wrapped_rows:
        assert len(line) <= columns  # no line is wider than the terminal


def test_emit_refuses_to_overwrite_an_existing_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "report.sarif")
        with open(path, "w") as handle:
            handle.write("existing")
        result = emit(_sarif("warning"), output=path)
        assert isinstance(result, Failure) and "already exists" in result.reason
        with open(path) as handle:
            assert handle.read() == "existing"  # left untouched
