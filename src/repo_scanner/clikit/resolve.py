# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Multi-source parameter resolution.

Every parameter resolves CLI > env > config > default. This module owns the
precedence merge (`resolve`) that converts and validates each value and logs an
override when sources disagree; the environment and the persisted config file (read
via `repo_scanner.ioutil.config`) are the lower sources it reads from.

Positionals and remainders are command-line only; value options and flags may also
be read from the environment (REPOSCAN_<NAME>) and, when marked, from config.
"""

import logging
import os
from collections.abc import Iterable, Mapping
from typing import Any

from repo_scanner.clikit.spec import Param
from repo_scanner.ioutil.config import load

logger = logging.getLogger(__name__)

# --verbosity choices, mapped to their logging levels ("info" is the default).
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


# --- value coercion ----------------------------------------------------------


def parse_bool(value: str) -> bool:
    """The boolean an env/config string denotes, or raise ValueError."""
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off", ""):
        return False
    raise ValueError(f"expected a boolean, got {value!r}")


# --- resolution --------------------------------------------------------------


def coerce(param: Param, raw: Any, source: str) -> tuple[Any, str | None]:
    """Convert and validate a raw value for `param`, or return (None, message).

    `source` is "cli", "env", or "config". A CLI flag arrives already boolean; every
    other raw value is a string converted via the parameter's `convert` (or
    parse_bool for a flag) and checked against `choices`.
    """
    if param.is_flag:
        if source == "cli":
            return bool(raw), None
        value, error = _run(parse_bool, raw, param)
        return value, error
    value: Any = raw
    if param.convert is not None:
        value, error = _run(param.convert, str(raw), param)
        if error is not None:
            return None, error
    if param.choices is not None and value not in param.choices:
        allowed = ", ".join(str(c) for c in param.choices)
        return None, f"invalid value for {param.name}: {value} (choose from {allowed})"
    return value, None


def _run(convert, raw: str, param: Param) -> tuple[Any, str | None]:
    try:
        return convert(raw), None
    except (ValueError, TypeError) as exc:
        return None, f"invalid value for {param.name}: {exc}"


def resolve(
    params: Iterable[Param],
    raw: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Resolve each parameter to a value, or return ({}, first error message).

    Args:
        params: The in-scope parameters to resolve.
        raw: The values parsed from the command line, keyed by name (a string for a
            value option or single positional, True for a flag, a list for a
            remainder or a `many` positional).
        env: The environment mapping (defaults to os.environ).
        config: The config mapping (defaults to `load()`).

    Returns:
        A dict of name -> resolved value, or ({}, message) on the first bad value.
        A CLI value that overrides a differing env/config value is logged.
    """
    environ = os.environ if env is None else env
    saved = load() if config is None else config
    out: dict[str, Any] = {}
    for param in params:
        value, error = _resolve_one(param, raw, environ, saved)
        if error is not None:
            return {}, error
        out[param.name] = value
    return out, None


def _resolve_one(
    param: Param,
    raw: Mapping[str, Any],
    env: Mapping[str, str],
    saved: Mapping[str, Any],
) -> tuple[Any, str | None]:
    # Positionals and remainders are command-line only.
    if param.positional or param.remainder:
        if param.name not in raw:
            return _default(param)
        return _positional_value(param, raw[param.name])

    found: list[tuple[str, Any]] = []
    if param.name in raw:
        value, error = coerce(param, raw[param.name], "cli")
        if error is not None:
            return None, error
        found.append(("cli", value))
    if param.env and env.get(param.env_var) is not None:
        value, error = coerce(param, env[param.env_var], "env")
        if error is not None:
            return None, error
        found.append(("env", value))
    if param.config and saved.get(param.name) is not None:
        value, error = coerce(param, saved[param.name], "config")
        if error is not None:
            return None, error
        found.append(("config", value))
    if not found:
        return _default(param)
    winner_source, winner_value = found[0]
    for source, value in found[1:]:
        if value != winner_value:
            logger.info("%s overrode %s for %s", winner_source, source, param.name)
    return winner_value, None


def _positional_value(param: Param, raw: Any) -> tuple[Any, str | None]:
    """Convert/validate a positional or remainder's raw command-line value."""
    if param.remainder:
        return list(raw), None
    if param.many:
        out = []
        for item in raw:
            value, error = coerce(param, item, "cli")
            if error is not None:
                return None, error
            out.append(value)
        return out, None
    return coerce(param, raw, "cli")


def _default(param: Param) -> tuple[Any, None]:
    if param.remainder or param.many:
        return list(param.default or []), None
    return param.default, None
