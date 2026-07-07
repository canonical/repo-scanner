"""Tests for the Docker execution context (repo_scanner.execution.docker).

docker is not invoked: run_process is patched with a fake that records the argv.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.execution.docker as docker
from repo_scanner.execution.docker import DockerContext
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

    saved = docker.run_process
    docker.run_process = fake
    try:
        yield calls
    finally:
        docker.run_process = saved


def test_starts_the_given_image_and_execs_commands_in_it() -> None:
    with _patched_run(ExecResult(0, "abc123\n", "")) as calls:
        ctx = DockerContext("reposcan:tools")
        assert ctx.start() is None
        assert ctx._instance_name == "abc123"  # container id from `docker run`
        assert "reposcan:tools" in calls[-1]  # started from the given image
        ctx.run(["ls", "-a"], cwd="/src", env={"K": "V"})
    expected = ["docker", "exec", "-w", "/src", "-e", "K=V", "abc123", "ls", "-a"]
    assert calls[-1] == expected
