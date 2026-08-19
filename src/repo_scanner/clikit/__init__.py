# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""clikit: a small, declarative command-line framework.

Declare commands as classes (`Action`/`Group`) with typed parameter attributes
(`option`/`flag`/`positional`/`remainder`), compose them into a `Cli`, and let the
engine parse argv, resolve each value (CLI > env > config > default), render help,
and dispatch. This package is the whole surface: consumers import from
`repo_scanner.clikit` and never reach into its internal modules.
"""

from repo_scanner.clikit.dispatch import configure_logging, dispatch
from repo_scanner.clikit.parse import parse
from repo_scanner.clikit.resolve import LOG_LEVELS, coerce, resolve
from repo_scanner.clikit.spec import (
    Action,
    Cli,
    Group,
    Param,
    check_requires,
    flag,
    option,
    params_of,
    positional,
    remainder,
)

__all__ = [
    "LOG_LEVELS",
    "Action",
    "Cli",
    "Group",
    "Param",
    "check_requires",
    "coerce",
    "configure_logging",
    "dispatch",
    "flag",
    "option",
    "params_of",
    "parse",
    "positional",
    "remainder",
    "resolve",
]
