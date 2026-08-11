# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The scan registry: every scan type, keyed by name.

The CLI builds a `scan <name>` subcommand for each entry from the scan's declared
`summary` and `parameters`, and constructs it from the parsed arguments.
"""

from repo_scanner.scans.iac import IacScan
from repo_scanner.scans.model import Scan
from repo_scanner.scans.sast import SastScan
from repo_scanner.scans.sbom import SbomScan
from repo_scanner.scans.sca import ScaScan
from repo_scanner.scans.secrets import SecretsScan
from repo_scanner.scans.workflow import WorkflowScan

SCANS: dict[str, type[Scan]] = {
    scan.name: scan
    for scan in (SecretsScan, SastScan, IacScan, WorkflowScan, ScaScan, SbomScan)
}
