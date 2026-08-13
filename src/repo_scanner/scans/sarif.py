# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Build minimal SARIF 2.1.0 documents from scan findings.

SARIF is the common output format for scans. A scan turns each tool finding into a
SarifResult and wraps them in a SarifDocument; `to_dict()` renders the JSON structure.
"""

import copy
import json
import shlex
from dataclasses import dataclass
from typing import Any, ClassVar

from repo_scanner.scans.model import ArtifactKind, Table, ToolInvocationRecord

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
    into one (their scanner lists combined) rather than duplicated. The original
    rules for each result are carried onto the merged driver, so their metadata
    is not lost.

    Args:
        sources: (scanner_name, SarifDocument) pairs.

    Returns:
        A single SarifDocument under a "reposcan" driver.
    """
    by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    order: list[tuple[str, str, int]] = []
    rules_by_id: dict[str, dict[str, Any]] = {}
    for scanner, document in sources:
        for run in document.to_dict().get("runs", []):
            for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
                rule_id = str(rule.get("id", ""))
                if rule_id and rule_id not in rules_by_id:
                    rules_by_id[rule_id] = rule
            for result in run.get("results", []):
                key = _result_key(result)
                if key in by_key:
                    _record_scanner(by_key[key], scanner)
                    continue
                copied = copy.deepcopy(result)
                # ruleIndex points into one run's rule list; results also reference
                # rules by id, so drop the now-meaningless index after combining runs.
                copied.pop("ruleIndex", None)
                _record_scanner(copied, scanner)
                by_key[key] = copied
                order.append(key)
    results = [by_key[key] for key in order]
    referenced = {str(result.get("ruleId", "")) for result in results}
    rules = [rules_by_id[rule_id] for rule_id in rules_by_id if rule_id in referenced]
    driver: dict[str, Any] = {"name": "reposcan"}
    if rules:
        driver["rules"] = rules
    return SarifDocument(
        {
            "$schema": SCHEMA,
            "version": "2.1.0",
            "runs": [{"tool": {"driver": driver}, "results": results}],
        }
    )


def parse(text: str) -> "SarifDocument | None":
    """The SARIF document a tool printed, or None if `text` is not a SARIF document.

    Each result's effective level is standardized onto the result at ingestion (see
    `_standardize_levels`), so downstream the level always lives in one place.

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
        _standardize_levels(document)
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
        level: The SARIF level ("error", "warning", "note"); defaults to the SARIF
            default of "warning" when a finding's severity is not set.
    """

    rule_id: str
    message: str
    uri: str
    start_line: int
    level: str = "warning"

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

    def rows(self) -> tuple[list[str], list[list[str]]]:
        """A table of findings, most severe first: level, rule, location, message.

        A result's level is standardized onto it at ingestion (see
        `_standardize_levels`); the default guards results built another way.
        """
        headers = ["LEVEL", "RULE", "LOCATION", "MESSAGE"]
        findings = [
            [
                str(result.get("level") or "warning"),
                str(result.get("ruleId", "")),
                _location(result),
                str(result.get("message", {}).get("text", "")),
            ]
            for result in self.results()
        ]
        findings.sort(key=lambda finding: _level_rank(finding[0]))
        return headers, findings

    def records(self) -> Table:
        """The findings as a `findings` table for querying and reconstruction.

        Parsed columns (location split into `uri`/`line`, the merge's
        `properties.scanners`) plus `run` (the result's run index) and `document` (the
        result's raw JSON, so a single finding reconstructs). In document order.
        """
        columns = (
            "rule",
            "level",
            "uri",
            "line",
            "message",
            "scanners",
            "run",
            "document",
        )
        findings = []
        for index, run in enumerate(self.content.get("runs", [])):
            for result in run.get("results", []):
                physical = _physical(result)
                line = physical.get("region", {}).get("startLine")
                findings.append(
                    (
                        str(result.get("ruleId", "")),
                        str(result.get("level") or "warning"),
                        str(physical.get("artifactLocation", {}).get("uri", "")),
                        str(line) if line else "",
                        str(result.get("message", {}).get("text", "")),
                        ",".join(result.get("properties", {}).get("scanners", [])),
                        str(index),
                        json.dumps(result),
                    )
                )
        return Table("findings", columns, findings)

    def record_invocations(self, invocations: list[ToolInvocationRecord]) -> None:
        """Record each executed tool command under the run's SARIF `invocations`.

        All tools merge into one run, so they share its `invocations` array; each
        tool is identified by its `executableLocation` and a `tool` property.
        """
        runs = self.content.get("runs")
        if not invocations or not runs:
            return
        runs[0]["invocations"] = [_invocation_object(inv) for inv in invocations]


# SARIF severity levels from most to least severe; unlisted levels sort last.
_LEVEL_RANK = {"error": 0, "warning": 1, "note": 2, "none": 3}


def _level_rank(level: str) -> int:
    """The sort rank of a SARIF level: lower is more severe, so it sorts first."""
    return _LEVEL_RANK.get(level, len(_LEVEL_RANK))


def _rule_levels(run: dict[str, Any]) -> dict[str, str]:
    """Each rule id mapped to its configured level, from a run's tool driver rules."""
    levels: dict[str, str] = {}
    for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
        rule_id = str(rule.get("id", ""))
        level = rule.get("defaultConfiguration", {}).get("level")
        if rule_id and level:
            levels[rule_id] = str(level)
    return levels


def _standardize_levels(document: dict[str, Any]) -> None:
    """Set each result's effective SARIF level explicitly on the result, in place.

    A result may carry its level directly (zizmor, our own findings) or inherit it
    from the rule's configuration (semgrep); one with neither takes the SARIF default
    of "warning". Resolving it once here keeps the level in one place -- on the
    result -- for every reader, and it survives a later merge unchanged.
    """
    for run in document.get("runs", []):
        rule_levels = _rule_levels(run)
        for result in run.get("results", []):
            if not result.get("level"):
                result["level"] = rule_levels.get(
                    str(result.get("ruleId", "")), "warning"
                )


def _invocation_object(inv: ToolInvocationRecord) -> dict[str, Any]:
    """A SARIF invocation object for one executed tool command."""
    invocation: dict[str, Any] = {
        "commandLine": shlex.join(inv.command),
        "arguments": list(inv.command[1:]),
        "executableLocation": {"uri": inv.command[0]},
        "workingDirectory": {"uri": inv.working_directory},
        "exitCode": inv.exit_code,
        "executionSuccessful": inv.successful,
        "properties": {"tool": inv.tool, "version": inv.version},
    }
    if inv.environment:
        invocation["environmentVariables"] = dict(inv.environment)
    return invocation


def _physical(result: dict[str, Any]) -> dict[str, Any]:
    """A result's primary physicalLocation object, or an empty dict if it has none."""
    locations = result.get("locations") or []
    return locations[0].get("physicalLocation", {}) if locations else {}


def _location(result: dict[str, Any]) -> str:
    """The 'uri:line' of a result's primary location, or '' if it has none."""
    physical = _physical(result)
    uri = str(physical.get("artifactLocation", {}).get("uri", ""))
    line = physical.get("region", {}).get("startLine")
    return f"{uri}:{line}" if line else uri
