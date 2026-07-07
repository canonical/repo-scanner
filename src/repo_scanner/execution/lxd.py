"""LXD execution context: run commands in an ephemeral container via the lxc
CLI (no SDK)."""

import logging
import os
from collections.abc import Mapping, Sequence

from repo_scanner.execution.firewall import firewall_warning
from repo_scanner.execution.process import ExecResult, Failure, run_process

logger = logging.getLogger(__name__)

_BRIDGE = "lxdbr0"


class LxdContext:
    """Runs commands in an ephemeral container via `lxc`, launched from `image`
    (a stock base for plain runs, or the tool image for scans)."""

    name = "lxd"

    def __init__(self, image: str) -> None:
        self._image = image
        self._instance_name: str | None = None

    def start(self) -> Failure | None:
        warning = firewall_warning(_BRIDGE)
        if warning is not None:
            logger.warning(warning)
        handle = f"reposcan-{os.getpid()}"
        result = run_process(["lxc", "launch", self._image, handle, "--ephemeral"])
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
