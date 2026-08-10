# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan config` command: read and write persistent configuration."""

import logging
import sys
from collections.abc import Callable

from repo_scanner import config
from repo_scanner.backends import BACKEND_NAMES

logger = logging.getLogger(__name__)


def _validate_backend(value: str) -> str | None:
    """None if `value` is an accepted backend, else an error message."""
    if value in BACKEND_NAMES:
        return None
    choices = ", ".join(BACKEND_NAMES)
    return f"invalid value for backend: {value} (choose from {choices})"


def _validate_image(value: str) -> str | None:
    """Validate image reference.

    Any non-empty reference is accepted (the 'canonical' shorthand, or a full OCI
    ref); whether it can actually be pulled is decided when it is used.

    Returns:
        None if `value` is a usable image reference, else an error message.
    """
    if value.strip():
        return None
    return "invalid value for image: give an image reference or 'canonical'"


# ConfigValidator: accepts a string and returns an error message or None if okay
ConfigValidator = Callable[[str], str | None]

# known config keys, each with a validator for its value.
_VALIDATORS: dict[str, ConfigValidator] = {
    "backend": _validate_backend,
    "image": _validate_image,
}


def set_value(key: str, value: str) -> int:
    """Validate and persist `key = value`.

    Returns:
        0 on success, 2 for an invalid key or value, 1 if the config could not
        be written.
    """
    validate = _VALIDATORS.get(key)
    if validate is None:
        logger.error("unknown config key: %s", key)
        return 2
    error = validate(value)
    if error is not None:
        logger.error("%s", error)
        return 2
    settings = config.load()
    settings[key] = value
    error = config.save(settings)
    if error is not None:
        logger.error("%s", error.reason)
        return 1
    return 0


def unset_value(key: str) -> int:
    """Remove `key` from the persisted config.

    Returns:
        0 on success, including when it was not set (the key is absent either
        way); 2 for an unknown key, 1 if the config could not be written.
    """
    settings = config.load()
    if key not in settings:
        logger.info("config key not set: %s", key)
        return 0
    del settings[key]
    error = config.save(settings)
    if error is not None:
        logger.error("%s", error.reason)
        return 1
    return 0


def get_value(key: str | None) -> int:
    """Print one config value, or all of them when `key` is None.

    Returns:
        0 on success, 1 if the requested key is not set.
    """
    if key is not None and key not in _VALIDATORS:
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
