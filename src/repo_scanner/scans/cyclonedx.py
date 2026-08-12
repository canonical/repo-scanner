# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Parse and merge CycloneDX SBOM documents.

An SBOM lists a repository's software components. SBOM tools each emit CycloneDX
JSON; these helpers merge several into one deduped inventory, annotating each
component with which scanners reported it (via CycloneDX `properties`).
"""

import copy
import json
from dataclasses import dataclass
from typing import Any, ClassVar

from repo_scanner.scans.model import ArtifactKind

# The property name carrying each contributing scanner on a merged component.
SCANNER_PROPERTY = "reposcan:scanner"


def parse(text: str) -> "CycloneDxDocument | None":
    """The CycloneDX document a tool printed, or None if `text` is not one.

    Args:
        text: A tool's stdout, expected to be a CycloneDX JSON document.

    Returns:
        A CycloneDxDocument if `text` is a CycloneDX JSON object, else None.
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(document, dict) and document.get("bomFormat") == "CycloneDX":
        return CycloneDxDocument(document)
    return None


def _component_key(component: dict[str, Any]) -> str:
    """A dedup key for a component: its package URL, else type/name/version."""
    purl = component.get("purl")
    if purl:
        return f"purl:{purl}"
    type_ = component.get("type", "")
    name = component.get("name", "")
    version = component.get("version", "")
    return f"nv:{type_}:{name}:{version}"


def _record_scanner(component: dict[str, Any], scanner: str) -> None:
    """Add `scanner` to the component's properties (no duplicates)."""
    properties = component.setdefault("properties", [])
    for existing in properties:
        if (
            existing.get("name") == SCANNER_PROPERTY
            and existing.get("value") == scanner
        ):
            return
    properties.append({"name": SCANNER_PROPERTY, "value": scanner})


def merge(sources: list[tuple[str, "CycloneDxDocument"]]) -> "CycloneDxDocument":
    """Merge CycloneDX documents from several scanners into one deduped SBOM.

    Components with the same package URL (or type/name/version) are merged into
    one, each annotated with a `reposcan:scanner` property per contributing tool.

    Args:
        sources: (scanner_name, CycloneDxDocument) pairs.

    Returns:
        A single CycloneDxDocument (CycloneDX 1.5).
    """
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for scanner, document in sources:
        for component in document.components():
            key = _component_key(component)
            if key in by_key:
                _record_scanner(by_key[key], scanner)
                continue
            copied = copy.deepcopy(component)
            _record_scanner(copied, scanner)
            by_key[key] = copied
            order.append(key)
    return CycloneDxDocument(
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [by_key[key] for key in order],
        }
    )


@dataclass(frozen=True)
class CycloneDxDocument:
    """A CycloneDX SBOM artifact (an Artifact of kind CYCLONEDX).

    Wraps the rendered CycloneDX `content` (a tool's output, or a `merge`).
    """

    kind: ClassVar[ArtifactKind] = ArtifactKind.CYCLONEDX
    content: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """The artifact as a CycloneDX document object."""
        return self.content

    def components(self) -> list[dict[str, Any]]:
        """Every component object the SBOM lists."""
        return self.content.get("components", [])

    def count(self) -> int:
        """The number of components the SBOM lists."""
        return len(self.components())

    def rows(self) -> tuple[list[str], list[list[str]]]:
        """A table of components: name, version, and type."""
        headers = ["COMPONENT", "VERSION", "TYPE"]
        rows = [
            [
                str(component.get("name", "")),
                str(component.get("version", "")),
                str(component.get("type", "")),
            ]
            for component in self.components()
        ]
        return headers, rows
