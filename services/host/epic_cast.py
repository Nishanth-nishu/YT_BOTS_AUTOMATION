"""Build the epic-story cast by restyling CC0 VRoid base models.

    python -m services.host.epic_cast            # build every character whose base model is present
    python -m services.host.epic_cast arjuna     # build one
    python -m services.host.epic_cast --list

The characters of the Mahabharata and Ramayana are public domain; these are
our own designs on CC0 bases (assets/models/LICENSE.txt), not copies of any
film, TV, game or comic depiction. Only textures are edited here (skin, hair,
eyes, clothes); crowns, feathers, jewellery and auras are drawn by the video
engine from the same registry (video-engine/src/design/epicCast.ts must list
the same names). Meshes, rig and expressions are untouched.

Voices are free Kokoro Hindi voices (hm_omega, hm_psi, hf_alpha, hf_beta).
`pitch` shifts a voice up or down so characters sharing a voice sound different.

Not built here: Hanuman, Garuda and Ganesha need non-human heads, which a
human base model cannot give; they need their own models.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from services.common import paths
from services.host.vrm_textures import extract, image_name, read_glb, repack, write_glb

MODELS = paths.PUBLIC / "models"
BASES = {"host": "host.vrm", "fumiriya": "fumiriya.vrm", "shino": "shino.vrm"}

GOLD = (236, 178, 60)
WHITE = (238, 236, 228)
BLACK = (26, 24, 30)

# name: base model, colours, voice. skin = ("mul", rgb multipliers) keeps the face detail and
# only tints; ("set", rgb) repaints the skin a new colour (blue Krishna, dark Kali).
CAST: dict[str, dict] = {
    "narada":       dict(label="Narad", base="fumiriya", skin=("mul", (0.93, 0.80, 0.68)), hair=BLACK, tops=(240, 150, 40), bottoms=(250, 235, 200), accessory=GOLD, eyes=(120, 80, 40), voice="hm_psi", pitch=1.14, speed=1.06),
    "drona":        dict(label="Guru Drona", base="host", skin=("mul", (0.96, 0.92, 0.90)), hair=(214, 214, 220), beard=(206, 206, 212), tops=WHITE, bottoms=(232, 226, 210), voice="hm_omega", pitch=0.90, speed=0.98),
    "arjuna":       dict(label="Arjun", base="fumiriya", skin=("mul", (0.86, 0.70, 0.58)), hair=BLACK, tops=(30, 70, 170), bottoms=(240, 200, 90), accessory=GOLD, eyes=(90, 60, 30), voice="hm_psi", pitch=0.97, speed=1.02),
    "krishna":      dict(label="Krishna", base="fumiriya", skin=("set", (70, 130, 215)), hair=(20, 22, 40), tops=(245, 196, 40), bottoms=(245, 196, 40), accessory=(200, 40, 60), eyes=(40, 30, 60), voice="hm_psi", pitch=1.04, speed=0.98),
    "karna":        dict(label="Karn", base="host", skin=("mul", (0.98, 0.90, 0.82)), hair=(40, 26, 18), tops=(196, 60, 30), bottoms=(60, 30, 24), voice="hm_omega", pitch=1.0, speed=1.0),
    "bhima":        dict(label="Bheem", base="host", skin=("mul", (0.92, 0.80, 0.72)), hair=BLACK, tops=(150, 40, 40), bottoms=(70, 40, 30), voice="hm_omega", pitch=0.82, speed=0.96, scale=1.12),
    "yudhishthira": dict(label="Yudhishthir", base="fumiriya", skin=("mul", (0.90, 0.76, 0.64)), hair=(30, 24, 22), tops=WHITE, bottoms=(230, 190, 110), accessory=GOLD, eyes=(80, 56, 30), voice="hm_omega", pitch=1.08, speed=0.96),
    "abhimanyu":    dict(label="Abhimanyu", base="fumiriya", skin=("mul", (0.90, 0.74, 0.62)), hair=(36, 24, 20), tops=(220, 70, 40), bottoms=(250, 220, 150), accessory=GOLD, eyes=(90, 60, 30), voice="hm_psi", pitch=1.10, speed=1.06),
    "ashwatthama":  dict(label="Ashwatthama", base="host", skin=("mul", (0.78, 0.74, 0.80)), hair=(60, 60, 78), tops=(40, 36, 60), bottoms=(26, 24, 36), voice="hm_omega", pitch=0.86, speed=0.94),
    "rama":         dict(label="Ram", base="fumiriya", skin=("set", (96, 150, 200)), hair=BLACK, tops=(246, 170, 40), bottoms=(246, 170, 40), accessory=GOLD, eyes=(50, 36, 30), voice="hm_omega", pitch=1.06, speed=0.96),
    "lakshmana":    dict(label="Lakshman", base="fumiriya", skin=("mul", (0.92, 0.80, 0.68)), hair=BLACK, tops=(60, 130, 70), bottoms=(240, 220, 160), accessory=GOLD, eyes=(80, 56, 30), voice="hm_psi", pitch=1.0, speed=1.04),
    "ravana":       dict(label="Ravan", base="host", skin=("mul", (0.84, 0.70, 0.66)), hair=BLACK, tops=(90, 20, 30), bottoms=(30, 20, 26), voice="hm_omega", pitch=0.78, speed=0.92, scale=1.1),
    "parashurama":  dict(label="Parashuram", base="host", skin=("mul", (0.92, 0.82, 0.74)), hair=(70, 40, 26), tops=(214, 110, 40), bottoms=(120, 60, 30), voice="hm_omega", pitch=0.94, speed=1.0),
    "draupadi":     dict(label="Draupadi", base="shino", skin=("mul", (0.92, 0.78, 0.66)), hair=BLACK, tops=(190, 30, 50), bottoms=(190, 30, 50), accessory=GOLD, eyes=(70, 44, 26), voice="hf_alpha", pitch=1.0, speed=1.0),
    "durga":        dict(label="Durga", base="shino", skin=("mul", (0.96, 0.82, 0.68)), hair=BLACK, tops=(214, 40, 40), bottoms=(240, 180, 50), accessory=GOLD, eyes=(90, 40, 30), voice="hf_beta", pitch=0.94, speed=0.96),
    "kali":         dict(label="Kali", base="shino", skin=("set", (54, 70, 130)), hair=(12, 10, 20), tops=(120, 20, 30), bottoms=(20, 16, 26), accessory=(210, 40, 50), eyes=(200, 40, 40), voice="hf_beta", pitch=0.84, speed=0.94),
}
NEEDS_OWN_MODEL = ("hanuman", "garuda", "ganesha")

TEXTURES = {"skin_face": r"Face_00$", "skin_body": r"Body_00$", "tops": r"Tops_01$", "accessory": r"Accessory_01$", "bottoms": r"Bottoms_01$",
            "hair": r"Hair(Back)?_00(_0[12])?$", "eyes": r"EyeIris_00$"}
NAME_BOX = (1080, 1160, 1330, 1225)  # the host's printed name on its hoodie (2048 texture)


def _lum(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) / 255.0


def recolour(im: Image.Image, colour: tuple[int, int, int], floor: float = 0.35, gain: float = 1.0) -> Image.Image:
    """Swap the colour, keep the shading. The texture's own contrast is stretched so both
    a black hoodie and a white shirt end up as the same clean colour with visible folds."""
    arr = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb, a = arr[:, :, :3], arr[:, :, 3:4]
    lum = _lum(rgb)
    solid = a[:, :, 0] > 8
    lo, hi = (np.percentile(lum[solid], [5, 95]) if solid.any() else (0.0, 1.0))
    norm = ((lum - lo) / max(hi - lo, 1e-3)).clip(0, 1)
    shade = (floor + norm * gain * (1 - floor))[:, :, None]
    out = np.asarray(colour, dtype=np.float32)[None, None, :] * shade
    return Image.fromarray(np.concatenate([out.clip(0, 255), a], axis=2).astype(np.uint8), "RGBA")


def tint(im: Image.Image, mul: tuple[float, float, float]) -> Image.Image:
    arr = np.asarray(im.convert("RGBA")).astype(np.float32)
    arr[:, :, :3] *= np.asarray(mul, dtype=np.float32)[None, None, :]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def skin(im: Image.Image, spec: tuple[str, tuple]) -> Image.Image:
    mode, value = spec
    return tint(im, value) if mode == "mul" else recolour(im, value, floor=0.55, gain=1.0)


def lighten_beard(face: Image.Image, colour: tuple[int, int, int]) -> Image.Image:
    """The host's beard is painted into the face texture: repaint its dark pixels (lower face only)."""
    arr = np.asarray(face.convert("RGBA")).astype(np.float32)
    lum = _lum(arr[:, :, :3])
    h = arr.shape[0]
    rows = np.arange(h)[:, None] > h * 0.55
    strength = ((0.42 - lum) / 0.25).clip(0, 1) * rows
    target = np.asarray(colour, dtype=np.float32)[None, None, :] * (0.7 + lum[:, :, None] * 0.9).clip(0, 1.1)
    arr[:, :, :3] = arr[:, :, :3] * (1 - strength[:, :, None]) + target * strength[:, :, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


def erase_name(tops: Image.Image) -> Image.Image:
    out = tops.convert("RGBA")
    scale = out.size[0] / 2048
    box = tuple(int(v * scale) for v in NAME_BOX)
    ImageDraw.Draw(out).rectangle(box, fill=out.getpixel((max(0, box[0] - int(30 * scale)), (box[1] + box[3]) // 2)))
    return out


def retint_materials(gltf: dict, spec: dict) -> None:
    """VRoid materials carry their own tint, shade and glow colours on top of the textures
    (the blond sample's hair glows orange). Neutralise them so the new texture colours show true."""
    def unit(rgb, k=1.0):
        return [min(1.0, c / 255 * k) for c in rgb] + [1.0]

    skin_set = spec["skin"][1] if spec["skin"][0] == "set" else None
    by_name = {}
    for mp in gltf.get("extensions", {}).get("VRM", {}).get("materialProperties", []):
        v = mp.setdefault("vectorProperties", {})
        name = mp.get("name", "")
        if "HAIR" in name:
            v["_Color"], v["_ShadeColor"], v["_EmissionColor"] = [1, 1, 1, 1], unit(spec["hair"], 0.62), [0, 0, 0, 1]
        elif "SKIN" in name and skin_set:
            v["_ShadeColor"] = unit(skin_set, 0.78)
        elif "CLOTH" in name:
            v["_ShadeColor"] = [0.8, 0.8, 0.86, 1]
        by_name[name] = v
    for m in gltf.get("materials", []):
        v = by_name.get(m.get("name", ""))
        if v and "HAIR" in m.get("name", ""):
            m.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = [1, 1, 1, 1]
            m["emissiveFactor"] = [0, 0, 0]


def build(name: str, out_dir: Path | None = None) -> Path:
    spec = CAST[name]
    src = MODELS / BASES[spec["base"]]
    if not src.exists():
        raise FileNotFoundError(f"{src.name} is missing (run: python -m services.host.fetch_cast)")
    gltf, bin_chunk = read_glb(src)
    retint_materials(gltf, spec)

    def edit(kind: str, im: Image.Image) -> Image.Image | None:
        if kind == "skin_face":
            im = skin(im, spec["skin"])
            return lighten_beard(im, spec["beard"]) if spec.get("beard") else im
        if kind == "skin_body":
            return skin(im, spec["skin"])
        if kind == "tops":
            return recolour(erase_name(im) if spec["base"] == "host" else im, spec["tops"], floor=0.45)
        if kind in ("bottoms", "accessory") and spec.get(kind):
            return recolour(im, spec[kind], floor=0.45)
        if kind == "hair":
            return recolour(im, spec["hair"], floor=0.3, gain=1.0)
        if kind == "eyes" and spec.get("eyes"):
            return recolour(im, spec["eyes"], floor=0.2, gain=1.3)
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        extract(gltf, bin_chunk, tdir)
        edited = tdir / "edited"
        edited.mkdir()
        for i in range(len(gltf["images"])):
            tex = image_name(gltf, i)
            kind = next((k for k, pattern in TEXTURES.items() if re.search(pattern, tex)), None)
            if kind:
                result = edit(kind, Image.open(next(tdir.glob(f"{i:02d}_*"))))
                if result is not None:
                    result.save(edited / f"{i:02d}_{tex}.png")
        gltf, new_bin = repack(gltf, bin_chunk, edited)
    out = (out_dir or MODELS) / f"{name}.vrm"
    write_glb(out, gltf, new_bin)
    return out


def available() -> list[str]:
    return [n for n, spec in CAST.items() if (MODELS / BASES[spec["base"]]).exists()]


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for n, s in CAST.items():
            print(f"{n:14s} {s['label']:12s} base={s['base']:9s} voice={s['voice']} pitch={s.get('pitch', 1.0)}")
        print("need their own model:", ", ".join(NEEDS_OWN_MODEL))
        return 0
    names = [a for a in argv if not a.startswith("-")] or available()
    for n in names:
        if n not in CAST:
            print(f"unknown character '{n}' (known: {', '.join(CAST)})", file=sys.stderr)
            return 1
        out = build(n)
        print("built", out.name, out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
