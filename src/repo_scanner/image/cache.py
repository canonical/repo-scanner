"""A persistent record of built images' real content identity, for verifying reuse.

An image is content-addressed by its BuildSpec (the reference/tag). But the reference
only says what should be in the image; this records the real identity captured at
build time -- the Docker image ID or the LXD fingerprint -- so a later run can confirm
the image currently present is the one we built before trusting and running it.

Stored as a JSON map of reference -> identity at $XDG_DATA_HOME/reposcan/images.json.
"""

import json
import logging

from repo_scanner.paths import image_cache

logger = logging.getLogger(__name__)


def _load() -> dict[str, str]:
    path = image_cache()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except OSError as exc:
        logger.warning("could not read image cache %s: %s", path, exc)
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("ignoring malformed image cache %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def recorded(reference: str) -> str | None:
    """The identity recorded when `reference` was last built, or None if never."""
    return _load().get(reference)


def record(reference: str, identity: str) -> None:
    """Remember that `reference` was built with content identity `identity`. A cache
    that cannot be written is a warning, not a failure: the image just gets rebuilt
    next time rather than reused."""
    data = _load()
    data[reference] = identity
    path = image_cache()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        logger.warning("could not write image cache %s: %s", path, exc)
