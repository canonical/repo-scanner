# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Value types and the ExecutionContext Protocol.

An ExecutionContext is a place reposcan can run commands: the local host, or an
ephemeral Docker/LXD container. main owns its lifecycle with start() and stop(),
and commands run() in between. Contexts are structural (Protocol) types, so a
concrete context is any object with the right methods.

Outcomes are returned, not raised. start() returns None on success or a Failure
carrying the reason. run() yields an ExecResult with the command's exit code and
captured output (whatever that exit code), or a Failure when the command could not
be started or timed out.
"""

import os
from collections.abc import Mapping, Sequence
from typing import Protocol

from repo_scanner.execution.process import ExecResult, Failure

# Parent directory a scanned source is bind-mounted under inside a container. A fixed
# parent (rather than the filesystem root) avoids colliding with system directories.
MOUNT_PARENT = "/scan"


def mounted_target(mount_source: str) -> str:
    """Where a mounted source directory appears inside a container.

    The source keeps its own directory name under `MOUNT_PARENT`, so tools that
    surface the directory in their output show the real repository name.

    Args:
        mount_source: The host directory being mounted for scanning.

    Returns:
        The in-container path, e.g. `/scan/<basename>`.
    """
    return f"{MOUNT_PARENT}/{os.path.basename(os.path.realpath(mount_source))}"


class ExecutionContext(Protocol):
    """A place reposcan can run commands: the local host, or an ephemeral container.

    Whether the backend is available is decided before a context is made (see
    backends.py), so a context is just a lifecycle: start(), run(), stop().
    """

    name: str

    def start(self) -> Failure | None: ...

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult | Failure: ...

    def stop(self) -> None: ...
