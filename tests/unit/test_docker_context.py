"""Tests for the Docker execution context (repo_scanner.execution.docker).

docker is not invoked: the tests patch the module's run_process with a fake that
records the CLI argv and returns a canned result.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.execution.docker as docker
from repo_scanner.execution.context import ExecResult, Failure
from repo_scanner.execution.docker import DockerContext


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

    saved = docker.run_process
    docker.run_process = fake
    try:
        yield calls
    finally:
        docker.run_process = saved


def test_available_when_docker_info_succeeds() -> None:
    with _patched_run(ExecResult(0, "", "")):
        assert DockerContext().availability().ok


def test_unavailable_reports_a_reason() -> None:
    with _patched_run(Failure(reason="command not found: docker")):
        missing = DockerContext().availability()
    assert not missing.ok and "docker" in missing.reason

    with _patched_run(ExecResult(1, "", "Cannot connect to the Docker daemon")):
        down = DockerContext().availability()
    assert not down.ok and "daemon" in down.reason


def test_start_captures_the_container_id() -> None:
    with _patched_run(ExecResult(0, "abc123\n", "")):
        ctx = DockerContext()
        assert ctx.start() is None
    assert ctx._instance_name == "abc123"


def test_run_execs_in_the_started_container() -> None:
    with _patched_run(ExecResult(0, "", "")) as calls:
        ctx = DockerContext()
        ctx._instance_name = "abc123"
        ctx.run(["ls", "-a"], cwd="/src", env={"K": "V"})
    assert calls[-1] == [
        "docker",
        "exec",
        "-w",
        "/src",
        "-e",
        "K=V",
        "abc123",
        "ls",
        "-a",
    ]
