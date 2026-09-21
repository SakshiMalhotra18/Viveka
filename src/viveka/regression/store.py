"""
Persistence store for VIVEKA Phase 10 BehavioralRegression artifacts.

Saves regression artifacts to .viveka/regressions/ as individual YAML files.
Filenames are derived only from validated VREG-prefixed IDs.
Regressions are git-ignored by default (private-by-default policy).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.regression.models import BehavioralRegression


class RegressionNotFoundError(VivekaError):
    """Raised when a requested regression ID is not found."""


class RegressionStore:
    """Manages reading and writing BehavioralRegression artifacts to .viveka/regressions/."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.regressions_dir = self.project_root / ".viveka" / "regressions"

    def ensure_dir(self) -> Path:
        """Ensure the `.viveka/regressions/` directory exists."""
        self.regressions_dir.mkdir(parents=True, exist_ok=True)
        return self.regressions_dir

    def regression_path(self, regression_id: str) -> Path:
        """Return expected YAML file path for a regression ID.

        Filename is derived from validated VREG ID only.
        """
        return self.regressions_dir / f"{regression_id}.yaml"

    def save(self, regression: BehavioralRegression) -> Path:
        """Save a BehavioralRegression artifact to disk as a YAML file."""
        self.ensure_dir()
        path = self.regression_path(regression.regression_id)
        dumped = regression.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def load(self, regression_id: str) -> BehavioralRegression | None:
        """Load a specific BehavioralRegression by ID."""
        if not self.regressions_dir.is_dir():
            return None
        path = self.regression_path(regression_id)
        if not path.is_file():
            for yaml_file in sorted(self.regressions_dir.glob("*.yaml")):
                if yaml_file.stem == regression_id:
                    path = yaml_file
                    break
            else:
                return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "regression_id" in data:
                return BehavioralRegression.model_validate(data)
        except Exception:
            return None
        return None

    def find_by_fingerprint(self, fingerprint: str) -> BehavioralRegression | None:
        """Find an existing BehavioralRegression matching the given fingerprint."""
        if not self.regressions_dir.is_dir():
            return None
        for yaml_file in sorted(self.regressions_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("fingerprint") == fingerprint:
                    return BehavioralRegression.model_validate(data)
            except Exception:
                continue
        return None

    def load_all(self) -> list[BehavioralRegression]:
        """Load all BehavioralRegression artifacts."""
        if not self.regressions_dir.is_dir():
            return []
        results: list[BehavioralRegression] = []
        for yaml_file in sorted(self.regressions_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "regression_id" in data:
                    results.append(BehavioralRegression.model_validate(data))
            except Exception:
                continue
        return results

    def clear(self) -> int:
        """Remove all stored regression files."""
        if not self.regressions_dir.is_dir():
            return 0
        count = 0
        for yaml_file in self.regressions_dir.glob("*.yaml"):
            try:
                yaml_file.unlink()
                count += 1
            except OSError:
                pass
        return count
