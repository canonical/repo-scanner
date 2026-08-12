# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the `reposcan scan` command (repo_scanner.commands.scan_cmd).

run_scan is patched to a scripted artifact/Failure, so this covers the command's
own job: writing the report and choosing the exit code (0 clean / 3 findings / 1
error).
"""

import io
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from typing import cast

import repo_scanner.commands.scan_cmd as scan_cmd
from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.scans import cyclonedx, sarif
from repo_scanner.scans.model import Artifact
from repo_scanner.scans.output import Format
from repo_scanner.scans.secrets import SecretsScan


def _sarif_artifact(findings: int) -> Artifact:
    results = [sarif.SarifResult("AWS", "secret", "f.py", 1) for _ in range(findings)]
    return sarif.SarifDocument.from_results("trufflehog", "3.95.8", results)


def _sbom_artifact(components: int) -> Artifact:
    listed = [{"name": f"c{i}"} for i in range(components)]
    return cyclonedx.CycloneDxDocument({"bomFormat": "CycloneDX", "components": listed})


@contextmanager
def _patched_run_scan(outcome: Artifact | Failure) -> Iterator[None]:
    saved = scan_cmd.run_scan
    scan_cmd.run_scan = lambda *args, **kwargs: outcome
    try:
        yield
    finally:
        scan_cmd.run_scan = saved


def _run(
    outcome: Artifact | Failure,
    *,
    output: str | None = None,
    fmt: Format | None = None,
) -> tuple[int, str]:
    out = io.StringIO()
    # run_scan is patched, so the context is never touched; cast a placeholder.
    ctx = cast(ExecutionContext, None)
    with _patched_run_scan(outcome), redirect_stdout(out):
        code = scan_cmd.run_scan_command(
            SecretsScan(), ctx, "/scan/x", "/opt/reposcan", output_file=output, fmt=fmt
        )
    return code, out.getvalue()


def test_sbom_artifact_always_exits_zero() -> None:
    # An SBOM is an inventory, not pass/fail: even with components it exits 0.
    code, out = _run(_sbom_artifact(5))
    assert code == 0
    assert "COMPONENT" in out and "c0" in out  # the default stdout table


def test_exit_zero_when_no_findings_and_three_when_findings() -> None:
    code, out = _run(_sarif_artifact(0))
    assert code == 0
    assert "LEVEL" in out  # the default stdout table's header
    code, _ = _run(_sarif_artifact(2))
    assert code == 3  # findings


def test_format_json_overrides_the_stdout_table_default() -> None:
    code, out = _run(_sarif_artifact(1), fmt=Format.JSON)
    assert code == 3
    assert json.loads(out)["version"] == "2.1.0"  # native SARIF, not a table


def test_a_scan_failure_returns_one() -> None:
    code, _ = _run(Failure(reason="trufflehog failed"))
    assert code == 1


def test_output_file_receives_the_report_and_stdout_stays_clean() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "report.sarif")
        code, out = _run(_sarif_artifact(1), output=path)
        assert code == 3
        assert out == ""  # nothing on stdout when writing to a file
        with open(path, encoding="ascii") as handle:
            written = json.loads(handle.read())
        assert written["version"] == "2.1.0"


def test_refuses_to_overwrite_an_existing_output_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "report.sarif")
        with open(path, "w", encoding="ascii") as handle:
            handle.write("existing report")
        code, out = _run(_sarif_artifact(1), output=path)
        assert code == 2  # refused before running the scan
        assert out == ""
        with open(path, encoding="ascii") as handle:
            assert handle.read() == "existing report"  # untouched
