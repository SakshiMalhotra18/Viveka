"""
Persistence store for VIVEKA Phase 5 properties.

Stores and manages properties in `.viveka/properties/` as individual YAML files.
This provides git-friendly diffs, versioning, audit tracking, and human editability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.properties.models import Property, PropertyCatalog, PropertyRevisionRecord
from viveka.properties.vocabulary import PropertyStatus


class PropertyNotFoundError(VivekaError):
    """Raised when a requested property ID or name is not found."""


class PropertyStore:
    """Manages reading, writing, approving, and rejecting properties on disk."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.properties_dir = self.project_root / ".viveka" / "properties"

    def ensure_dir(self) -> Path:
        """Ensure the `.viveka/properties/` directory exists."""
        self.properties_dir.mkdir(parents=True, exist_ok=True)
        return self.properties_dir

    def property_path(self, property_id: str) -> Path:
        """Return the expected YAML file path for a property ID."""
        return self.properties_dir / f"{property_id}.yaml"

    def load_catalog(self) -> PropertyCatalog:
        """Load all properties currently stored in `.viveka/properties/`."""
        if not self.properties_dir.is_dir():
            return PropertyCatalog(properties=[])

        props: list[Property] = []
        for yaml_file in sorted(self.properties_dir.glob("*.yaml")):
            try:
                raw_text = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(raw_text)
                if isinstance(data, dict) and "id" in data:
                    prop = Property.model_validate(data)
                    props.append(prop)
            except Exception:
                # Corrupted or malformed file skipped gracefully
                continue

        return PropertyCatalog(properties=props)

    def get(self, identifier: str) -> Property | None:
        """Look up a property by exact ID or name slug."""
        catalog = self.load_catalog()
        prop = catalog.by_id(identifier)
        if prop is not None:
            return prop
        for p in catalog.properties:
            if p.name == identifier:
                return p
        return None

    def save(self, prop: Property) -> Path:
        """Save a property model to disk as a YAML file."""
        self.ensure_dir()
        path = self.property_path(prop.id)
        dumped = prop.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def approve(self, identifier: str) -> Property:
        """Mark a property as approved and record revision history."""
        prop = self.get(identifier)
        if prop is None:
            raise PropertyNotFoundError(f"Property not found: {identifier}")

        now = datetime.now(UTC)
        prop.revision += 1
        prop.status = PropertyStatus.APPROVED
        prop.updated_at = now
        prop.revision_history.append(
            PropertyRevisionRecord(
                revision=prop.revision,
                status=PropertyStatus.APPROVED,
                timestamp=now,
                reason="Approved by developer",
                actor="developer",
            )
        )
        self.save(prop)
        return prop

    def reject(self, identifier: str) -> Property:
        """Mark a property as rejected and record revision history."""
        prop = self.get(identifier)
        if prop is None:
            raise PropertyNotFoundError(f"Property not found: {identifier}")

        now = datetime.now(UTC)
        prop.revision += 1
        prop.status = PropertyStatus.REJECTED
        prop.updated_at = now
        prop.revision_history.append(
            PropertyRevisionRecord(
                revision=prop.revision,
                status=PropertyStatus.REJECTED,
                timestamp=now,
                reason="Rejected by developer",
                actor="developer",
            )
        )
        self.save(prop)
        return prop

    def merge_candidates(
        self,
        candidates: list[Property],
    ) -> tuple[list[Property], list[Property]]:
        """Merge freshly inferred candidate properties into the store.

        Uses the stable_key to ensure that existing properties are never
        overwritten, preserving human approvals and revision history.

        Returns:
            A tuple of ``(new_properties, existing_properties)``.
        """
        self.ensure_dir()
        catalog = self.load_catalog()
        existing_by_key = {p.stable_key: p for p in catalog.properties}

        new_props: list[Property] = []
        kept_existing: list[Property] = []

        for candidate in candidates:
            if candidate.stable_key in existing_by_key:
                kept_existing.append(existing_by_key[candidate.stable_key])
            else:
                self.save(candidate)
                new_props.append(candidate)
                existing_by_key[candidate.stable_key] = candidate

        return new_props, kept_existing
