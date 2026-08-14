# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Dependency resolution: generate lockfiles so scanners see transitive deps.

`resolve_dependencies` is the entry point; each ecosystem is a `Resolver` in its own
module (see `core` for the registry).
"""

from repo_scanner.scans.resolve.core import resolve_dependencies
from repo_scanner.scans.resolve.resolver import Resolver

__all__ = ["Resolver", "resolve_dependencies"]
