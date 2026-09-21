"""
Persistence store for Phase 9 ReductionResult records.

Saves and manages reduction results in `.viveka/reductions/` as YAML files.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.reduction.models import ReductionResult


class ReductionNotFoundError(VivekaError):
    """Raised when a requested reduction ID is not found."""


class ReductionStore:
    """Manages reading and writing ReductionResult models to .viveka/reductions/."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.reductions_dir = self.project_root / ".viveka" / "reductions"

    def ensure_dir(self) -> Path:
        """Ensure the `.viveka/reductions/` directory exists."""
        self.reductions_dir.mkdir(parents=True, exist_ok=True)
        return self.reductions_dir

    def reduction_path(self, reduction_id: str) -> Path:
        """Return expected YAML file path for a reduction ID."""
        return self.reductions_dir / f"{reduction_id}.yaml"

    def save(self, result: ReductionResult) -> Path:
        """Save a ReductionResult to disk as a YAML file."""
        self.ensure_dir()
        path = self.reduction_path(result.reduction_id)
        dumped = result.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def load(self, reduction_id: str) -> ReductionResult | None:
        """Load a specific reduction result by ID."""
        if not self.reductions_dir.is_dir():
            return None
        path = self.reduction_path(reduction_id)
        if not path.is_file():
            for yaml_file in sorted(self.reductions_dir.glob("*.yaml")):
                if yaml_file.stem == reduction_id or yaml_file.name == f"{reduction_id}.yaml":
                    path = yaml_file
                    break
            else:
                return None

        try:
            raw_text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_text)
            if isinstance(data, dict) and "reduction_id" in data:
                return ReductionResult.model_validate(data)
        except Exception:
            return None

        return None

    def load_all(self) -> list[ReductionResult]:
        """Load all reduction results stored in `.viveka/reductions/`."""
        if not self.reductions_dir.is_dir():
            return []

        results: list[ReductionResult] = []
        for yaml_file in sorted(self.reductions_dir.glob("*.yaml")):
            try:
                raw_text = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(raw_text)
                if isinstance(data, dict) and "reduction_id" in data:
                    results.append(ReductionResult.model_validate(data))
            except Exception:
                continue

        return results

    def clear(self) -> int:
        """Remove all stored reduction files."""
        if not self.reductions_dir.is_dir():
            return 0
        count = 0
        for yaml_file in self.reductions_dir.glob("*.yaml"):
            try:
                yaml_file.unlink()
                count += 1
            except OSError:
                pass
        return count
