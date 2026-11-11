"""Download the extra CC0 characters for the dialogue scene.

    python -m services.host.fetch_cast

Both are VRoid Project sample models that pixiv released under CC0 (see
assets/models/LICENSE.txt), mirrored on OpenGameArt. Each archive is checked
against a known SHA-256 before anything is unpacked, and only the .vrm inside
is kept. The models are not committed: they are 15 to 20 MB each.
"""
from __future__ import annotations

import hashlib
import io
import sys
import zipfile

import httpx

from services.common import paths

BASE = "https://opengameart.org/sites/default/files/"
CAST = {
    # output name: (archive, archive sha256, member inside the archive)
    "fumiriya.vrm": ("sakurada_fumiriya.zip", "f3c53eea11398c7ed650d686a1e19e0823122068280ed4adc8105c9913e9fc66", "Sakurada Fumiriya.vrm"),
    "shino.vrm": ("sendagaya_shino.zip", "ff85ff42c1d041fd66dabdb36761a98557d7b55199f635769f3698a41c0a3696", "Sendagaya Shino.vrm"),
}


def fetch(force: bool = False) -> list[str]:
    out_dir = paths.PUBLIC / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True) as client:
        for name, (archive, sha, member) in CAST.items():
            target = out_dir / name
            if target.exists() and not force:
                done.append(f"{name}: already present")
                continue
            blob = client.get(BASE + archive).raise_for_status().content
            got = hashlib.sha256(blob).hexdigest()
            if got != sha:
                raise RuntimeError(f"{archive}: checksum mismatch ({got}); refusing to unpack")
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                data = z.read(member)
            if data[:4] != b"glTF":
                raise RuntimeError(f"{member} is not a VRM/glTF binary")
            target.write_bytes(data)
            done.append(f"{name}: downloaded ({len(data)} bytes)")
    return done


if __name__ == "__main__":
    print("\n".join(fetch(force="--force" in sys.argv)))
