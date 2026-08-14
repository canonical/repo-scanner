# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI option specifications."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from repo_scanner.backends import BACKEND_NAMES
from repo_scanner.execution.context import SCAN_UID
from repo_scanner.scans import output

# --verbosity choices, mapped to their logging levels. "info" is the default.
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# Option values, keyed by dest, threaded down the tree.
Values = dict[str, Any]


@dataclass(frozen=True)
class Option:
    """One CLI parameter (flagged or positional).

    For an option, `flags` are the dash-prefixed names (e.g. ("--backend",)) and
    `dest` is the value's key. For a positional, `flags` is a one-tuple whose sole
    entry is both the displayed name and the dest (argparse derives a positional's
    dest from its name, so they must match), `positional` is True, and `remainder`
    or `nargs` selects its arity.

    Attributes:
        flags: The names argparse registers. For an option, dash-prefixed; for a
            positional, a single name.
        dest: The key this option's value is stored under (and read by `run`).
        default: The value when the option is omitted.
        choices: The allowed values, or None for any.
        type: A converter for the raw string (e.g. int), or None for a string.
        help: The option's help text.
        metavar: The placeholder shown in usage, or None for argparse's default.
        store_true: When True, the option is a flag (no value) defaulting False.
        positional: When True, this is a positional argument, not an option.
        nargs: "*" or "?" for a positional that takes many/optional values.
        remainder: When True (with `positional`), uses argparse.REMAINDER,
            capturing everything from the first non-option token (the
            `exec`/`invoke` passthrough).
    """

    flags: tuple[str, ...]
    dest: str
    default: object = None
    choices: tuple[str, ...] | None = None
    type: Callable[[str], object] | None = None
    help: str = ""
    metavar: str | None = None
    store_true: bool = False
    positional: bool = False
    nargs: str | None = None
    remainder: bool = False


# shared report-formatting options
REPORT_FORMAT_OPTIONS: tuple[Option, ...] = (
    Option(
        ("-f", "--format"),
        "format",
        default=None,
        choices=tuple(f.value for f in output.Format),
        help=f"Output format: {[f.value for f in output.Format]}.",
    ),
    Option(
        ("-n", "--limit"),
        "limit",
        default=output.DEFAULT_ROW_LIMIT,
        type=int,
        metavar="N",
        help=f"Maximum rows shown in the table (default: {output.DEFAULT_ROW_LIMIT}).",
    ),
    Option(
        ("--wrap",),
        "wrap",
        store_true=True,
        help="Wrap long table cells across multiple lines instead of truncating.",
    ),
)


GLOBAL_OPTIONS: tuple[Option, ...] = (
    Option(
        ("-v", "--verbosity"),
        "verbosity",
        default="info",
        choices=tuple(LOG_LEVELS),
        help="Lowest log level written to stderr (default: info).",
    ),
    Option(
        ("--backend",),
        "backend",
        default=None,
        choices=BACKEND_NAMES,
        help="Execution backend to run in. Overrides $REPOSCAN_BACKEND and the "
        "saved config; if unset, falls back to those, then to auto.",
    ),
    Option(
        ("--uid",),
        "uid",
        default=SCAN_UID,
        type=int,
        metavar="UID",
        help="UID for all in-backend processes. Ignored by the local backend.",
    ),
)
