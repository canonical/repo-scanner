# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the local execution context (repo_scanner.execution.local)."""

import sys

from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.process import ExecResult


def test_run_executes_on_the_host_with_env_overlaid() -> None:
    result = LocalContext().run(
        [sys.executable, "-c", "import os; print(os.environ['REPOSCAN_TEST_VAR'])"],
        env={"REPOSCAN_TEST_VAR": "overlaid"},
    )
    assert isinstance(result, ExecResult)
    assert result.stdout.strip() == "overlaid"
