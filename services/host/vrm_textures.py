"""Extract, edit and repack the textures of a VRM (glTF binary) avatar.

    python -m services.host.vrm_textures list   <model.vrm>
    python -m services.host.vrm_textures extract <model.vrm> <out_dir>
    python -m services.host.vrm_textures repack  <model.vrm> <edited_dir> <out.vrm>

`extract` writes every image as <index>_<name>.png; `repack` replaces any image
whose file exists in <edited_dir> and rebuilds the binary chunk with new
offsets. Nothing else in the model changes. Standard library only.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

MAGIC = b"glTF"


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == MAGIC, "not a GLB/VRM file"
    off = 12
    gltf: dict | None = None
    bin_chunk = b""
    while off < length:
        clen, ctype = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off : off + clen]
        off += clen
        if ctype == b"JSON":
            gltf = json.loads(chunk.decode("utf-8"))
        elif ctype == b"BIN\x00":
            bin_chunk = chunk
    assert gltf is not None
    return gltf, bin_chunk


def write_glb(path: Path, gltf: dict, bin_chunk: bytes) -> None:
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    bb = bin_chunk + b"\x00" * ((4 - len(bin_chunk) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(bb)
    with path.open("wb") as f:
        f.write(struct.pack("<4sII", MAGIC, 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON"))
        f.write(js)
        f.write(struct.pack("<I4s", len(bb), b"BIN\x00"))
        f.write(bb)


def image_name(gltf: dict, i: int) -> str:
    img = gltf["images"][i]
    name = img.get("name") or f"image{i}"
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def list_images(gltf: dict) -> list[dict]:
    out = []
    mats = gltf.get("materials", [])
    tex_to_mat: dict[int, list[str]] = {}
    for m in mats:
        refs = []
        pbr = m.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr:
            refs.append(pbr["baseColorTexture"]["index"])
        for key in ("emissiveTexture", "normalTexture"):
            if key in m:
                refs.append(m[key]["index"])
        for t in refs:
            tex_to_mat.setdefault(t, []).append(m.get("name", "?"))
    tex_to_img = {ti: t.get("source") for ti, t in enumerate(gltf.get("textures", []))}
    for i, img in enumerate(gltf["images"]):
        bv = gltf["bufferViews"][img["bufferView"]]
        mats_using = sorted({m for ti, src in tex_to_img.items() if src == i for m in tex_to_mat.get(ti, [])})
        out.append({"index": i, "name": image_name(gltf, i), "bytes": bv["byteLength"], "mime": img.get("mimeType"), "materials": mats_using})
    return out


def extract(gltf: dict, bin_chunk: bytes, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(gltf["images"]):
        bv = gltf["bufferViews"][img["bufferView"]]
        blob = bin_chunk[bv["byteOffset"] : bv["byteOffset"] + bv["byteLength"]]
        ext = ".png" if img.get("mimeType") == "image/png" else ".jpg"
        (out_dir / f"{i:02d}_{image_name(gltf, i)}{ext}").write_bytes(blob)


def repack(gltf: dict, bin_chunk: bytes, edited_dir: Path) -> tuple[dict, bytes]:
    replacements: dict[int, bytes] = {}
    for i, img in enumerate(gltf["images"]):
        for ext in (".png", ".jpg"):
            f = edited_dir / f"{i:02d}_{image_name(gltf, i)}{ext}"
            if f.exists():
                replacements[img["bufferView"]] = f.read_bytes()
                img["mimeType"] = "image/png" if ext == ".png" else "image/jpeg"
    new_bin = bytearray()
    for bi, bv in enumerate(gltf["bufferViews"]):
        blob = replacements.get(bi) or bin_chunk[bv["byteOffset"] : bv["byteOffset"] + bv["byteLength"]]
        pad = (4 - len(new_bin) % 4) % 4
        new_bin += b"\x00" * pad
        bv["byteOffset"] = len(new_bin)
        bv["byteLength"] = len(blob)
        new_bin += blob
    gltf["buffers"][0]["byteLength"] = len(new_bin)
    return gltf, bytes(new_bin)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "list":
        gltf, _ = read_glb(Path(argv[1]))
        for row in list_images(gltf):
            print(json.dumps(row))
        return 0
    if cmd == "extract":
        gltf, bin_chunk = read_glb(Path(argv[1]))
        extract(gltf, bin_chunk, Path(argv[2]))
        print("extracted", len(gltf["images"]), "images to", argv[2])
        return 0
    if cmd == "repack":
        gltf, bin_chunk = read_glb(Path(argv[1]))
        gltf, new_bin = repack(gltf, bin_chunk, Path(argv[2]))
        write_glb(Path(argv[3]), gltf, new_bin)
        print("wrote", argv[3], Path(argv[3]).stat().st_size, "bytes")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
