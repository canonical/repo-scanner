# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the image identity cache (repo_scanner.image.cache)."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from repo_scanner.image import cache
from repo_scanner.paths import image_cache


@contextmanager
def _isolated() -> Iterator[None]:
    saved = os.environ.get("XDG_DATA_HOME")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_DATA_HOME"] = tmp
        try:
            yield
        finally:
            if saved is None:
                os.environ.pop("XDG_DATA_HOME", None)
            else:
                os.environ["XDG_DATA_HOME"] = saved


def test_records_and_reads_back_identities() -> None:
    with _isolated():
        assert cache.recorded("reposcan:x") is None  # nothing recorded yet
        cache.record("reposcan:x", "sha256:abc")
        cache.record("reposcan:y", "sha256:def")  # a second entry coexists
        assert cache.recorded("reposcan:x") == "sha256:abc"
        assert cache.recorded("reposcan:y") == "sha256:def"


def test_a_malformed_cache_reads_as_empty() -> None:
    with _isolated():
        path = image_cache()
        path.parent.mkdir(parents=True)
        path.write_text("{ not json")
        assert cache.recorded("reposcan:x") is None  # ignored, not fatal
