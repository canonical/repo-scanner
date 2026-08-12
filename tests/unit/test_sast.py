# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the SAST scan (repo_scanner.scans.sast)."""

import json

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.model import ArtifactKind, ToolResult
from repo_scanner.scans.sast import SastScan


def test_invocations_run_semgrep_producing_sarif() -> None:
    inv = SastScan().invocations("/scan/acme")[0]
    assert inv.tool == "semgrep"
    assert "--sarif" in inv.args
    assert inv.args[-1] == "/scan/acme"  # the target is the last argument


def test_consolidate_merges_semgrep_sarif() -> None:
    # consolidate parses and merges each result's SARIF; the semgrep finding survives
    # into the merged artifact (merge behavior itself is covered in test_workflow).
    document = {
        "version": "2.1.0",
        "runs": [{"results": [{"ruleId": "x", "level": "error"}]}],
    }
    result = SastScan().consolidate(
        [ToolResult("semgrep", ExecResult(0, json.dumps(document), ""))]
    )
    assert not isinstance(result, Failure)
    assert result.kind is ArtifactKind.SARIF
    findings = result.results()
    assert len(findings) == 1
    assert findings[0]["ruleId"] == "x" and findings[0]["level"] == "error"


def test_consolidate_rejects_non_sarif_output() -> None:
    result = SastScan().consolidate(
        [ToolResult("semgrep", ExecResult(0, "not sarif output", ""))]
    )
    assert isinstance(result, Failure)
