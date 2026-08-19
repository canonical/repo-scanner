# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Local execution context: run commands directly on the host."""

import logging
import os
from collections.abc import Mapping, Sequence

from repo_scanner.execution.context import RunUser
from repo_scanner.execution.process import ExecResult, Failure, run_process

logger = logging.getLogger(__name__)


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
        user: RunUser | None = None,
        timeout: float | None = None,
        stream_stdout: bool = False,
        stream_stderr: bool = False,
        stdin: str | None = None,
    ) -> ExecResult | Failure:
        if user is not None:
            logger.warning(
                "the local backend runs as the invoking user (uid %d); ignoring the "
                "requested identity (uid %d)",
                os.getuid(),
                user.uid,
            )
        run_env = None if env is None else {**os.environ, **env}
        return run_process(
            command,
            cwd=cwd,
            env=run_env,
            timeout=timeout,
            stream_stdout=stream_stdout,
            stream_stderr=stream_stderr,
            stdin=stdin,
        )

    def stop(self) -> None:
        return None
