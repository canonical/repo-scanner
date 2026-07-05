"""Choose the execution context to run in."""

from repo_scanner.execution.context import ExecutionContext, Failure
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.lxd import LxdContext

_DEFAULT_CTX_PRECEDENCE = {
    "lxd": LxdContext,
    "docker": DockerContext,
    "local": LocalContext,
}


def select_context(backend: str) -> ExecutionContext | Failure:
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
