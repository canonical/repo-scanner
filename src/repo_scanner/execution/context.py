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

from collections.abc import Mapping, Sequence
from typing import Protocol

from repo_scanner.execution.process import ExecResult, Failure


class ExecutionContext(Protocol):
    """A place reposcan can run commands: the local host, or an ephemeral container.
    Whether the backend is available is decided before a context is made (see
    backends.py), so a context is just a lifecycle: start(), run(), stop()."""

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
