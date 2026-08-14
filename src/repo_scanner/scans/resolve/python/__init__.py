# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Python ecosystem resolver.

uv (PEP 621 / `requirements*` / `setup.cfg`), Poetry (legacy `[tool.poetry]`), and
Pipenv (`Pipfile`) can each apply to a directory independently. Each is a no-op when
its manifest is absent, the wrong flavor, or already locked.
"""

import logging
from collections.abc import Mapping

from repo_scanner.execution.context import ExecutionContext
from repo_scanner.scans.resolve.python.pipenv import Pipenv
from repo_scanner.scans.resolve.python.poetry import Poetry
from repo_scanner.scans.resolve.python.uv import Uv
from repo_scanner.scans.resolve.resolver import PackageManager

logger = logging.getLogger(__name__)


class PythonResolver:
    """Resolves Python dependencies."""

    name = "python"
    _managers: tuple[PackageManager, ...] = (Uv(), Poetry(), Pipenv())

    def find_roots(self, tracked: Mapping[str, set[str]]) -> list[str]:
        """The directories at least one Python package manager can resolve."""
        return sorted(
            directory
            for directory, names in tracked.items()
            if any(manager.can_resolve(names) for manager in self._managers)
        )

    def resolve(
        self,
        ctx: ExecutionContext,
        repo_dir: str,
        directory: str,
        names: set[str],
        tool_root: str,
        uid: int,
        *,
        allow_code_execution: bool,
    ) -> None:
        """Run every package manager that can resolve `directory` in the copy."""
        workdir = repo_dir if not directory else f"{repo_dir}/{directory}"
        for manager in self._managers:
            if manager.can_resolve(names):
                manager.resolve(
                    ctx,
                    workdir,
                    names,
                    tool_root,
                    uid,
                    allow_code_execution=allow_code_execution,
                )
