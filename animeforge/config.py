"""AnimeForge settings: where things live and what the target machine must have.

Every path can be moved with an environment variable (or the same key in the
repo's git-ignored .env), so models can sit on a different drive from the code:

    ANIMEFORGE_HOME        working data (database, jobs, outputs)   default <repo>/data/animeforge
    ANIMEFORGE_MODELS_DIR  model checkpoints                         default <home>/models
    ANIMEFORGE_CACHE_DIR   download and inference caches             default <home>/cache
    ANIMEFORGE_DB          SQLite database file                      default <home>/animeforge.sqlite
    ANIMEFORGE_ACK         comma-separated ids of conditional models whose conditions you accept
    ANIMEFORGE_RESERVE_GB  free space to always leave on a drive     default 20
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# What the platform is designed for (spec section 1). The audit compares a machine against this.
TARGET = {"gpu_vendor": "NVIDIA", "min_vram_gb": 24, "min_ram_gb": 32, "min_free_disk_gb": 150}


@dataclass(frozen=True)
class Settings:
    home: Path
    models_dir: Path
    cache_dir: Path
    db: Path
    acknowledged: tuple[str, ...]
    reserve_gb: float


def settings(env: dict | None = None) -> Settings:
    e = os.environ if env is None else env
    home = Path(e.get("ANIMEFORGE_HOME") or ROOT / "data" / "animeforge")
    return Settings(
        home=home,
        models_dir=Path(e.get("ANIMEFORGE_MODELS_DIR") or home / "models"),
        cache_dir=Path(e.get("ANIMEFORGE_CACHE_DIR") or home / "cache"),
        db=Path(e.get("ANIMEFORGE_DB") or home / "animeforge.sqlite"),
        acknowledged=tuple(x.strip() for x in (e.get("ANIMEFORGE_ACK") or "").split(",") if x.strip()),
        reserve_gb=float(e.get("ANIMEFORGE_RESERVE_GB") or 20),
    )
