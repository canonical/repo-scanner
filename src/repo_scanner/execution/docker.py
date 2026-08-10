# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Docker execution context: run commands in an ephemeral container.

Uses the docker CLI (no SDK).
"""

from collections.abc import Mapping, Sequence

from repo_scanner.execution.process import ExecResult, Failure, run_process


class DockerContext:
    """Runs commands in an ephemeral container via `docker`, started from `image`."""

    name = "docker"

    def __init__(self, image: str) -> None:
        self._image = image
        self._instance_name: str | None = None

    def start(self) -> Failure | None:
        result = run_process(
            ["docker", "run", "-d", "--rm", self._image, "sleep", "infinity"]
        )
        if isinstance(result, Failure):
            return result
        if result.exit_code != 0:
            return Failure(reason=result.stderr.strip() or "docker run failed")
        self._instance_name = result.stdout.strip()
        return None

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult | Failure:
        if self._instance_name is None:
            return Failure(reason="container is not started")
        argv = ["docker", "exec"]
        if cwd is not None:
            argv += ["-w", cwd]
        for key, value in sorted((env or {}).items()):
            argv += ["-e", f"{key}={value}"]
        argv += [self._instance_name, *command]
        return run_process(argv, timeout=timeout)

    def stop(self) -> None:
        if self._instance_name is not None:
            run_process(["docker", "rm", "-f", self._instance_name])
            self._instance_name = None
