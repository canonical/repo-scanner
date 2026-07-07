"""Run a subprocess and return its outcome as a value.

`run_process` captures stdout and stderr (so a caller can parse or display them
regardless of exit code), enforces an optional timeout, and translates the ways a
process can fail to start, or to finish in time, into a Failure instead of raising.
A process that runs to completion yields an ExecResult carrying its exit code and
output, even when that exit code is nonzero -- unless `check` is set, in which case a
nonzero exit is itself a Failure (like `subprocess.run(check=True)`, but returned
rather than raised). Use `check` when a command's only interesting outcome is whether
it succeeded.
"""

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


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


def run_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> ExecResult | Failure:
    """Run `command`. Return an ExecResult if it ran, or a Failure if it could not be
    started or exceeded `timeout` (None means no limit). With `check`, a nonzero exit
    is also a Failure, so a returned ExecResult has exited 0."""
    argv = list(command)
    if not argv:
        return Failure(reason="no command given")
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return Failure(
            reason=f"timed out after {exc.timeout} seconds: {argv[0]}",
            timed_out=True,
        )
    except FileNotFoundError:
        return Failure(reason=f"command not found: {argv[0]}")
    except PermissionError:
        return Failure(reason=f"permission denied: {argv[0]}")
    except OSError as exc:
        return Failure(reason=f"could not start {argv[0]}: {exc}")
    if check and completed.returncode != 0:
        reason = completed.stderr.strip() or f"{argv[0]} exited {completed.returncode}"
        return Failure(reason=reason)
    return ExecResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
