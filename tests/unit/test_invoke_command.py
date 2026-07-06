"""Tests for the `reposcan invoke` command (repo_scanner.commands.invoke_cmd)."""

import io
import os
import stat
import tempfile
from contextlib import redirect_stdout

from repo_scanner.commands.invoke_cmd import run_invoke
from repo_scanner.execution.local import LocalContext
from repo_scanner.tools.registry import TRUFFLEHOG


def _install_fake(root: str, tool, script: str) -> None:
    """Write an executable stand-in at the path the tool installs to."""
    path = tool.installed_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(script)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IRUSR)


def test_unknown_tool_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as root:
        code = run_invoke(LocalContext(), "not-a-tool", [], root, timeout=None)
    assert code == 2


def test_not_installed_tool_returns_1() -> None:
    with tempfile.TemporaryDirectory() as root:
        code = run_invoke(LocalContext(), "trufflehog", [], root, timeout=None)
    assert code == 1


def test_runs_the_installed_tool_forwarding_args_output_and_exit_code() -> None:
    with tempfile.TemporaryDirectory() as root:
        _install_fake(root, TRUFFLEHOG, '#!/bin/sh\necho "ran $*"\nexit 5\n')
        out = io.StringIO()
        with redirect_stdout(out):
            code = run_invoke(
                LocalContext(), "trufflehog", ["--only", "verified"], root, timeout=None
            )
    assert code == 5  # the tool's own exit code is forwarded
    assert "ran --only verified" in out.getvalue()
