"""LXD execution context: run commands in an ephemeral container via the lxc
CLI (no SDK)."""

import logging
import os
from collections.abc import Mapping, Sequence

from repo_scanner.execution.context import Availability, ExecResult, Failure
from repo_scanner.execution.firewall import firewall_warning
from repo_scanner.execution.process import run_process

logger = logging.getLogger(__name__)

_IMAGE = "ubuntu:24.04"
_BRIDGE = "lxdbr0"


class LxdContext:
    """Runs commands in an ephemeral `ubuntu:24.04` container via `lxc`."""

    name = "lxd"

    def __init__(self) -> None:
        self._instance_name: str | None = None

    def availability(self) -> Availability:
        result = run_process(["lxc", "info"], timeout=10)
        if isinstance(result, Failure):
            return Availability(ok=False, reason=result.reason)
        if result.exit_code != 0:
            reason = result.stderr.strip() or "lxd is not available"
            return Availability(ok=False, reason=reason)
        return Availability(ok=True)

    def start(self) -> Failure | None:
        warning = firewall_warning(_BRIDGE)
        if warning is not None:
            logger.warning(warning)
        handle = f"reposcan-{os.getpid()}"
        result = run_process(["lxc", "launch", _IMAGE, handle, "--ephemeral"])
        if isinstance(result, Failure):
            return result
        if result.exit_code != 0:
            return Failure(reason=result.stderr.strip() or "lxc launch failed")
        self._instance_name = handle
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
        argv = ["lxc", "exec", self._instance_name]
        if cwd is not None:
            argv += ["--cwd", cwd]
        for key, value in sorted((env or {}).items()):
            argv += ["--env", f"{key}={value}"]
        argv += ["--", *command]
        return run_process(argv, timeout=timeout)

    def stop(self) -> None:
        if self._instance_name is not None:
            run_process(["lxc", "stop", self._instance_name])
            self._instance_name = None
