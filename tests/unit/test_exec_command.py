# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the `reposcan exec` command (repo_scanner.commands.exec_cmd)."""

import io
import sys
from contextlib import redirect_stdout

from repo_scanner.commands.exec_cmd import TIMEOUT_EXIT_CODE, run_exec
from repo_scanner.execution.local import LocalContext


def test_forwards_output_and_the_commands_own_exit_code() -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = run_exec(
            LocalContext(),
            [sys.executable, "-c", "print('X'); raise SystemExit(7)"],
            timeout=None,
        )
    assert code == 7
    assert "X" in out.getvalue()


def test_maps_the_failure_modes_to_exit_codes() -> None:
    local = LocalContext()
    assert run_exec(local, [], timeout=None) == 2  # no command given
    assert run_exec(local, ["reposcan-no-such-binary-xyz"], timeout=None) == 1  # start
    slept = [sys.executable, "-c", "import time; time.sleep(5)"]
    assert run_exec(local, slept, timeout=0.5) == TIMEOUT_EXIT_CODE  # timed out
