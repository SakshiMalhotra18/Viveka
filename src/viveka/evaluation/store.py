"""
Persistence store for VIVEKA Phase 8 EvaluationResult artifacts.

Saves evaluation artifacts to .viveka/evaluations/ as individual YAML files.
Evaluation artifacts are local evidence; they are git-ignored by default.

Phase 10 diagnosis engine uses this store to retrieve EvaluationEvidence
associated with a historical reproduction run.

Do not redesign Phase 8 evaluation semantics.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.evaluation.models import EvaluationResult


class EvaluationNotFoundError(VivekaError):
    """Raised when a requested evaluation ID is not found."""


class EvaluationStore:
    """Manages reading and writing EvaluationResult artifacts to .viveka/evaluations/."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.evaluations_dir = self.project_root / ".viveka" / "evaluations"

    def ensure_dir(self) -> Path:
        """Ensure the `.viveka/evaluations/` directory exists."""
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)
        return self.evaluations_dir

    def evaluation_path(self, eval_id: str) -> Path:
        """Return the expected YAML file path for an evaluation ID.

        Filename is derived from the validated VEVAL-prefixed ID only,
        never from untrusted free-form strings.
        """
        return self.evaluations_dir / f"{eval_id}.yaml"

    def save(self, result: EvaluationResult) -> Path:
        """Save an EvaluationResult to disk as a YAML file."""
        self.ensure_dir()
        path = self.evaluation_path(result.eval_id)
        dumped = result.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def load(self, eval_id: str) -> EvaluationResult | None:
        """Load a specific EvaluationResult by ID."""
        if not self.evaluations_dir.is_dir():
            return None
        path = self.evaluation_path(eval_id)
        if not path.is_file():
            for yaml_file in sorted(self.evaluations_dir.glob("*.yaml")):
                if yaml_file.stem == eval_id:
                    path = yaml_file
                    break
            else:
                return None

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "eval_id" in data:
                return EvaluationResult.model_validate(data)
        except Exception:
            return None
        return None

    def load_for_run(self, execution_id: str) -> list[EvaluationResult]:
        """Load all EvaluationResult artifacts for a given execution ID."""
        if not self.evaluations_dir.is_dir():
            return []
        results: list[EvaluationResult] = []
        for yaml_file in sorted(self.evaluations_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("execution_id") == execution_id:
                    results.append(EvaluationResult.model_validate(data))
            except Exception:
                continue
        return results

    def clear(self) -> int:
        """Remove all stored evaluation files."""
        if not self.evaluations_dir.is_dir():
            return 0
        count = 0
        for yaml_file in self.evaluations_dir.glob("*.yaml"):
            try:
                yaml_file.unlink()
                count += 1
            except OSError:
                pass
        return count
