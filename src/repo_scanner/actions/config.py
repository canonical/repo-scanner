# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan config` action: read and write persistent configuration."""

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from repo_scanner import config
from repo_scanner.backends import BACKEND_NAMES

logger = logging.getLogger(__name__)


# ConfigValidator: accepts a string and returns an error message, or None if okay.
ConfigValidator = Callable[[str], str | None]


def _validate_image(value: str) -> str | None:
    """None if `value` is a usable image reference, else an error message.

    Any non-empty reference is accepted (the 'canonical' shorthand, or a full OCI
    ref); whether it can actually be pulled is decided when it is used.
    """
    if value.strip():
        return None
    return "invalid value for image: give an image reference or 'canonical'"


@dataclass(frozen=True)
class ConfigKey:
    """A supported config key, declared as data.

    Attributes:
        name: The config key.
        summary: A short description of what its value means.
        choices: The allowed values when the key is limited to an enum, or None
            for a free-form key whose values are checked by `validator`.
        validator: Validates a free-form value; unused when `choices` is set.
    """

    name: str
    summary: str
    choices: tuple[str, ...] | None = None
    validator: ConfigValidator | None = None

    def validate(self, value: str) -> str | None:
        """None if `value` is allowed for this key, else an error message.

        Args:
            value: The candidate value.

        Returns:
            None when the value is allowed, else a message naming the problem
            (and the choices, for an enum key).
        """
        if self.choices is not None:
            if value in self.choices:
                return None
            options = ", ".join(self.choices)
            return f"invalid value for {self.name}: {value} (choose from {options})"
        if self.validator is not None:
            return self.validator(value)
        return None


# The supported config keys, keyed by name.
_KEYS: dict[str, ConfigKey] = {
    "backend": ConfigKey(
        "backend",
        "The execution backend tools run in.",
        choices=BACKEND_NAMES,
    ),
    "image": ConfigKey(
        "image",
        "The tool image to run: an OCI reference, or the 'canonical' shorthand.",
        validator=_validate_image,
    ),
}


def set_value(key: str, value: str) -> int:
    """Validate and persist `key = value`.

    Returns:
        0 on success, 2 for an invalid key or value, 1 if the config could not
        be written.
    """
    config_key = _KEYS.get(key)
    if config_key is None:
        logger.error("unknown config key: %s", key)
        return 2
    error = config_key.validate(value)
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
    if key is not None and key not in _KEYS:
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


def list_keys() -> int:
    """Print every supported config key and its description.

    Returns:
        0.
    """
    for name, config_key in sorted(_KEYS.items()):
        sys.stdout.write(f"{name} - {config_key.summary}\n")
    return 0


def list_options(key: str) -> int:
    """Print the supported values for `key`.

    For a key limited to an enum, prints each allowed value, one per line. For a
    free-form key, prints a note that any value is accepted, with its description.

    Args:
        key: The config key to describe.

    Returns:
        0 on success, 2 for an unknown key.
    """
    config_key = _KEYS.get(key)
    if config_key is None:
        logger.error("unknown config key: %s", key)
        return 2
    if config_key.choices is not None:
        for choice in config_key.choices:
            sys.stdout.write(f"{choice}\n")
        return 0
    sys.stdout.write(f"{key} accepts any value: {config_key.summary}\n")
    return 0
