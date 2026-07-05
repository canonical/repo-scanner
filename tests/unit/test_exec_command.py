"""Tests for the `reposcan exec` command (repo_scanner.commands.exec_)."""

import io
import logging
import sys
from contextlib import redirect_stdout

from repo_scanner.commands.exec_ import TIMEOUT_EXIT_CODE, run_exec
from repo_scanner.execution.local import LocalContext


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_forwards_stdout_and_returns_the_exit_code() -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = run_exec(
            LocalContext(),
            [sys.executable, "-c", "import sys; print('X'); sys.exit(7)"],
            timeout=None,
        )
    assert code == 7
    assert "X" in out.getvalue()


def test_empty_command_logs_an_error_and_returns_2() -> None:
    handler = _ListHandler()
    logger = logging.getLogger("repo_scanner")
    logger.addHandler(handler)
    try:
        code = run_exec(LocalContext(), [], timeout=None)
    finally:
        logger.removeHandler(handler)
    assert code == 2
    assert any("no command" in record.getMessage() for record in handler.records)


def test_failed_command_returns_1() -> None:
    code = run_exec(LocalContext(), ["reposcan-no-such-binary-xyz"], timeout=None)
    assert code == 1


def test_timeout_returns_the_timeout_code() -> None:
    code = run_exec(
        LocalContext(),
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout=0.5,
    )
    assert code == TIMEOUT_EXIT_CODE
