"""Tests for the LXD execution context (repo_scanner.execution.lxd).

lxc is not invoked: run_process is patched with a fake that records the argv.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.execution.lxd as lxd
from repo_scanner.execution.lxd import LxdContext
from repo_scanner.execution.process import ExecResult, Failure


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


def test_launches_an_ephemeral_container_and_execs_commands_in_it() -> None:
    with _patched_run(ExecResult(0, "", "")) as calls:
        ctx = LxdContext()
        assert ctx.start() is None
        assert ctx._instance_name is not None
        assert calls[-1][:2] == ["lxc", "launch"] and "--ephemeral" in calls[-1]
        ctx.run(["ls"], cwd="/src", env={"K": "V"})
    name = ctx._instance_name
    expected = ["lxc", "exec", name, "--cwd", "/src", "--env", "K=V", "--", "ls"]
    assert calls[-1] == expected
