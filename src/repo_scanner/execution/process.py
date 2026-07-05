"""Run a subprocess and return its outcome as a value.

`run_process` captures stdout and stderr (so a caller can parse or display them
regardless of exit code), enforces an optional timeout, and translates the ways a
process can fail to start, or to finish in time, into a Failure instead of raising.
A process that runs to completion yields an ExecResult carrying its exit code and
output, even when that exit code is nonzero.
"""

import subprocess
from collections.abc import Mapping, Sequence

from repo_scanner.execution.context import ExecResult, Failure


def run_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> ExecResult | Failure:
    """Run `command`. Return an ExecResult if it ran (any exit code), or a Failure
    if it could not be started or exceeded `timeout` (None means no limit)."""
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
    return ExecResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
