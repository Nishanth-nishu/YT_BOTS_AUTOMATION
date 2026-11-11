"""Download one registered checkpoint, after the licence gate and the disk check.

    python -m animeforge.cluster.fetch_model <registry id> <hf repo> [--allow PATTERN ...]

The size is read from the model host before anything is fetched; the download
is refused when it would leave less than the reserve free.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path

from animeforge import registry
from animeforge.storage import ensure_space


def planned_gb(repo: str, allow: list[str]) -> float:
    from huggingface_hub import HfApi

    info = HfApi().model_info(repo, files_metadata=True)
    total = 0
    for f in info.siblings:
        if allow and not any(fnmatch.fnmatch(f.rfilename, p) for p in allow):
            continue
        total += f.size or 0
    return total / 1e9


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_id")
    ap.add_argument("repo")
    ap.add_argument("--allow", nargs="*", default=[])
    a = ap.parse_args()

    ack = tuple(x for x in os.environ.get("ANIMEFORGE_ACK", "").split(",") if x)
    registry.require(a.model_id, acknowledged=ack)

    hub = Path(os.environ["HF_HOME"])
    hub.mkdir(parents=True, exist_ok=True)
    need = planned_gb(a.repo, a.allow)
    print(f"{a.repo}: {need:.1f} GB to fetch")
    ensure_space(hub, need, a.repo)

    from huggingface_hub import snapshot_download

    path = snapshot_download(a.repo, allow_patterns=a.allow or None)
    print("at", path)


if __name__ == "__main__":
    main()
