# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exclude gitignored paths from filesystem-walking scanners.

SBOM tools (trivy, syft, cdxgen) and SCA tools (trivy, grype) catalog a repo by
walking its working tree, so they descend into git-ignored directories (.venv,
.tox, node_modules) and report packages that are not part of the project. No tool
honors .gitignore natively; each takes a manual exclude flag with its own glob
dialect.
"""

import logging
from dataclasses import dataclass

from repo_scanner.execution.context import ExecutionContext
from repo_scanner.execution.process import ExecResult

logger = logging.getLogger(__name__)

# Tools whose scan walks the filesystem and so accepts path exclusions. A scan that
# invokes none of these skips the (otherwise pointless) git lookup entirely.
EXCLUDABLE_TOOLS = frozenset({"trivy", "syft", "grype", "cdxgen"})


@dataclass(frozen=True)
class IgnoredPaths:
    """Repository-root-relative paths git ignores, split into directories and files."""

    dirs: tuple[str, ...] = ()
    files: tuple[str, ...] = ()

    @classmethod
    def from_context(cls, ctx: ExecutionContext, target: str) -> "IgnoredPaths":
        """The paths git ignores under `target`, found by running git in `ctx`.

        Runs `git ls-files` (read-only) with `target` as the working directory, so
        git resolves its own ignore rules (.gitignore, .git/info/exclude, the global
        excludes file). Wholly-ignored directories collapse to one entry. Returns
        empty when `target` is not a git working tree or git is unavailable.

        Args:
            ctx: The started context to run git in.
            target: The repository path as seen in the context.

        Returns:
            The ignored directories and files, relative to the repository root.
        """
        result = ctx.run(
            [
                "git",
                "ls-files",
                "-z",  # NUL-delimited, so odd paths are not quoted or split
                "--others",  # untracked entries (ignored files are untracked)
                "--ignored",
                "--exclude-standard",  # honor .gitignore and the other ignore sources
                "--directory",  # collapse a wholly-ignored directory to "<dir>/"
            ],
            cwd=target,
        )
        if not (isinstance(result, ExecResult) and result.exit_code == 0):
            return cls()
        dirs: list[str] = []
        files: list[str] = []
        for entry in result.stdout.split("\0"):
            if not entry:
                continue
            if entry.endswith("/"):
                dirs.append(entry.rstrip("/"))
            else:
                files.append(entry)
        return cls(tuple(dirs), tuple(files))


def build_exclude_flags(tool: str, ignored: IgnoredPaths) -> list[str]:
    """tool-specific CLI flags that make `tool` skip `ignored`'s paths.

    Args:
        tool: The tool the flags are for.
        ignored: The paths to exclude, relative to the repository root.

    Returns:
        The flags to append to the tool's arguments, or an empty list.
    """
    if tool == "trivy":
        flags: list[str] = []
        for directory in ignored.dirs:
            flags += ["--skip-dirs", directory]
        for path in ignored.files:
            flags += ["--skip-files", path]
        return flags
    if tool in ("syft", "grype"):
        # grype reuses syft's directory-source exclusion, so the dialect matches:
        # patterns anchor to the scan root and must begin with "./".
        flags = []
        for directory in ignored.dirs:
            flags += ["--exclude", f"./{directory}/**"]
        for path in ignored.files:
            flags += ["--exclude", f"./{path}"]
        return flags
    if tool == "cdxgen":
        # cdxgen globs run with nodir:true, so a directory is excluded by matching
        # the files under it ("<dir>/**"); patterns resolve against the scan root.
        flags = []
        for directory in ignored.dirs:
            flags += ["--exclude", f"{directory}/**"]
        for path in ignored.files:
            flags += ["--exclude", path]
        return flags
    return []
