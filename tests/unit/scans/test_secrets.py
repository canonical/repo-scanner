# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the secrets scan (repo_scanner.scans.secrets)."""

import json

from repo_scanner.execution.process import ExecResult
from repo_scanner.scans.model import ToolResult
from repo_scanner.scans.secrets import SecretsScan

# Two trufflehog findings (git and filesystem metadata) plus a non-JSON log line.
_TRUFFLEHOG_OUTPUT = (
    json.dumps(
        {
            "SourceMetadata": {"Data": {"Git": {"file": "src/config.py", "line": 10}}},
            "DetectorName": "AWS",
            "Verified": True,
            "Raw": "AKIAEXAMPLE",
        }
    )
    + "\n"
    + "not json, a progress line trufflehog printed\n"
    + json.dumps(
        {
            "SourceMetadata": {"Data": {"Filesystem": {"file": "/scan/x/.env"}}},
            "DetectorName": "GitHub",
            "Verified": False,
            "Raw": "ghp_example",
        }
    )
    + "\n"
)


def test_invocations_choose_git_or_filesystem_by_mode() -> None:
    history = SecretsScan(mode="history").invocations("/scan/acme")[0]
    assert history.tool == "trufflehog"
    assert history.args == ["git", "file:///scan/acme", "--json", "--no-update"]
    filesystem = SecretsScan(mode="filesystem").invocations("/scan/acme")[0]
    assert filesystem.args == ["filesystem", "/scan/acme", "--json", "--no-update"]


def test_history_depth_limits_the_commit_scan_and_filesystem_ignores_it() -> None:
    history = SecretsScan(mode="history", depth=50).invocations("/scan/acme")[0]
    assert history.args[-2:] == ["--max-depth", "50"]
    # depth is a history-only option; a filesystem scan does not carry it.
    filesystem = SecretsScan(mode="filesystem", depth=50).invocations("/scan/acme")[0]
    assert "--max-depth" not in filesystem.args


def test_consolidate_turns_trufflehog_findings_into_sarif() -> None:
    result = SecretsScan().consolidate(
        [ToolResult("trufflehog", ExecResult(0, _TRUFFLEHOG_OUTPUT, ""))]
    )
    assert result.count() == 2  # the log line was skipped

    aws, github = result.results()
    assert aws["ruleId"] == "AWS" and aws["level"] == "error"  # verified -> error
    assert aws["locations"][0]["physicalLocation"]["region"]["startLine"] == 10
    assert github["ruleId"] == "GitHub" and github["level"] == "warning"  # unverified


def test_consolidate_aggregates_findings_across_all_tool_results() -> None:
    def one_finding(detector: str) -> str:
        data = {"SourceMetadata": {"Data": {"Git": {"file": "x.py"}}}}
        return json.dumps({**data, "DetectorName": detector}) + "\n"

    results = [
        ToolResult("trufflehog", ExecResult(0, one_finding("AWS"), "")),
        ToolResult("trufflehog", ExecResult(0, one_finding("GitHub"), "")),
    ]
    artifact = SecretsScan().consolidate(results)
    assert artifact.count() == 2  # one from each result
