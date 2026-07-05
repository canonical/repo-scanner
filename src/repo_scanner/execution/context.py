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
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExecResult:
    """The outcome of a command that ran to completion (any exit code)."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class Failure:
    """An operation that did not complete: a context that could not be started, or
    a command that could not be started or exceeded its timeout. `reason` is
    human-readable."""

    reason: str
    timed_out: bool = False


@dataclass(frozen=True)
class Availability:
    """Whether a context is usable on this host, with a reason to show the user."""

    ok: bool
    reason: str = ""


class ExecutionContext(Protocol):
    """A place reposcan can run commands: the local host, or an ephemeral container."""

    name: str

    def availability(self) -> Availability: ...

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
