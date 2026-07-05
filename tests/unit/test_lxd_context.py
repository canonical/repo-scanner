"""Tests for the LXD execution context (repo_scanner.execution.lxd).

lxc is not invoked: the tests patch the module's run_process with a fake that
records the CLI argv and returns a canned result.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.execution.lxd as lxd
from repo_scanner.execution.context import ExecResult, Failure
from repo_scanner.execution.lxd import LxdContext


@contextmanager
def _patched_run(result: ExecResult | Failure):
    calls: list[list[str]] = []

    def fake(
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult | Failure:
        calls.append(list(command))
        return result

    saved = lxd.run_process
    lxd.run_process = fake
    try:
        yield calls
    finally:
        lxd.run_process = saved


def test_available_when_lxc_info_succeeds() -> None:
    with _patched_run(ExecResult(0, "", "")):
        assert LxdContext().availability().ok


def test_start_launches_an_ephemeral_container() -> None:
    with _patched_run(ExecResult(0, "", "")) as calls:
        ctx = LxdContext()
        assert ctx.start() is None
        assert ctx._instance_name is not None
    assert calls[-1][:2] == ["lxc", "launch"]
    assert "--ephemeral" in calls[-1]


def test_run_execs_in_the_started_container() -> None:
    with _patched_run(ExecResult(0, "", "")) as calls:
        ctx = LxdContext()
        ctx._instance_name = "reposcan-1"
        ctx.run(["ls"], cwd="/src", env={"K": "V"})
    assert calls[-1] == [
        "lxc",
        "exec",
        "reposcan-1",
        "--cwd",
        "/src",
        "--env",
        "K=V",
        "--",
        "ls",
    ]
