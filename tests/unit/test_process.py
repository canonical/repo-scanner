"""Tests for the subprocess runner (repo_scanner.execution.process)."""

import sys

from repo_scanner.execution.process import ExecResult, Failure, run_process


def test_captures_stdout_stderr_and_exit_code() -> None:
    result = run_process(
        [sys.executable, "-c", "import sys; print('o'); sys.stderr.write('e'); exit(3)"]
    )
    assert isinstance(result, ExecResult)
    assert result.stdout.strip() == "o"
    assert "e" in result.stderr
    assert result.exit_code == 3


def test_check_turns_a_nonzero_exit_into_a_failure() -> None:
    ok = run_process([sys.executable, "-c", ""], check=True)
    assert isinstance(ok, ExecResult) and ok.exit_code == 0
    bad = run_process([sys.executable, "-c", "raise SystemExit(3)"], check=True)
    assert isinstance(bad, Failure)


def test_the_ways_a_run_can_fail_become_failures() -> None:
    assert isinstance(run_process([]), Failure)  # no command
    missing = run_process(["reposcan-no-such-binary-xyz"])
    assert isinstance(missing, Failure) and not missing.timed_out
    sleep = [sys.executable, "-c", "import time; time.sleep(5)"]
    slow = run_process(sleep, timeout=0.5)
    assert isinstance(slow, Failure) and slow.timed_out
