"""
Persistence store for VIVEKA Phase 6 worlds.

Stores and manages generated worlds in `.viveka/worlds/` as individual YAML files.
This provides git-friendly diffs, versioning, audit tracking, and human editability.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from viveka.core.errors import VivekaError
from viveka.worlds.models import World


class WorldNotFoundError(VivekaError):
    """Raised when a requested world ID is not found."""


class WorldStore:
    """Manages reading and writing World definitions to .viveka/worlds/."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.worlds_dir = self.project_root / ".viveka" / "worlds"

    def ensure_dir(self) -> Path:
        """Ensure the `.viveka/worlds/` directory exists."""
        self.worlds_dir.mkdir(parents=True, exist_ok=True)
        return self.worlds_dir

    def world_path(self, world_id: str) -> Path:
        """Return the expected YAML file path for a world ID."""
        return self.worlds_dir / f"{world_id}.yaml"

    def save(self, world: World) -> Path:
        """Save a world model to disk as a YAML file."""
        self.ensure_dir()
        path = self.world_path(world.id)
        dumped = world.model_dump(mode="json")
        yaml_content = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        path.write_text(yaml_content, encoding="utf-8")
        return path

    def save_all(self, worlds: list[World]) -> list[Path]:
        """Save multiple worlds to disk."""
        return [self.save(w) for w in worlds]

    def load(self, world_id: str) -> World | None:
        """Load a specific world by ID."""
        if not self.worlds_dir.is_dir():
            return None
        path = self.world_path(world_id)
        if not path.is_file():
            # Try searching by partial ID or scanning directory
            for yaml_file in sorted(self.worlds_dir.glob("*.yaml")):
                if yaml_file.stem == world_id or yaml_file.name == f"{world_id}.yaml":
                    path = yaml_file
                    break
            else:
                return None

        try:
            raw_text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_text)
            if isinstance(data, dict) and "id" in data:
                return World.model_validate(data)
        except Exception:
            return None

        return None

    def load_all(self) -> list[World]:
        """Load all worlds stored in `.viveka/worlds/`."""
        if not self.worlds_dir.is_dir():
            return []

        worlds: list[World] = []
        for yaml_file in sorted(self.worlds_dir.glob("*.yaml")):
            try:
                raw_text = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(raw_text)
                if isinstance(data, dict) and "id" in data:
                    world = World.model_validate(data)
                    worlds.append(world)
            except Exception:
                continue

        return worlds

    def load_by_property(self, property_stable_key: str) -> list[World]:
        """Load all worlds bound to a specific property stable key."""
        all_worlds = self.load_all()
        return [w for w in all_worlds if w.property_stable_key == property_stable_key]

    def clear(self) -> int:
        """Remove all stored world files."""
        if not self.worlds_dir.is_dir():
            return 0
        count = 0
        for yaml_file in self.worlds_dir.glob("*.yaml"):
            try:
                yaml_file.unlink()
                count += 1
            except OSError:
                pass
        return count
