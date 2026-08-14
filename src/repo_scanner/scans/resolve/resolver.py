# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Resolver interface."""

from collections.abc import Mapping
from typing import Protocol

from repo_scanner.execution.context import ExecutionContext


class Resolver(Protocol):
    """Resolves one ecosystem's dependencies into a writable copy of the repo.

    A resolver claims the directories it can resolve from the repo's tracked-file
    listing (`find_roots`), then generates a lockfile in each (`resolve`). New
    ecosystems plug in by implementing this and joining the `_RESOLVERS` registry in
    `core`.
    """

    name: str

    def find_roots(self, tracked: Mapping[str, set[str]]) -> list[str]:
        """The directories (relative to the repo, "" for its root) to resolve.

        Args:
            tracked: Each tracked directory mapped to the set of file basenames in it.

        Returns:
            The directories holding a manifest this resolver handles.
        """
        ...

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
        """Generate a lockfile for the manifest(s) in one directory of the copy.

        Args:
            ctx: The started context to run the resolver in.
            repo_dir: The writable repo copy's path in the context.
            directory: The directory to resolve, relative to `repo_dir` ("" for root).
            names: The file basenames in `directory`.
            tool_root: Where the tools are installed in the context.
            uid: The user id the resolver runs as.
            allow_code_execution: Permit building source packages (runs untrusted code).
        """
        ...
