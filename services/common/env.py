"""Load the git-ignored .env into os.environ (values already set win). No dependency."""
from __future__ import annotations

import os
from pathlib import Path

from services.common import paths

_loaded = False


def load_dotenv(path: Path | None = None) -> None:
    global _loaded
    env_file = path or (paths.ROOT / ".env")
    if _loaded and path is None:
        return
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.split(" #", 1)[0].strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    _loaded = True
