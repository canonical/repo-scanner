# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Filesystem locations reposcan uses on the local host.

Config lives under $XDG_CONFIG_HOME (see config.py); installed tools live under
$XDG_DATA_HOME, following the same XDG convention.
"""

import os
from pathlib import Path


def _data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "reposcan"


def tools_root() -> Path:
    """Where `bootstrap` installs tools and `invoke`/`tools` look for them.

    $XDG_DATA_HOME/reposcan/tools (default ~/.local/share/reposcan/tools).
    """
    return _data_home() / "tools"


def image_cache() -> Path:
    """Where built images' verified identities are recorded (see image/cache.py).

    $XDG_DATA_HOME/reposcan/images.json.
    """
    return _data_home() / "images.json"
