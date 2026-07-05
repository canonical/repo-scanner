"""Choose the execution context to run in."""

from repo_scanner.execution.context import ExecutionContext, Failure
from repo_scanner.execution.local import LocalContext


def select_context(backend: str) -> ExecutionContext | Failure:
    if backend in ("auto", "local"):
        context = LocalContext()
        availability = context.availability()
        if not availability.ok:
            return Failure(
                reason=f"{context.name} backend unavailable: {availability.reason}"
            )
        return context
    return Failure(reason=f"unknown backend: {backend}")
