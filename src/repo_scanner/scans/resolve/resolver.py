# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""`Resolver` and `PackageManager` interfaces.

A `Resolver` coordinates one ecosystem (Python, JS, Go): it discovers the directories
the ecosystem can resolve and drives resolution in each by composing
`PackageManager`s -- specific tools within the ecosystem (uv, poetry, pipenv;
later npm, pnpm).
"""

from collections.abc import Mapping
from typing import Protocol

from repo_scanner.execution.context import ExecutionContext


class Resolver(Protocol):
    """Coordinates dependency resolution for an ecosystem.

    Discovers directories it can resolve from the repo's tracked-file listing
    (`find_roots`) and resolves each (`resolve`) by dispatching to `PackageManager`s.
    """

    name: str

    def find_roots(self, tracked: Mapping[str, set[str]]) -> list[str]:
        """The directories (relative to the repo, "" for its root) to resolve.

        Args:
            tracked: Each tracked directory mapped to the set of file basenames in it.

        Returns:
            The directories this ecosystem can resolve something in.
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


class PackageManager(Protocol):
    """A package manager within an ecosystem (uv, poetry, pipenv, npm, ...)."""

    def can_resolve(self, names: set[str]) -> bool:
        """Whether this package manager can resolve deps in a directory with `names`.

        Args:
            names: The file basenames in the directory.

        Returns:
            True if the directory holds a manifest this manager owns and no lock it
            would only reproduce.
        """
        ...

    def resolve(
        self,
        ctx: ExecutionContext,
        workdir: str,
        names: set[str],
        tool_root: str,
        uid: int,
        *,
        allow_code_execution: bool,
    ) -> None:
        """Generate a lockfile in `workdir`.

        Args:
            ctx: The started context to run the package manager in.
            workdir: The directory's absolute path in the writable repo copy.
            names: The file basenames in `workdir`.
            tool_root: Where the tools are installed in the context.
            uid: The user id the package manager runs as.
            allow_code_execution: Permit building source packages
                (may run untrusted code).
        """
        ...
