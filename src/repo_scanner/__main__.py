# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Enables `python -m repo_scanner`."""

import sys

from repo_scanner.app import main

if __name__ == "__main__":
    sys.exit(main())
