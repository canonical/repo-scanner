# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the CI/workflow scan (repo_scanner.scans.workflow)."""

import json

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.model import ToolResult
from repo_scanner.scans.workflow import WorkflowScan


def _result(rule: str, uri: str, line: int) -> dict:
    location = {"artifactLocation": {"uri": uri}, "region": {"startLine": line}}
    return {"ruleId": rule, "locations": [{"physicalLocation": location}]}


def _sarif(results: list[dict]) -> str:
    return json.dumps({"version": "2.1.0", "runs": [{"results": results}]})


def test_consolidate_merges_dedups_and_annotates_scanners() -> None:
    shared = _result("SHARED", "workflow.yml", 3)
    zizmor = _sarif([shared, _result("ZIZ", "workflow.yml", 5)])
    poutine = _sarif([shared, _result("POU", "workflow.yml", 7)])

    result = WorkflowScan().consolidate(
        [
            ToolResult("zizmor", ExecResult(0, zizmor, "")),
            ToolResult("poutine", ExecResult(0, poutine, "")),
        ]
    )
    assert not isinstance(result, Failure)
    assert result.count() == 3  # the shared finding is deduped
    by_rule = {r["ruleId"]: r for r in result.results()}
    assert by_rule["SHARED"]["properties"]["scanners"] == ["zizmor", "poutine"]
    assert by_rule["ZIZ"]["properties"]["scanners"] == ["zizmor"]
    assert by_rule["POU"]["properties"]["scanners"] == ["poutine"]


def test_consolidate_fails_when_a_tool_output_is_not_sarif() -> None:
    result = WorkflowScan().consolidate(
        [ToolResult("zizmor", ExecResult(0, "not sarif", ""))]
    )
    assert isinstance(result, Failure)
