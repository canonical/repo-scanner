"""Docker execution context: run commands in an ephemeral container via the
docker CLI (no SDK)."""

from collections.abc import Mapping, Sequence

from repo_scanner.execution.context import Availability, ExecResult, Failure
from repo_scanner.execution.process import run_process

_IMAGE = "ubuntu:24.04"


class DockerContext:
    """Runs commands in an ephemeral `ubuntu:24.04` container via `docker`."""

    name = "docker"

    def __init__(self) -> None:
        self._instance_name: str | None = None

    def availability(self) -> Availability:
        result = run_process(["docker", "info"], timeout=10)
        if isinstance(result, Failure):
            return Availability(ok=False, reason=result.reason)
        if result.exit_code != 0:
            reason = result.stderr.strip() or "docker is not available"
            return Availability(ok=False, reason=reason)
        return Availability(ok=True)

    def start(self) -> Failure | None:
        result = run_process(
            ["docker", "run", "-d", "--rm", _IMAGE, "sleep", "infinity"]
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
