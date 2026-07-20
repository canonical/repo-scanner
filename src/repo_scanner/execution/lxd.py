"""LXD execution context: run commands in an ephemeral container via the lxc
CLI (no SDK)."""

import os
from collections.abc import Mapping, Sequence

from repo_scanner.execution.firewall import warn_if_lxd_bridge_blocked
from repo_scanner.execution.process import ExecResult, Failure, run_process

# The dedicated LXD project reposcan works in. Every instance- or image-acting lxc
# command is pinned to it (the LXC prefix) so reposcan's ephemeral containers and its
# built tool image never land in the user's default project.
PROJECT = "reposcan"
LXC = ["lxc", "--project", PROJECT]


def ensure_project() -> Failure | None:
    """Create reposcan's LXD project if it does not exist yet; a no-op once it does.
    features.images=true keeps the built tool image inside this project rather than the
    default one; features.profiles=false borrows the default project's profile so
    containers still get its root disk and network and launch with no per-project setup.
    Instances are isolated to the project regardless (that is what LXD projects do)."""
    presence_check = run_process(["lxc", "project", "show", PROJECT])
    if isinstance(presence_check, ExecResult) and presence_check.ok:
        return None
    created = run_process(
        [
            "lxc",
            "project",
            "create",
            PROJECT,
            "-c",
            "features.images=true",
            "-c",
            "features.profiles=false",
        ],
        check=True,
    )
    return created if isinstance(created, Failure) else None


class LxdContext:
    """Runs commands in an ephemeral container via `lxc`, launched from `image`
    (a stock base for plain runs, or the tool image for scans)."""

    name = "lxd"

    def __init__(self, image: str) -> None:
        self._image = image
        self._instance_name: str | None = None

    def start(self) -> Failure | None:
        warn_if_lxd_bridge_blocked()
        project_creation_error = ensure_project()
        if project_creation_error is not None:
            return project_creation_error
        handle = f"reposcan-{os.getpid()}"
        result = run_process([*LXC, "launch", self._image, handle, "--ephemeral"])
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
        argv = [*LXC, "exec", self._instance_name]
        if cwd is not None:
            argv += ["--cwd", cwd]
        for key, value in sorted((env or {}).items()):
            argv += ["--env", f"{key}={value}"]
        argv += ["--", *command]
        return run_process(argv, timeout=timeout)

    def stop(self) -> None:
        if self._instance_name is not None:
            run_process([*LXC, "stop", self._instance_name])
            self._instance_name = None
