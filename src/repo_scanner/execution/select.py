"""Choose the execution context to run in, honoring backend precedence."""

import os

from repo_scanner import config
from repo_scanner.execution.context import ExecutionContext, Failure
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.lxd import LxdContext

_DEFAULT_CTX_PRECEDENCE = {
    "lxd": LxdContext,
    "docker": DockerContext,
    "local": LocalContext,
}

# Values accepted for --backend and the `backend` config key.
BACKENDS = ("auto", *_DEFAULT_CTX_PRECEDENCE)


def select_context(requested_backend: str | None) -> ExecutionContext | Failure:
    """Choose an execution context. `requested_backend` is the command-line choice,
    or None to fall back to $REPOSCAN_BACKEND, then the saved config, then 'auto'.
    'auto' returns the first available of lxd, docker, then local."""
    backend = requested_backend or os.environ.get("REPOSCAN_BACKEND")
    if not backend:
        saved = config.load().get("backend")
        backend = saved if isinstance(saved, str) else "auto"

    if backend != "auto" and backend not in _DEFAULT_CTX_PRECEDENCE:
        return Failure(reason=f"unknown backend {backend}")

    for name, ctx_type in _DEFAULT_CTX_PRECEDENCE.items():
        if not (backend == name or backend == "auto"):
            continue

        ctx = ctx_type()
        availability = ctx.availability()
        if availability.ok:
            return ctx

        if backend == name:
            return Failure(
                f"selected backend ({name}) not available: {availability.reason}"
            )

    return Failure(reason="no execution backend is available")
