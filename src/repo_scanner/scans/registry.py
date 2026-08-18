# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `scan` command group.

Imported and added to the app's command tree by `app.py`.
"""

from repo_scanner.clikit import Group
from repo_scanner.scans.iac import IacScan
from repo_scanner.scans.sast import SastScan
from repo_scanner.scans.sbom import SbomScan
from repo_scanner.scans.sca import ScaScan
from repo_scanner.scans.secrets import SecretsScan
from repo_scanner.scans.workflow import WorkflowScan


class ScanGroup(Group):
    name = "scan"
    help = "Scan a repository."
    subcommands = (SecretsScan, SastScan, IacScan, WorkflowScan, ScaScan, SbomScan)
