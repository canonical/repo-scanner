"""Integration tests for the container execution contexts.

Unlike the unit tests, these invoke real docker / lxc and start real ephemeral
ubuntu:24.04 containers. They are excluded from the default unit run
(`testpaths = ["tests/unit"]`); run them explicitly with:

    pytest tests/integration

Each test skips cleanly when its backend is unavailable, so this is safe to run
on a host with only one (or neither) backend. The LXD image may be downloaded on
first run, so the first lxd test can be slow.
"""

import pytest

from repo_scanner.execution.context import ExecResult, ExecutionContext, Failure
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.lxd import LxdContext


def _exercise_lifecycle(ctx: ExecutionContext) -> None:
    """Run a series of commands in an already-started context and check that they
    execute inside the ubuntu:24.04 container with cwd/env/exit-code honored."""
    # Runs in the ubuntu:24.04 image, not on the host.
    os_release = ctx.run(["cat", "/etc/os-release"])
    assert isinstance(os_release, ExecResult), os_release
    assert os_release.ok
    assert 'VERSION_ID="24.04"' in os_release.stdout

    # The command's exit code is propagated.
    exit_code = ctx.run(["sh", "-c", "exit 7"])
    assert isinstance(exit_code, ExecResult), exit_code
    assert exit_code.exit_code == 7

    # Per-command env reaches the container.
    env = ctx.run(["sh", "-c", "echo $REPOSCAN_IT"], env={"REPOSCAN_IT": "present"})
    assert isinstance(env, ExecResult), env
    assert env.stdout.strip() == "present"

    # cwd is honored.
    cwd = ctx.run(["pwd"], cwd="/tmp")
    assert isinstance(cwd, ExecResult), cwd
    assert cwd.stdout.strip() == "/tmp"


def test_docker_context_lifecycle() -> None:
    ctx = DockerContext()
    availability = ctx.availability()
    if not availability.ok:
        pytest.skip(f"docker unavailable: {availability.reason}")

    started = ctx.start()
    assert started is None, f"docker run failed: {started}"
    try:
        _exercise_lifecycle(ctx)
    finally:
        ctx.stop()

    # After stop the context has no running container.
    assert isinstance(ctx.run(["true"]), Failure)


def test_lxd_context_lifecycle() -> None:
    ctx = LxdContext()
    availability = ctx.availability()
    if not availability.ok:
        pytest.skip(f"lxd unavailable: {availability.reason}")

    started = ctx.start()
    # If this fails right after launch, the container may not be ready to exec yet
    # and LxdContext.start would need a readiness wait.
    assert started is None, f"lxc launch failed: {started}"
    try:
        _exercise_lifecycle(ctx)
    finally:
        ctx.stop()

    # After stop the context has no running container.
    assert isinstance(ctx.run(["true"]), Failure)
