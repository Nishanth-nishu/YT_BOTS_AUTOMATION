"""Make a second character from the host avatar by recolouring its textures.

    python -m services.host.make_guest [video-engine/public/models/host.vrm] [video-engine/public/models/guest.vrm]

Same CC0 VRoid model (assets/models/LICENSE.txt), so no new asset or licence:
the hoodie becomes orange with the host's name removed, and the hair goes
sandy blond. Meshes, rig and expressions are untouched, so the guest lip-syncs
and emotes exactly like the host.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from services.common import paths
from services.host.vrm_textures import extract, image_name, read_glb, repack, write_glb

HOODIE = (238, 118, 38)
HAIR = (222, 184, 112)
NAME_BOX = (1080, 1160, 1330, 1225)  # where restyle_vrm.name_on_hoodie prints the host's name (2048 texture)


def _recolour(im: Image.Image, colour: tuple[int, int, int], floor: float, gain: float) -> Image.Image:
    """Keep the shading (luminance) and swap the colour: dark fabric or hair becomes `colour`."""
    arr = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3:4]
    lum = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) / 255.0
    shade = (floor + lum * gain).clip(0, 1.15)[:, :, None]
    out = np.asarray(colour, dtype=np.float32)[None, None, :] * shade
    return Image.fromarray(np.concatenate([out.clip(0, 255), a], axis=2).astype(np.uint8), "RGBA")


def orange_hoodie(tops: Image.Image) -> Image.Image:
    out = tops.convert("RGBA")
    scale = out.size[0] / 2048
    box = tuple(int(v * scale) for v in NAME_BOX)
    # paint the name out with the fabric colour sampled just left of it
    fabric = out.getpixel((max(0, box[0] - int(30 * scale)), (box[1] + box[3]) // 2))
    ImageDraw.Draw(out).rectangle(box, fill=fabric)
    return _recolour(out, HOODIE, floor=0.5, gain=2.6)


def blond_hair(hair: Image.Image) -> Image.Image:
    return _recolour(hair, HAIR, floor=0.42, gain=1.5)


def main(argv: list[str]) -> int:
    src = Path(argv[0]) if argv else paths.PUBLIC / "models" / "host.vrm"
    dst = Path(argv[1]) if len(argv) > 1 else paths.PUBLIC / "models" / "guest.vrm"
    gltf, bin_chunk = read_glb(src)
    edits = {"Tops_01": orange_hoodie, "Hair_00": blond_hair}
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        extract(gltf, bin_chunk, tdir)
        edited = tdir / "edited"
        edited.mkdir()
        for i in range(len(gltf["images"])):
            name = image_name(gltf, i)
            for key, fn in edits.items():
                if name.endswith(key):
                    fn(Image.open(next(tdir.glob(f"{i:02d}_*")))).save(edited / f"{i:02d}_{name}.png")
                    print("edited", name)
        gltf, new_bin = repack(gltf, bin_chunk, edited)
    write_glb(dst, gltf, new_bin)
    print("wrote", dst, dst.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
