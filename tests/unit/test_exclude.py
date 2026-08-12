# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for git-ignored-path exclusion (repo_scanner.scans.exclude)."""

from collections.abc import Mapping, Sequence

from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.scans.exclude import IgnoredPaths


class _FakeContext:
    name = "fake"

    def __init__(self, result: ExecResult | Failure) -> None:
        self._result = result
        self.commands: list[list[str]] = []

    def start(self) -> Failure | None:
        return None

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        uid: int | None = None,
        timeout: float | None = None,
        stream_stdout: bool = False,
        stream_stderr: bool = False,
    ) -> ExecResult | Failure:
        self.commands.append(list(command))
        return self._result

    def stop(self) -> None:
        return None


def test_from_context_splits_git_output_into_dirs_and_files() -> None:
    # git ls-files -z emits NUL-terminated entries; a wholly-ignored dir ends in "/".
    ctx = _FakeContext(ExecResult(0, ".venv/\0src/.cache/\0secret.env\0", ""))
    ignored = IgnoredPaths.from_context(ctx, "/scan/acme")
    assert ignored.dirs == (".venv", "src/.cache")
    assert ignored.files == ("secret.env",)
    assert ctx.commands[0][:2] == ["git", "ls-files"]  # read-only lookup, cwd is target


def test_from_context_is_empty_when_git_fails() -> None:
    # Not a git repo / git missing -> no exclusions, scan proceeds unfiltered.
    for result in (Failure(reason="no git"), ExecResult(128, "", "fatal")):
        assert IgnoredPaths.from_context(_FakeContext(result), "/x") == IgnoredPaths()
