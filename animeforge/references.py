"""Permanent character reference sheets, and the check that a sheet is complete.

A character's look is fixed by a reference folder and a `character.json`:

    data/animeforge/characters/<id>/
        character.json        identity, defining attributes, palette, rights
        front.png             front-facing
        side.png              side profile
        three_quarter.png     three-quarter view
        full_body.png         full body
        expressions.png       facial expression sheet
        costume.png           costume
        ornaments.png         ornaments and jewellery
        poses.png             pose reference
        lora/                 optional character LoRA and its training record

    python -m animeforge.references check <id>      # is the sheet complete and consistent?
    python -m animeforge.references new <id> "Name" # start a sheet from the template

No shot may be generated for a character whose sheet fails this check. The
`defining` block lists what must never change between scenes (skin colour,
number of arms, crown, weapon...). A scene may override one only by naming it
in `story_reason`, and `diff_defining` reports any other change as an error.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from animeforge.config import settings

VIEWS = {"front": "front-facing reference", "side": "side profile", "three_quarter": "three-quarter view", "full_body": "full-body reference",
         "expressions": "facial expression sheet", "costume": "costume reference", "ornaments": "ornament reference", "poses": "pose reference"}
MIN_SIDE = 768
REQUIRED_FIELDS = ("id", "name", "kind", "source", "rights_status", "rights_basis", "defining", "palette", "appearance")
DEFINING_KEYS = ("skin", "hair", "eyes", "arms", "build", "costume", "ornaments", "attributes")

TEMPLATE = {
    "id": "", "name": "", "kind": "adapted | original", "source": "the work this character comes from, or 'invented for this channel'",
    "rights_status": "pending", "rights_basis": "why this character and this design may be used",
    "appearance": "one paragraph: age, build, face, bearing",
    "defining": {"skin": "", "hair": "", "eyes": "", "arms": 2, "build": "", "costume": "", "ornaments": [], "attributes": []},
    "palette": {"skin": "#", "hair": "#", "primary": "#", "secondary": "#", "metal": "#", "aura": "#"},
    "expressions": ["neutral", "serene", "joyful", "stern", "wrathful", "compassionate", "surprised", "sorrowful"],
    "visual_direction": "traditional devotional painting | 3D cinematic | stylised anime | epic fantasy",
    "do_not": ["copy any film, TV, game or comic design", "change a defining attribute without a story reason"],
    "lora": {"file": "", "base_checkpoint": "", "trained_on": "only images we made or own", "trigger": ""},
}


def character_dir(char_id: str, root: Path | None = None) -> Path:
    return (root or settings().home / "characters") / char_id


def png_size(path: Path) -> tuple[int, int] | None:
    """Width and height from the PNG header, without loading the image."""
    with path.open("rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def check(char_id: str, root: Path | None = None) -> list[str]:
    """Every reason the reference sheet is not ready for shot generation."""
    d = character_dir(char_id, root)
    spec_file = d / "character.json"
    if not spec_file.exists():
        return [f"no character.json in {d}"]
    try:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"character.json is not valid JSON: {exc}"]
    out: list[str] = []
    for key in REQUIRED_FIELDS:
        if not spec.get(key):
            out.append(f"character.json: '{key}' is empty")
    if spec.get("id") and spec["id"] != char_id:
        out.append(f"character.json id '{spec['id']}' does not match the folder '{char_id}'")
    if spec.get("kind") not in ("adapted", "original"):
        out.append("character.json: kind must be 'adapted' or 'original'")
    if spec.get("rights_status") not in ("cleared", "conditional"):
        out.append(f"rights are '{spec.get('rights_status')}': clear the character before making shots")
    defining = spec.get("defining") or {}
    for key in DEFINING_KEYS:
        if key not in defining or defining[key] in ("", None):
            out.append(f"defining.{key} is not set")
    if not isinstance(defining.get("arms"), int) or defining.get("arms", 0) < 2 or defining.get("arms", 0) % 2:
        out.append("defining.arms must be an even whole number of 2 or more")
    for name, colour in (spec.get("palette") or {}).items():
        if not (isinstance(colour, str) and len(colour) == 7 and colour[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in colour[1:])):
            out.append(f"palette.{name} is not a #RRGGBB colour")
    for view, label in VIEWS.items():
        img = d / f"{view}.png"
        if not img.exists():
            out.append(f"missing {label} ({view}.png)")
            continue
        size = png_size(img)
        if size is None:
            out.append(f"{view}.png is not a PNG image")
        elif min(size) < MIN_SIDE:
            out.append(f"{view}.png is {size[0]}x{size[1]}; the short side must be at least {MIN_SIDE}px")
    return out


def diff_defining(spec: dict, shot: dict) -> list[str]:
    """A shot may restate defining attributes. Any that differ must be listed in the shot's `story_reason`."""
    allowed = set((shot.get("story_reason") or {}).keys())
    out = []
    for key, value in (shot.get("defining") or {}).items():
        base = (spec.get("defining") or {}).get(key)
        if value != base and key not in allowed:
            out.append(f"shot changes defining.{key} from {base!r} to {value!r} without a story reason")
    return out


def new(char_id: str, name: str, root: Path | None = None) -> Path:
    d = character_dir(char_id, root)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "character.json"
    if f.exists():
        raise FileExistsError(f"{f} already exists")
    f.write_text(json.dumps({**TEMPLATE, "id": char_id, "name": name}, indent=1), encoding="utf-8")
    return f


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) >= 2 and args[0] == "check":
        problems = check(args[1])
        print("reference sheet complete" if not problems else "NOT ready:\n  " + "\n  ".join(problems))
        return 1 if problems else 0
    if len(args) >= 3 and args[0] == "new":
        print("created", new(args[1], args[2]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
