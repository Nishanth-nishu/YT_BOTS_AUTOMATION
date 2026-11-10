"""Restyle the VRoid host avatar: Indian skin tone, full beard, brown eyes, black hoodie.

    python -m services.host.restyle_vrm assets/models/HairSample_Male.vrm video-engine/public/models/host.vrm

Edits the embedded textures (face, body, iris, mouth, tops) with Pillow and
repacks the VRM; meshes, rig and expressions are untouched. Coordinates refer
to the VRoid face texture layout (1024 x 1024: eyes around y 540, mouth at
y 775, chin at y 890).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from services.host.vrm_textures import extract, image_name, read_glb, repack, write_glb

SKIN_MUL = (0.64, 0.49, 0.40)  # medium brown from the model's pale base, less orange
BEARD = (34, 22, 16)


def tint_skin(im: Image.Image) -> Image.Image:
    arr = np.asarray(im.convert("RGBA")).astype(np.float32)
    arr[:, :, 0] *= SKIN_MUL[0]
    arr[:, :, 1] *= SKIN_MUL[1]
    arr[:, :, 2] *= SKIN_MUL[2]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def beard_mask(size: tuple[int, int], seed: int = 3) -> Image.Image:
    w, h = size
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    # lower face ring: jaw and cheeks (outer ellipse of the face minus an inner one), only below the cheekbones
    d.ellipse([52, 90, 972, 960], fill=255)
    d.ellipse([190, 250, 834, 820], fill=0)
    top = Image.new("L", size, 0)
    ImageDraw.Draw(top).rectangle([0, 0, w, 610], fill=255)
    m = Image.composite(Image.new("L", size, 0), m, top)
    # chin block under the lower lip and the moustache above the lip
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([300, 812, 724, 905], radius=120, fill=255)
    d.ellipse([410, 722, 614, 764], fill=255)
    # keep the lips clear
    d.ellipse([420, 760, 604, 806], fill=0)
    # soften, then break up with noise so it reads as hair, not paint
    m = m.filter(ImageFilter.GaussianBlur(14))
    rng = np.random.default_rng(seed)
    noise = rng.uniform(0.72, 1.0, size=(h, w)).astype(np.float32)
    noise = np.asarray(Image.fromarray((noise * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255.0
    arr = np.asarray(m).astype(np.float32) / 255.0 * noise * 0.96
    return Image.fromarray((arr * 255).astype(np.uint8), "L")


def paint_beard(face: Image.Image) -> Image.Image:
    face = face.convert("RGBA")
    layer = Image.new("RGBA", face.size, BEARD + (255,))
    layer.putalpha(beard_mask(face.size))
    out = face.copy()
    out.alpha_composite(layer)
    return out


def brown_eyes(iris: Image.Image) -> Image.Image:
    arr = np.asarray(iris.convert("RGBA")).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3:4]
    lum = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) / 255.0
    tint = np.array([112.0, 62.0, 30.0])
    out = lum[:, :, None] * tint[None, None, :] * 1.6
    out = np.concatenate([out.clip(0, 255), a], axis=2)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def black_hoodie(tops: Image.Image) -> Image.Image:
    arr = np.asarray(tops.convert("RGBA")).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3:4]
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    dark = lum * 0.16 + 8.0
    out = np.stack([dark, dark, dark * 1.08], axis=2)
    return Image.fromarray(np.concatenate([out.clip(0, 255), a], axis=2).astype(np.uint8), "RGBA")


def darker_lips(mouth: Image.Image) -> Image.Image:
    arr = np.asarray(mouth.convert("RGBA")).astype(np.float32)
    arr[:, :, 0] *= 0.78
    arr[:, :, 1] *= 0.56
    arr[:, :, 2] *= 0.52
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def main(argv: list[str]) -> int:
    src, dst = Path(argv[0]), Path(argv[1])
    gltf, bin_chunk = read_glb(src)
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        extract(gltf, bin_chunk, tdir)
        edits = {
            "Face_00": lambda im: paint_beard(tint_skin(im)),
            "Body_00": tint_skin,
            "EyeIris_00": brown_eyes,
            "Tops_01": black_hoodie,
            "FaceMouth_00": darker_lips,
        }
        edited = tdir / "edited"
        edited.mkdir()
        for i in range(len(gltf["images"])):
            name = image_name(gltf, i)
            for key, fn in edits.items():
                if name.endswith(key):
                    f = next(tdir.glob(f"{i:02d}_*"))
                    fn(Image.open(f)).save(edited / f"{i:02d}_{name}.png")
                    print("edited", name)
        gltf, new_bin = repack(gltf, bin_chunk, edited)
    write_glb(dst, gltf, new_bin)
    print("wrote", dst, dst.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
