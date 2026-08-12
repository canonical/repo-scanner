# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Local execution context: run commands directly on the host."""

import os
from collections.abc import Mapping, Sequence

from repo_scanner.execution.process import ExecResult, Failure, run_process


class LocalContext:
    """Runs commands on the host.

    Nothing to start or stop. Per-command `env` is overlaid on the inherited host
    environment.
    """

    name = "local"

    def start(self) -> Failure | None:
        return None

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        uid: int | None = None,  # ignored: local runs as the invoking user
        timeout: float | None = None,
        stream_stdout: bool = False,
        stream_stderr: bool = False,
    ) -> ExecResult | Failure:
        run_env = None if env is None else {**os.environ, **env}
        return run_process(
            command,
            cwd=cwd,
            env=run_env,
            timeout=timeout,
            stream_stdout=stream_stdout,
            stream_stderr=stream_stderr,
        )

    def stop(self) -> None:
        return None
