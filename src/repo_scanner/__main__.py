"""Enables `python -m repo_scanner`."""

import sys

from repo_scanner.cli import main

if __name__ == "__main__":
    sys.exit(main())
