"""Disk-space guard. Nothing large is downloaded until this says there is room.

    from animeforge.storage import ensure_space
    ensure_space(settings().models_dir, need_gb=17.0, what="Wan2.1 I2V 14B 480P")

It raises StorageError, naming the drive, what is free and what is needed,
when the download would leave less than the reserve (default 20 GB) on that
drive. Downloaders must call it with the real size taken from the model host,
never a guess, and must not catch the error to carry on.

    python -m animeforge.storage              # free space on the drives AnimeForge uses
"""
from __future__ import annotations

import shutil
from pathlib import Path

from animeforge.config import settings


class StorageError(RuntimeError):
    pass


def existing_parent(path: Path) -> Path:
    """The nearest directory that exists, so space can be checked before a folder is created."""
    p = Path(path).resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def free_gb(path: Path) -> float:
    return shutil.disk_usage(existing_parent(path)).free / 1024 ** 3


def ensure_space(path: Path, need_gb: float, what: str = "download", reserve_gb: float | None = None, free: float | None = None) -> float:
    """Return the free space that would remain. Raise StorageError if it would dip under the reserve."""
    if need_gb < 0:
        raise ValueError("need_gb must be zero or more")
    reserve = settings().reserve_gb if reserve_gb is None else reserve_gb
    have = free_gb(path) if free is None else free
    left = have - need_gb
    if left < reserve:
        raise StorageError(f"not enough disk space for {what}: needs {need_gb:.1f} GB, {existing_parent(path).anchor or existing_parent(path)} has {have:.1f} GB free, "
                           f"and {reserve:.0f} GB must stay free. Free up {reserve - left:.1f} GB or point ANIMEFORGE_MODELS_DIR at a larger drive.")
    return left


def report() -> list[dict]:
    s = settings()
    seen: dict[str, dict] = {}
    for label, p in (("home", s.home), ("models", s.models_dir), ("cache", s.cache_dir)):
        root = existing_parent(p)
        usage = shutil.disk_usage(root)
        key = Path(root).anchor or str(root)
        entry = seen.setdefault(key, {"drive": key, "free_gb": round(usage.free / 1024 ** 3, 1), "total_gb": round(usage.total / 1024 ** 3, 1), "used_for": []})
        entry["used_for"].append(label)
    return list(seen.values())


if __name__ == "__main__":
    for d in report():
        print(f"{d['drive']}  {d['free_gb']} GB free of {d['total_gb']} GB  (AnimeForge {', '.join(d['used_for'])})")
