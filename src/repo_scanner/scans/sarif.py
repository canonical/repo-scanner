# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Build minimal SARIF 2.1.0 documents from scan findings.

SARIF is the common output format for scans. A scan turns each tool finding into a
SarifResult and wraps them in a SarifDocument; `to_dict()` renders the JSON structure.
"""

import copy
import json
from dataclasses import dataclass
from typing import Any, ClassVar

from repo_scanner.scans.model import ArtifactKind

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def _result_key(result: dict[str, Any]) -> tuple[str, str, int]:
    """A dedup key for a SARIF result: its rule and primary location."""
    rule = str(result.get("ruleId", ""))
    locations = result.get("locations") or []
    physical = locations[0].get("physicalLocation", {}) if locations else {}
    uri = str(physical.get("artifactLocation", {}).get("uri", ""))
    line = physical.get("region", {}).get("startLine", 0)
    return (rule, uri, line if isinstance(line, int) else 0)


def _record_scanner(result: dict[str, Any], scanner: str) -> None:
    """Add `scanner` to the result's properties.scanners list (no duplicates)."""
    scanners = result.setdefault("properties", {}).setdefault("scanners", [])
    if scanner not in scanners:
        scanners.append(scanner)


def merge(sources: list[tuple[str, "SarifDocument"]]) -> "SarifDocument":
    """Merge SARIF documents from several scanners into one deduped document.

    Each result is annotated with a properties.scanners list naming the scanners
    that reported it; results with the same rule and primary location are merged
    into one (their scanner lists combined) rather than duplicated.

    Args:
        sources: (scanner_name, SarifDocument) pairs.

    Returns:
        A single SarifDocument under a "reposcan" driver.
    """
    by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    order: list[tuple[str, str, int]] = []
    for scanner, document in sources:
        for result in document.results():
            key = _result_key(result)
            if key in by_key:
                _record_scanner(by_key[key], scanner)
                continue
            copied = copy.deepcopy(result)
            _record_scanner(copied, scanner)
            by_key[key] = copied
            order.append(key)
    return SarifDocument(
        {
            "$schema": SCHEMA,
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "reposcan"}},
                    "results": [by_key[key] for key in order],
                }
            ],
        }
    )


def parse(text: str) -> "SarifDocument | None":
    """The SARIF document a tool printed, or None if `text` is not a SARIF document.

    Args:
        text: A tool's stdout, expected to be a SARIF JSON document.

    Returns:
        A SarifDocument if `text` is a JSON object with a `runs` list, else None.
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(document, dict) and isinstance(document.get("runs"), list):
        return SarifDocument(document)
    return None


@dataclass(frozen=True)
class SarifResult:
    """A single SARIF result for one finding.

    Attributes:
        rule_id: The rule that produced the finding (e.g. the detector name).
        message: A human-readable description of the finding.
        uri: The file the finding is in, relative to the scanned repository.
        start_line: The 1-based line of the finding, or 0 if unknown.
        level: The SARIF level ("error", "warning", "note").
    """

    rule_id: str
    message: str
    uri: str
    start_line: int
    level: str = "error"

    def to_dict(self) -> dict[str, Any]:
        """Render this result as a SARIF result object."""
        physical: dict[str, Any] = {"artifactLocation": {"uri": self.uri}}
        if self.start_line:
            physical["region"] = {"startLine": self.start_line}
        return {
            "ruleId": self.rule_id,
            "level": self.level,
            "message": {"text": self.message},
            "locations": [{"physicalLocation": physical}],
        }


@dataclass(frozen=True)
class SarifDocument:
    """A SARIF 2.1.0 document artifact.

    Wraps the rendered SARIF `content`. Build one from Result findings under a
    single tool driver with `from_results`, or from an already-rendered document
    (a tool's SARIF output, or a `merge`) with the plain constructor.
    """

    kind: ClassVar[ArtifactKind] = ArtifactKind.SARIF
    content: dict[str, Any]

    @classmethod
    def from_results(
        cls, driver_name: str, driver_version: str, results: list[SarifResult]
    ) -> "SarifDocument":
        """Build a document from findings under a single tool driver.

        Args:
            driver_name: The tool that produced the results.
            driver_version: The tool's version.
            results: The findings the run reports.

        Returns:
            The rendered SarifDocument.
        """
        driver = {"name": driver_name, "version": driver_version}
        content = {
            "$schema": SCHEMA,
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": driver},
                    "results": [result.to_dict() for result in results],
                }
            ],
        }
        return cls(content)

    def to_dict(self) -> dict[str, Any]:
        """The artifact as a SARIF 2.1.0 document object."""
        return self.content

    def results(self) -> list[dict[str, Any]]:
        """Every SARIF result object, flattened across all runs."""
        return [
            result
            for run in self.content.get("runs", [])
            for result in run.get("results", [])
        ]

    def count(self) -> int:
        """The number of findings across every run."""
        return len(self.results())
