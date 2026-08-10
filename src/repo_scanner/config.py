# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Persistent user configuration, stored as JSON.

Located at $XDG_CONFIG_HOME/reposcan/config.json (default
~/.config/reposcan/config.json), read and written with the stdlib json module.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from repo_scanner.execution.process import Failure

logger = logging.getLogger(__name__)


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "reposcan" / "config.json"


def load() -> dict[str, Any]:
    """The saved config, or {} if there is none. A missing file is empty; a
    malformed one is ignored with a warning rather than failing the command."""
    path = config_path()
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        logger.warning("could not read config %s: %s", path, exc)
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("ignoring malformed config %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save(settings: dict[str, Any]) -> Failure | None:
    """Write `settings` as JSON, creating the parent directory. None on success, or
    a Failure if it could not be written."""
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        return Failure(reason=f"could not write config {path}: {exc}")
    return None
