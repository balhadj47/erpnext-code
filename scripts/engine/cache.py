"""Phase 7: Filesystem Cache

Avoids repeated scans of hooks.py, modules.txt, DocType JSONs.
Cache invalidates when any tracked file's mtime changes.
"""

import json
import os
from pathlib import Path
from typing import Any

from .interfaces import ArtifactGraph, ICache


class ProjectModelCache(ICache):
    """Filesystem-backed cache for the artifact graph."""

    def __init__(self, cache_dir: str = ".builds/.cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / "cache_index.json"

    def _cache_path(self, app_path: str) -> Path:
        """Get the cache file path for an app."""
        safe_name = Path(app_path).resolve().name
        return self.cache_dir / f"{safe_name}.json"  # H3/S1: JSON instead of pickle

    def _scan_mtimes(self, app_path: str) -> dict[str, float]:
        """Scan mtimes of all tracked files."""
        mtimes: dict[str, float] = {}
        root = Path(app_path)
        tracked_patterns = [
            "hooks.py", "modules.txt", "patches.txt", "pyproject.toml",
            "**/doctype/**/*.json", "**/doctype/**/*.py",
            "**/workspace/**/*.json", "**/report/**/*.json",
            "**/dashboard/**/*.json", "**/fixtures/**/*.json",
        ]
        for pattern in tracked_patterns:
            for f in root.glob(pattern):
                try:
                    mtimes[str(f)] = f.stat().st_mtime
                except OSError:
                    pass
        return mtimes

    def is_fresh(self, app_path: str) -> bool:
        """Compare cached mtimes with current filesystem state."""
        cache_file = self._cache_path(app_path)
        meta_file = self.cache_dir / f"{Path(app_path).resolve().name}_meta.json"
        if not cache_file.exists() or not meta_file.exists():
            return False
        try:
            cached_mtimes = json.loads(meta_file.read_text())
            current_mtimes = self._scan_mtimes(app_path)
            return cached_mtimes == current_mtimes
        except (json.JSONDecodeError, OSError):
            return False

    def get_graph(self, app_path: str) -> ArtifactGraph | None:
        """Get cached artifact graph if fresh."""
        if not self.is_fresh(app_path):
            return None
        cache_file = self._cache_path(app_path)
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            return self._graph_from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError):
            return None

    def _graph_from_dict(self, data: dict) -> ArtifactGraph:
        """Reconstruct ArtifactGraph from JSON dict. (H3/S1: JSON replaces pickle)"""
        from .interfaces import DocTypeDef
        import dataclasses
        docs = {}
        for name, d in data.get("doctypes", {}).items():
            docs[name] = DocTypeDef(**d)
        childs = {}
        for name, d in data.get("child_tables", {}).items():
            childs[name] = DocTypeDef(**d)
        return ArtifactGraph(
            app_name=data.get("app_name", ""),
            app_path=data.get("app_path", ""),
            modules=data.get("modules", []),
            doctypes=docs,
            child_tables=childs,
            hooks=data.get("hooks", {}),
            patches=data.get("patches", []),
            fixtures=data.get("fixtures", {}),
            workspaces=data.get("workspaces", []),
            reports=data.get("reports", []),
            dashboards=data.get("dashboards", []),
            dependency_order=data.get("dependency_order", []),
        )

    def _graph_to_dict(self, graph: ArtifactGraph) -> dict:
        """Serialize ArtifactGraph to JSON-safe dict. (H3/S1: JSON replaces pickle)"""
        import dataclasses
        return {
            "app_name": graph.app_name,
            "app_path": graph.app_path,
            "modules": graph.modules,
            "doctypes": {n: dataclasses.asdict(d) for n, d in graph.doctypes.items()},
            "child_tables": {n: dataclasses.asdict(d) for n, d in graph.child_tables.items()},
            "hooks": graph.hooks,
            "patches": graph.patches,
            "fixtures": graph.fixtures,
            "workspaces": graph.workspaces,
            "reports": graph.reports,
            "dashboards": graph.dashboards,
            "dependency_order": graph.dependency_order,
        }

    def put_graph(self, app_path: str, graph: ArtifactGraph):
        """Cache the artifact graph with current mtimes."""
        cache_file = self._cache_path(app_path)
        meta_file = self.cache_dir / f"{Path(app_path).resolve().name}_meta.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(self._graph_to_dict(graph), f)  # H3/S1: JSON instead of pickle
            mtimes = self._scan_mtimes(app_path)
            meta_file.write_text(json.dumps(mtimes, indent=2))
        except OSError:
            pass

    def invalidate(self, app_path: str, file_path: str):
        """Invalidate cache entries affected by a file change."""
        cache_file = self._cache_path(app_path)
        meta_file = self.cache_dir / f"{Path(app_path).resolve().name}_meta.json"
        cache_file.unlink(missing_ok=True)
        meta_file.unlink(missing_ok=True)
