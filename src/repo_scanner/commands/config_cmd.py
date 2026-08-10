# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan config` command: read and write persistent configuration."""

import logging
import sys

from repo_scanner import config
from repo_scanner.backends import BACKEND_NAMES

logger = logging.getLogger(__name__)

# Config keys reposcan understands, with the values each accepts.
_ALLOWED_VALUES = {"backend": BACKEND_NAMES}


def set_value(key: str, value: str) -> int:
    """Validate and persist `key = value`. 0 on success, 2 for an invalid key or
    value, 1 if the config could not be written."""
    allowed = _ALLOWED_VALUES.get(key)
    if allowed is None:
        logger.error("unknown config key: %s", key)
        return 2
    if value not in allowed:
        logger.error(
            "invalid value for %s: %s (choose from %s)", key, value, ", ".join(allowed)
        )
        return 2
    settings = config.load()
    settings[key] = value
    error = config.save(settings)
    if error is not None:
        logger.error("%s", error.reason)
        return 1
    return 0


def get_value(key: str | None) -> int:
    """Print one config value, or all of them when `key` is None. 0 on success, 1 if
    the requested key is not set."""
    if key is not None and key not in _ALLOWED_VALUES:
        logger.error("config key '%s' is not known", key)
    settings = config.load()
    if key is None:
        for name, value in sorted(settings.items()):
            sys.stdout.write(f"{name} = {value}\n")
        return 0
    if key not in settings:
        logger.error("config key not set: %s", key)
        return 1
    sys.stdout.write(f"{settings[key]}\n")
    return 0
