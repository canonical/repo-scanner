# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Resolve transitive dependencies before an SBOM/SCA scan.

The SBOM/SCA tools report a full transitive dependency tree only from a committed
lockfile. When the scan has network access, this pre-step runs a package resolver to
generate one. The repo is mounted read-only, so the resolver runs against a writable
copy of it, which becomes the scan target. It is best-effort: any failure (no
network, an unsatisfiable resolve, a missing resolver) leaves the target unchanged.

Python is resolved with `uv pip compile`, wheel-only by default so no source is built
and no untrusted code runs. `--only-binary :all:` is all-or-nothing, though: one
sdist-only dependency makes the whole resolve fail, so when it fails and
`allow_code_execution` is set the resolve is retried allowing source builds. See
docs/sbom-dependency-detection.md.
"""

import logging
import os

from repo_scanner.execution.context import SCAN_UID, ExecutionContext
from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.tools.registry import UV, UV_PYTHON_SUBDIR

logger = logging.getLogger(__name__)

# The pinned requirements file the Python resolver writes. A `*requirements*.txt` name
# so the catalogers pick it up, but distinct so it never clobbers a repo file.
_PY_LOCK = "reposcan-resolved.requirements.txt"


def resolve_dependencies(
    ctx: ExecutionContext,
    target: str,
    tool_root: str,
    resolved_parent: str,
    *,
    uid: int = SCAN_UID,
    allow_code_execution: bool = False,
) -> str:
    """Generate lockfiles for `target` so scanners catalog transitive deps.

    Copies `target` into a writable working directory, resolves each ecosystem into
    it, and returns that directory as the new scan target. Returns `target` unchanged
    when there is nothing to resolve or the copy fails.

    Args:
        ctx: The started context to run the resolvers in.
        target: The (read-only) repository path as seen in the context.
        tool_root: Where the tools are installed in the context.
        resolved_parent: The directory to copy the repo under (from the backend).
        uid: The user id the resolvers run as.
        allow_code_execution: Permit building source distributions to resolve
            sdist-only Python packages (runs untrusted code).

    Returns:
        The directory the scan should target.
    """
    if not _has_file(ctx, f"{target}/pyproject.toml", uid):
        return target  # nothing this batch knows how to resolve
    # Copy under `resolved_parent` keeping the repo's own name, so scan-output
    # locations read as "<repo>/..." rather than a scratch-dir name.
    dest = f"{resolved_parent}/{os.path.basename(target.rstrip('/'))}"
    if not _copy_repo(ctx, target, dest, uid):
        return target
    _resolve_python(ctx, dest, tool_root, uid, allow_code_execution)
    return dest


def _has_file(ctx: ExecutionContext, path: str, uid: int) -> bool:
    return _ok(ctx.run(["test", "-f", path], uid=uid))


def _copy_repo(ctx: ExecutionContext, target: str, dest: str, uid: int) -> bool:
    # Ensure the parent exists (the local cache dir may not yet) and clear any stale
    # copy (that cache persists across runs, unlike an ephemeral container).
    ctx.run(["mkdir", "-p", os.path.dirname(dest)], uid=uid)
    ctx.run(["rm", "-rf", dest], uid=uid)
    if _ok(ctx.run(["cp", "-a", target, dest], uid=uid)):
        return True
    logger.warning("dependency resolution skipped: could not copy the repository")
    return False


def _resolve_python(
    ctx: ExecutionContext,
    workdir: str,
    tool_root: str,
    uid: int,
    allow_code_execution: bool,
) -> None:
    compile_cmd = [
        UV.installed_path(tool_root),
        "pip",
        "compile",
        "pyproject.toml",
        "-o",
        _PY_LOCK,
        "--no-header",
    ]
    # Point uv at the managed Python baked under the install root; as the scan user it
    # has no Python of its own and would otherwise try to fetch one at scan time.
    env = {"UV_PYTHON_INSTALL_DIR": f"{tool_root}/{UV_PYTHON_SUBDIR}"}
    wheel_only = [*compile_cmd, "--only-binary", ":all:"]
    logger.info("detected python; running: %s", " ".join(wheel_only))
    result = ctx.run(wheel_only, cwd=workdir, env=env, uid=uid)
    if _ok(result):
        logger.info("resolved python dependencies (wheel-only)")
        return
    if allow_code_execution:
        # Retry allowing source builds so sdist-only packages resolve (runs code).
        logger.info(
            "retrying python resolution with source builds: %s", " ".join(compile_cmd)
        )
        result = ctx.run(compile_cmd, cwd=workdir, env=env, uid=uid)
        if _ok(result):
            logger.info("resolved python dependencies (with source builds)")
            return
    stderr = result.stderr.strip() if isinstance(result, ExecResult) else ""
    note = stderr.splitlines()[-1] if stderr else "resolver unavailable"
    logger.warning("python dependency resolution skipped: %s", note)


def _ok(result: ExecResult | Failure) -> bool:
    return isinstance(result, ExecResult) and result.exit_code == 0
