"""JSON storage for the recipe library.

Design goals:
- Path safety: the store file must live inside an allowed base directory,
  must end in ``.json``, and we re-check the real path on every write so a
  renamed/symlinked directory can't smuggle us outside the sandbox.
- Auto-backup: before every mutating save we rotate up to ``keep_backups``
  copies (``recipes.json.bak-3`` is the newest). If anything goes wrong
  mid-write, the previous file plus its backups are untouched.
- Atomic saves via a temp file + os.replace in the same directory.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .starter_recipes import starter_recipes

STORE_FILENAME = "recipes.json"
BACKUP_PREFIX = STORE_FILENAME + ".bak-"
DEFAULT_KEEP_BACKUPS = 3


class StorageError(Exception):
    """Raised when a storage operation is unsafe or fails."""


def validate_store_path(raw_path: str | os.PathLike, base_dir: Path) -> Path:
    """Prove ``raw_path`` is inside ``base_dir`` and is a safe target.

    Returns the fully resolved real path. Raises StorageError otherwise.
    """
    base = Path(os.path.realpath(str(base_dir)))
    try:
        resolved = Path(os.path.realpath(str(raw_path)))
    except (OSError, ValueError) as exc:  # ValueError: embedded null bytes
        raise StorageError(f"invalid store path: {raw_path!r}") from exc

    if resolved.parent != base:
        raise StorageError(
            f"store path must name a file directly inside {base}: got {resolved}"
        )
    if resolved.name != STORE_FILENAME:
        raise StorageError(f"store file must be named {STORE_FILENAME!r}")
    # Belt-and-checks: no symlink, no traversal, .json extension.
    if resolved.is_symlink() or STORE_FILENAME not in resolved.name:
        raise StorageError("store path must not be a symlink")
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise StorageError("store path escapes the allowed directory") from exc
    return resolved


class RecipeStore:
    """Load/seed/save a recipe collection with rotation backups."""

    # ---- path safety ----------------------------------------------------

    @staticmethod
    def validate_data_dir(raw: str) -> Path:
        """Sanity-check the data directory before starting (CLI guard)."""
        if not isinstance(raw, str) or not raw.strip():
            raise StorageError("data directory must be a non-empty path")
        path = Path(raw.strip())
        try:
            path = Path(os.path.realpath(str(path)))
        except (OSError, ValueError) as exc:
            raise StorageError(f"invalid data directory: {raw!r}") from exc
        if path.exists() and not path.is_dir():
            raise StorageError(f"data directory path is not a directory: {path}")
        if path.name == "":
            raise StorageError("data directory must not be the filesystem root")
        return path

    def __init__(
        self,
        data_dir: str | os.PathLike,
        *,
        keep_backups: int = DEFAULT_KEEP_BACKUPS,
        seed: bool = True,
    ) -> None:
        self.keep_backups = max(1, int(keep_backups))
        self.base_dir = Path(os.path.realpath(str(data_dir)))
        self.path = validate_store_path(self.base_dir / STORE_FILENAME, self.base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_json(seed_recipes() if seed else [])
            self._rotate_backups()  # make backup #1 of the fresh file
        self.recipes = self._load()

    # ---- reading -------------------------------------------------------

    def _load(self) -> list[dict]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        except OSError as exc:
            raise StorageError(f"cannot read store: {exc}") from exc
        if not text.strip():
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # Corrupt main file: fall back to the newest readable backup.
            data = self._recover_from_backup(exc)
        if isinstance(data, dict) and isinstance(data.get("recipes"), list):
            return data["recipes"]
        if isinstance(data, list):
            return data
        return []

    def _recover_from_backup(self, original_exc: Exception) -> list[dict]:
        for backup in self.list_backups():
            try:
                data = json.loads(backup.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and isinstance(data.get("recipes"), list):
                return data["recipes"]
            if isinstance(data, list):
                return data
        raise StorageError(f"store file is corrupt and no backup could be read: {original_exc}")

    def list_backups(self) -> list[Path]:
        """Backup paths, newest first."""
        found = []
        for p in self.base_dir.glob(f"{BACKUP_PREFIX}*"):
            suffix = p.name[len(BACKUP_PREFIX):]
            if suffix.isdigit():
                found.append(p)
        found.sort(key=lambda p: int(p.name[len(BACKUP_PREFIX):]), reverse=True)
        return found

    # ---- writing -------------------------------------------------------

    def save(self) -> None:
        """Validate path again (it may have moved), rotate backups, write."""
        self.path = validate_store_path(self.path, self.base_dir)
        self._rotate_backups()
        self._write_json(list(self.recipes))

    def _rotate_backups(self) -> None:
        existing = self.list_backups()
        # Shift numbered slots: bak-2 -> bak-3, bak-1 -> bak-2, newest = bak-1.
        for old in reversed(existing[: self.keep_backups]):
            n = int(old.name[len(BACKUP_PREFIX):])
            if n + 1 <= self.keep_backups:
                try:
                    os.replace(old, self.base_dir / f"{BACKUP_PREFIX}{n + 1}")
                except OSError:
                    pass
            else:
                old.unlink(missing_ok=True)
        if self.path.exists():
            shutil.copy2(self.path, self.base_dir / f"{BACKUP_PREFIX}1")

    def _write_json(self, recipes: list[dict]) -> None:
        tmp = self.base_dir / f".{STORE_FILENAME}.tmp-{int(time.time() * 1000)}"
        payload = json.dumps({"recipes": recipes}, indent=2, ensure_ascii=False, sort_keys=False)
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise StorageError(f"cannot write store: {exc}") from exc


def seed_recipes() -> list[dict]:
    """The starter recipe set, normalized for storage."""
    return [normalize_recipe(r) for r in starter_recipes()]


def normalize_recipe(raw: dict) -> dict:
    """Validate + normalize one recipe dict; raises ValueError on bad input."""
    from .service import normalize_recipe as service_normalize

    return service_normalize(raw)
