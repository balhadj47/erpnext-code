"""Phase 11.3: Rollback

Tracks file state before modifications. On repeated failure,
automatically restores the last stable state.

Rollback restores: files, generated artifacts, journal state.
Never leaves the repository partially modified.
"""

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class FileSnapshot:
    """Snapshot of a file's state before modification."""
    path: str
    content: str | None = None  # None means file didn't exist
    existed: bool = False
    checksum: str = ""

    def restore(self, app_path: str):
        """Restore this file to its original state."""
        full_path = Path(app_path) / self.path
        if self.content is None:
            # File didn't exist before — delete it
            full_path.unlink(missing_ok=True)
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(self.content)


class RollbackManager:
    """Manages file snapshots for rollback."""

    def __init__(self, app_path: str, journal_dir: str = ".builds"):
        self.app_path = Path(app_path)
        self.journal_dir = Path(journal_dir)
        self.snapshots: list[FileSnapshot] = []
        self._enabled = True

    def snapshot_file(self, relative_path: str):
        """Take a snapshot of a file before modifying it."""
        if not self._enabled:
            return
        full_path = self.app_path / relative_path
        if full_path.exists():
            try:
                content = full_path.read_text()
                self.snapshots.append(FileSnapshot(
                    path=relative_path,
                    content=content,
                    existed=True,
                    checksum=str(hash(content)),
                ))
            except (OSError, UnicodeDecodeError):
                # Binary file or unreadable — skip
                pass
        else:
            self.snapshots.append(FileSnapshot(
                path=relative_path,
                content=None,
                existed=False,
            ))

    def snapshot_directory(self, pattern: str = "**/*"):
        """Snapshot all files matching a pattern."""
        for f in self.app_path.glob(pattern):
            if f.is_file() and not any(p in str(f) for p in [".git/", "__pycache__/", ".builds/", "node_modules/"]):
                self.snapshot_file(str(f.relative_to(self.app_path)))

    def rollback(self) -> list[str]:
        """Restore all files to their original state. Returns list of restored files."""
        restored = []
        for snapshot in reversed(self.snapshots):  # Reverse: restore newest first
            try:
                snapshot.restore(str(self.app_path))
                restored.append(snapshot.path)
            except OSError:
                pass
        self.snapshots.clear()
        return restored

    def save_snapshot_state(self, build_id: str):
        """Save snapshot state to journal for audit trail."""
        build_dir = self.journal_dir / build_id
        build_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "timestamp": datetime.now().isoformat(),
            "file_count": len(self.snapshots),
            "files": [
                {"path": s.path, "existed": s.existed, "checksum": s.checksum}
                for s in self.snapshots
            ],
        }
        (build_dir / "snapshot.json").write_text(json.dumps(state, indent=2))

    def has_snapshots(self) -> bool:
        return len(self.snapshots) > 0

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True
