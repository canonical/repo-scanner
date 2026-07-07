"""The `reposcan bootstrap` command: install tools onto the host (or, with an
explicit --backend, into a container). All scanning tools by default, or a named
subset; either way each tool's prerequisites (uv, the Go SDK) are pulled in
automatically."""

import logging

from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import Failure
from repo_scanner.tools.install import install_plan
from repo_scanner.tools.model import Platform, Tool
from repo_scanner.tools.registry import TOOLS

logger = logging.getLogger(__name__)


def run_bootstrap(
    ctx: ExecutionContext,
    names: list[str],
    platform: Platform,
    install_root: str,
) -> int:
    """Install `names` (an empty list means every scanning tool), adding the
    prerequisites each depends on. Tools install as independent groups: if one fails
    it is reported and the rest proceed, since 9 of 10 installed beats 0. Returns 0
    when every tool installed, 1 if any failed, or 2 for an unknown tool name."""
    if names:
        requested: list[Tool] = []
        unknown = []
        for name in names:
            tool = TOOLS.get(name)
            if tool is None:
                unknown.append(name)
            else:
                requested.append(tool)
        if unknown:
            logger.error("unknown tool(s): %s", ", ".join(unknown))
            return 2
    else:
        requested = list(TOOLS.values())

    plan = install_plan(requested, platform, install_root)
    failed = []
    for step in plan:
        logger.info("installing %s %s", step.tool.name, step.tool.version)
        reason = None
        for command in step.commands:
            result = ctx.run(["sh", "-euc", command])
            if isinstance(result, Failure):
                reason = result.reason
                break
            if not result.ok:
                reason = result.stderr.strip() or f"exit code {result.exit_code}"
                break
        if reason is not None:
            logger.error("failed to install %s: %s", step.tool.name, reason)
            failed.append(step.tool.name)

    if failed:
        logger.error(
            "%d of %d tools failed: %s", len(failed), len(plan), ", ".join(failed)
        )
        return 1
    logger.info("installed %d tools into %s", len(plan), install_root)
    return 0
