"""Tests for the `reposcan invoke` command (repo_scanner.commands.invoke_cmd)."""

import io
import os
import stat
import tempfile
from contextlib import redirect_stdout

from repo_scanner.commands.invoke_cmd import run_invoke
from repo_scanner.execution.local import LocalContext
from repo_scanner.tools.registry import TRUFFLEHOG


def test_rejects_an_unknown_or_uninstalled_tool() -> None:
    with tempfile.TemporaryDirectory() as root:
        assert run_invoke(LocalContext(), "not-a-tool", [], root, timeout=None) == 2
        # trufflehog is a real tool but nothing is installed under this root.
        assert run_invoke(LocalContext(), "trufflehog", [], root, timeout=None) == 1


def test_runs_the_installed_tool_forwarding_args_output_and_exit_code() -> None:
    with tempfile.TemporaryDirectory() as root:
        # Write an executable stand-in where trufflehog would install.
        path = TRUFFLEHOG.installed_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write('#!/bin/sh\necho "ran $*"\nexit 5\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IRUSR)

        out = io.StringIO()
        with redirect_stdout(out):
            code = run_invoke(
                LocalContext(), "trufflehog", ["--only", "verified"], root, timeout=None
            )
    assert code == 5  # the tool's own exit code is forwarded
    assert "ran --only verified" in out.getvalue()
