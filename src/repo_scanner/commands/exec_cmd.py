"""The `reposcan exec` command: run a command within the selected execution
context. Only the local context exists so far."""

import logging
import sys

from repo_scanner.execution.context import ExecutionContext, Failure

logger = logging.getLogger(__name__)

# Exit code returned when a command is killed for exceeding its timeout.
TIMEOUT_EXIT_CODE = 124


def run_exec(
    context: ExecutionContext, command: list[str], *, timeout: float | None
) -> int:
    """Run `command` in the already-started `context` and return an exit code: the
    command's own exit code when it ran, 2 for a usage error, 124 on timeout, or 1
    when it could not be started."""
    if not command:
        logger.error("no command given")
        return 2
    result = context.run(command, timeout=timeout)
    if isinstance(result, Failure):
        logger.error("%s", result.reason)
        return TIMEOUT_EXIT_CODE if result.timed_out else 1
    # Forward the command's own output verbatim; this is program output, not a log.
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.exit_code
