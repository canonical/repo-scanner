"""Tests for the subprocess runner (repo_scanner.execution.process)."""

import sys

from repo_scanner.execution.context import ExecResult, Failure
from repo_scanner.execution.process import run_process


def test_captures_stdout_stderr_and_exit_code() -> None:
    result = run_process(
        [
            sys.executable,
            "-c",
            "import sys; print('o'); sys.stderr.write('e'); sys.exit(3)",
        ]
    )
    assert isinstance(result, ExecResult)
    assert result.stdout.strip() == "o"
    assert "e" in result.stderr
    assert result.exit_code == 3


def test_empty_command_is_a_failure() -> None:
    assert isinstance(run_process([]), Failure)


def test_missing_command_is_a_failure() -> None:
    result = run_process(["reposcan-no-such-binary-xyz"])
    assert isinstance(result, Failure)
    assert not result.timed_out


def test_timeout_is_a_failure() -> None:
    result = run_process(
        [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5
    )
    assert isinstance(result, Failure)
    assert result.timed_out
