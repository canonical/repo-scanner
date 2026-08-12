# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Docker execution context: run commands in an ephemeral container.

Uses the docker CLI (no SDK).
"""

from collections.abc import Mapping, Sequence

from repo_scanner.execution.context import as_user, home_for, mounted_target
from repo_scanner.execution.process import ExecResult, Failure, run_process


class DockerContext:
    """Runs commands in an ephemeral container via `docker`, started from `image`.

    When `mount_source` is given, that host directory is bind-mounted read-only at
    `mounted_target(mount_source)` so a scan can reach the repository.
    """

    name = "docker"

    def __init__(self, image: str, mount_source: str | None = None) -> None:
        self._image = image
        self._mount_source = mount_source
        self._instance_name: str | None = None

    def start(self) -> Failure | None:
        argv = ["docker", "run", "-d", "--rm"]
        if self._mount_source is not None:
            src = self._mount_source
            argv += ["-v", f"{src}:{mounted_target(src)}:ro"]
        argv += [self._image, "sleep", "infinity"]
        result = run_process(argv)
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
        uid: int | None = None,
        timeout: float | None = None,
        stream_stdout: bool = False,
        stream_stderr: bool = False,
    ) -> ExecResult | Failure:
        if self._instance_name is None:
            return Failure(reason="container is not started")
        argv = ["docker", "exec"]
        if cwd is not None:
            argv += ["-w", cwd]
        run_env = dict(env or {})
        command = list(command)
        if uid is not None:
            run_env.setdefault("HOME", home_for(uid))
            command = as_user(command, uid)
        for key, value in sorted(run_env.items()):
            argv += ["-e", f"{key}={value}"]
        argv += [self._instance_name, *command]
        return run_process(
            argv,
            timeout=timeout,
            stream_stdout=stream_stdout,
            stream_stderr=stream_stderr,
        )

    def stop(self) -> None:
        if self._instance_name is not None:
            run_process(["docker", "rm", "-f", self._instance_name])
            self._instance_name = None
