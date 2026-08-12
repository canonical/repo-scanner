# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the IaC scan (repo_scanner.scans.iac)."""

import json

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.iac import IacScan
from repo_scanner.scans.model import ArtifactKind, ToolResult


def test_consolidate_converts_checkov_failed_checks_to_sarif() -> None:
    report = {
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_DOCKER_3",
                    "check_name": "Ensure a user for the container has been created",
                    "file_path": "/Dockerfile",
                    "file_line_range": [1, 2],
                }
            ]
        }
    }
    result = IacScan().consolidate(
        [ToolResult("checkov", ExecResult(0, json.dumps(report), ""))]
    )
    assert not isinstance(result, Failure)
    assert result.kind is ArtifactKind.SARIF
    finding = result.results()[0]
    assert finding["ruleId"] == "CKV_DOCKER_3"
    location = finding["locations"][0]["physicalLocation"]["artifactLocation"]
    assert location["uri"] == "Dockerfile"  # the leading slash is stripped


def test_consolidate_rejects_non_json_output() -> None:
    result = IacScan().consolidate([ToolResult("checkov", ExecResult(0, "boom", ""))])
    assert isinstance(result, Failure)
