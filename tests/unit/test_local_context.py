"""Tests for the local execution context (repo_scanner.execution.local)."""

import sys

from repo_scanner.execution.context import ExecResult
from repo_scanner.execution.local import LocalContext


def test_is_always_available() -> None:
    assert LocalContext().availability().ok


def test_run_executes_on_the_host_with_env_overlaid() -> None:
    result = LocalContext().run(
        [sys.executable, "-c", "import os; print(os.environ['REPOSCAN_TEST_VAR'])"],
        env={"REPOSCAN_TEST_VAR": "overlaid"},
    )
    assert isinstance(result, ExecResult)
    assert result.stdout.strip() == "overlaid"
