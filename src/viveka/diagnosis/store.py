"""
Persistence store for VIVEKA Phase 10 Diagnosis artifacts.

Saves diagnosis artifacts to .viveka/diagnoses/ as individual YAML files.
Filenames are derived only from validated VDIAG-prefixed IDs.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.diagnosis.models import Diagnosis


class DiagnosisNotFoundError(VivekaError):
    pass


class DiagnosisStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.diagnoses_dir = self.project_root / ".viveka" / "diagnoses"

    def ensure_dir(self) -> Path:
        self.diagnoses_dir.mkdir(parents=True, exist_ok=True)
        return self.diagnoses_dir

    def diagnosis_path(self, diag_id: str) -> Path:
        return self.diagnoses_dir / f"{diag_id}.yaml"

    def save(self, diagnosis: Diagnosis) -> Path:
        self.ensure_dir()
        path = self.diagnosis_path(diagnosis.diag_id)
        dumped = diagnosis.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def load(self, diag_id: str) -> Diagnosis | None:
        if not self.diagnoses_dir.is_dir():
            return None
        path = self.diagnosis_path(diag_id)
        if not path.is_file():
            for yaml_file in sorted(self.diagnoses_dir.glob("*.yaml")):
                if yaml_file.stem == diag_id:
                    path = yaml_file
                    break
            else:
                return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "diag_id" in data:
                return Diagnosis.model_validate(data)
        except Exception:
            return None
        return None

    def load_for_reduction(self, reduction_id: str) -> Diagnosis | None:
        if not self.diagnoses_dir.is_dir():
            return None
        for yaml_file in sorted(self.diagnoses_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("reduction_id") == reduction_id:
                    return Diagnosis.model_validate(data)
            except Exception:
                continue
        return None

    def load_all(self) -> list[Diagnosis]:
        if not self.diagnoses_dir.is_dir():
            return []
        results: list[Diagnosis] = []
        for yaml_file in sorted(self.diagnoses_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "diag_id" in data:
                    results.append(Diagnosis.model_validate(data))
            except Exception:
                continue
        return results

    def clear(self) -> int:
        if not self.diagnoses_dir.is_dir():
            return 0
        count = 0
        for yaml_file in self.diagnoses_dir.glob("*.yaml"):
            try:
                yaml_file.unlink()
                count += 1
            except OSError:
                pass
        return count
