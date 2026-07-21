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
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import IO, TextIO


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


class _Tee:
    """Drains one pipe into a buffer and -- when a live stream is given -- echoes it to
    that stream a character at a time (like `tee`), so output with no trailing newline
    (prompts, progress bars) shows immediately instead of waiting for the line to end.
    The capture stays line-oriented. One instance handles one pipe; stdout and stderr
    each get their own so that reading both concurrently (on separate threads) never
    deadlocks on a full pipe buffer. A None live stream captures without echoing."""

    def __init__(self, source: IO[str], live: TextIO | None) -> None:
        self._source = source
        self._live = live
        self._captured: list[str] = []

    def drain(self) -> None:
        """Read the source to EOF, echoing each character live (when a live stream is
        set) and buffering the text as whole lines."""
        line: list[str] = []
        while True:
            char = self._source.read(1)
            if not char:  # EOF
                break
            if self._live is not None:
                self._live.write(char)
                self._live.flush()
            line.append(char)
            if char == "\n":
                self._captured.append("".join(line))
                line = []
        if line:  # trailing text with no final newline
            self._captured.append("".join(line))

    @property
    def captured(self) -> str:
        return "".join(self._captured)


def run_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    check: bool = False,
    stream: bool = False,
) -> ExecResult | Failure:
    """Run `command`. Return an ExecResult if it ran, or a Failure if it could not be
    started or exceeded `timeout` (None means no limit). With `check`, a nonzero exit
    is also a Failure, so a returned ExecResult has exited 0. With `stream`, the
    command's output is also streamed to this process's console as it runs.
    """
    argv = list(command)
    if not argv:
        return Failure(reason="no command given")
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return Failure(reason=f"command not found: {argv[0]}")
    except PermissionError:
        return Failure(reason=f"permission denied: {argv[0]}")
    except OSError as exc:
        return Failure(reason=f"could not start {argv[0]}: {exc}")

    assert process.stdout is not None and process.stderr is not None
    out = _Tee(process.stdout, sys.stdout if stream else None)
    err = _Tee(process.stderr, sys.stderr if stream else None)
    readers = [threading.Thread(target=out.drain), threading.Thread(target=err.drain)]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()  # closes the pipes, so the reader threads reach EOF and exit
        process.wait()
        for reader in readers:
            reader.join()
        return Failure(
            reason=f"timed out after {timeout} seconds: {argv[0]}", timed_out=True
        )
    for reader in readers:
        reader.join()
    if check and process.returncode != 0:
        reason = err.captured.strip() or f"{argv[0]} exited {process.returncode}"
        return Failure(reason=reason)
    return ExecResult(
        exit_code=process.returncode, stdout=out.captured, stderr=err.captured
    )
