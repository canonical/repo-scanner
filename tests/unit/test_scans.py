# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the scan model and run_scan driver (repo_scanner.scans.model)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans import sarif
from repo_scanner.scans.model import (
    NO_PARAMETERS,
    Artifact,
    ArtifactKind,
    Parameter,
    ToolInvocation,
    ToolResult,
    run_scan,
)


class _FakeContext:
    name = "fake"

    def __init__(self, result: ExecResult | Failure) -> None:
        self._result = result
        self.commands: list[list[str]] = []
        self.streamed: list[tuple[bool, bool]] = []

    def start(self) -> Failure | None:
        return None

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stream_stdout: bool = False,
        stream_stderr: bool = False,
    ) -> ExecResult | Failure:
        self.commands.append(list(command))
        self.streamed.append((stream_stdout, stream_stderr))
        return self._result

    def stop(self) -> None:
        return None


@dataclass(frozen=True)
class _FakeScan:
    # Invokes one real registered tool so installed-path lookup resolves.
    name: ClassVar[str] = "faux"
    summary: ClassVar[str] = "A fake scan for testing the driver."
    parameters: ClassVar[tuple[Parameter, ...]] = NO_PARAMETERS

    def invocations(self, target: str) -> list[ToolInvocation]:
        return [ToolInvocation("trufflehog", ["--version"])]

    def consolidate(self, results: list[ToolResult]) -> Artifact | Failure:
        return sarif.SarifDocument({"runs": [{"results": []}]})


def test_run_scan_runs_each_tool_at_its_installed_path_and_consolidates() -> None:
    ctx = _FakeContext(ExecResult(0, "", ""))
    artifact = run_scan(_FakeScan(), ctx, "/scan/acme", "/opt/reposcan")
    assert not isinstance(artifact, Failure)
    assert artifact.kind is ArtifactKind.SARIF
    assert ctx.commands[0][0] == "/opt/reposcan/bin/trufflehog"


def test_run_scan_reports_a_nonzero_tool_exit_as_a_failure() -> None:
    ctx = _FakeContext(ExecResult(2, "", "trufflehog: bad target"))
    result = run_scan(_FakeScan(), ctx, "/scan/acme", "/opt/reposcan")
    assert isinstance(result, Failure)
    assert "trufflehog failed" in result.reason


def test_run_scan_streams_tool_progress_but_not_its_stdout() -> None:
    ctx = _FakeContext(ExecResult(0, "", ""))
    run_scan(_FakeScan(), ctx, "/scan/acme", "/opt/reposcan", stream=True)
    # (stream_stdout, stream_stderr): the tool's stderr (progress) streams, its
    # stdout (results) is captured but not echoed.
    assert ctx.streamed == [(False, True)]
