# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan invoke` action: run an installed tool, passing arguments through."""

import logging
import sys

from repo_scanner.actions.base import Action
from repo_scanner.backends import start_session
from repo_scanner.clikit import option, positional, remainder
from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.tools.registry import TOOLS

logger = logging.getLogger(__name__)

# Exit code returned when the tool is killed for exceeding its timeout.
TIMEOUT_EXIT_CODE = 124


class InvokeAction(Action):
    name = "invoke"
    help = "Run an installed tool, passing arguments through to it."

    timeout: float | None = option(
        convert=float,
        help="Kill the tool if it runs longer than this (default: no limit).",
    )
    tool: str = positional(help="The installed tool to run.")
    argv: list[str] = remainder(
        help="Arguments for the tool, after a double-hyphen (invoke semgrep -- --help)."
    )

    def run(self) -> int:
        with start_session(self.backend, tool_image=True, image=self.image) as session:
            if not session.ok:
                return session.exit_code
            return invoke(
                session.context,
                self.tool,
                self.argv,
                session.tool_root,
                timeout=self.timeout,
            )


def invoke(
    ctx: ExecutionContext,
    name: str,
    args: list[str],
    install_root: str,
    *,
    timeout: float | None,
) -> int:
    """Run the installed tool `name` with `args`, forwarding its output and exit code.

    Returns 2 for an unknown tool, 1 when it is not installed or could not be started,
    124 on timeout, or the tool's own exit code.
    """
    tool = TOOLS.get(name)
    if tool is None:
        logger.error("unknown tool: %s", name)
        return 2
    executable = tool.installed_path(install_root)
    probe = ctx.run(["test", "-x", executable])
    if isinstance(probe, Failure) or not probe.ok:
        logger.error("%s is not installed; run: reposcan bootstrap %s", name, name)
        return 1

    result = ctx.run([executable, *args], timeout=timeout)
    if isinstance(result, Failure):
        logger.error("%s", result.reason)
        return TIMEOUT_EXIT_CODE if result.timed_out else 1
    # Forward the tool's own output verbatim; this is program output, not a log.
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.exit_code
