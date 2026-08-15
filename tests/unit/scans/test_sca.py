# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the SCA scan (repo_scanner.scans.sca), including govulncheck parsing."""

import json

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.model import ToolResult
from repo_scanner.scans.sca import ScaScan


def test_govulncheck_stream_becomes_sarif() -> None:
    stream = "\n".join(
        [
            json.dumps({"osv": {"id": "GO-2024-1", "summary": "bad thing"}}),
            json.dumps(
                {
                    "finding": {
                        "osv": "GO-2024-1",
                        "trace": [{"position": {"filename": "main.go", "line": 12}}],
                    }
                }
            ),
            json.dumps(
                {"finding": {"osv": "GO-2024-2", "trace": [{}]}}  # no position: skipped
            ),
            json.dumps({"progress": {"message": "scanning"}}),
        ]
    )
    result = ScaScan().consolidate(
        [ToolResult("govulncheck", ExecResult(3, stream, ""))]
    )
    assert not isinstance(result, Failure)
    assert result.count() == 1  # only the source-reaching finding
    finding = result.results()[0]
    assert finding["ruleId"] == "GO-2024-1"
    assert finding["message"]["text"] == "bad thing"  # the OSV summary
    assert finding["properties"]["scanners"] == ["govulncheck"]


def test_consolidate_merges_sarif_tools_with_converted_govulncheck() -> None:
    location = {"artifactLocation": {"uri": "pkg"}, "region": {"startLine": 1}}
    trivy = json.dumps(
        {
            "version": "2.1.0",
            "runs": [
                {
                    "results": [
                        {
                            "ruleId": "CVE-1",
                            "locations": [{"physicalLocation": location}],
                        }
                    ]
                }
            ],
        }
    )
    govulncheck = json.dumps(
        {
            "finding": {
                "osv": "GO-1",
                "trace": [{"position": {"filename": "main.go", "line": 2}}],
            }
        }
    )
    result = ScaScan().consolidate(
        [
            ToolResult("trivy", ExecResult(0, trivy, "")),
            ToolResult("govulncheck", ExecResult(3, govulncheck, "")),
        ]
    )
    assert not isinstance(result, Failure)
    rules = {r["ruleId"] for r in result.results()}
    assert rules == {"CVE-1", "GO-1"}


def test_consolidate_fails_when_a_sarif_tool_output_is_unusable() -> None:
    result = ScaScan().consolidate(
        [ToolResult("grype", ExecResult(0, "not sarif", ""))]
    )
    assert isinstance(result, Failure)
