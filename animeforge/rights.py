"""Character database and asset rights registry (SQLite).

Every character and every asset (3D model, voice, image, font, music) has a
row saying where it came from, what licence covers it, and whether it may be
used in monetized video, and where. The pipeline asks `require_character`
before casting anyone; a character that is not cleared, or that depends on an
asset that is not cleared, is refused.

    python -m animeforge.rights seed     # register the characters and assets this repo already uses
    python -m animeforge.rights list
    python -m animeforge.rights check arjuna --territory IN

Nothing is assumed free. `rights_basis` must say why a thing may be used and
`evidence` must point at where that was read. These records are our own notes,
not legal advice: no lawyer has reviewed them.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from animeforge.config import settings

RightsStatus = Literal["cleared", "conditional", "pending", "blocked"]
WORLD = "worldwide"


class RightsError(RuntimeError):
    pass


class VoiceProfile(BaseModel):
    """An original voice, described in broad terms. Never a named real person."""

    engine: str = ""
    voice: str = ""
    pitch: float = 1.0
    speed: float = 1.0
    description: str = ""          # age, pitch, accent, pacing, emotional range
    reference_asset: Optional[str] = None  # asset id of a reference clip we own or licensed, if the engine clones


class Asset(BaseModel):
    id: str
    kind: Literal["model3d", "voice", "image", "lora", "font", "music", "sfx", "backdrop"]
    path: str = ""
    source: str = ""               # who made it / where it came from
    source_url: str = ""
    license: str = ""
    rights_status: RightsStatus = "pending"
    rights_basis: str = ""         # why we may use it
    evidence: str = ""             # where that was read
    conditions: list[str] = Field(default_factory=list)
    territories: list[str] = Field(default_factory=lambda: [WORLD])
    attribution: str = ""
    verified_on: str = ""


class Character(BaseModel):
    id: str
    name: str
    kind: Literal["original", "adapted"]   # original = invented here; adapted = taken from an existing work
    source: str = ""                         # for adapted: the work and why it is usable
    rights_status: RightsStatus = "pending"
    rights_basis: str = ""
    conditions: list[str] = Field(default_factory=list)
    territories: list[str] = Field(default_factory=lambda: [WORLD])
    reference_images: list[str] = Field(default_factory=list)
    character_sheet: str = ""
    appearance: str = ""
    personality: str = ""
    voice: VoiceProfile = Field(default_factory=VoiceProfile)
    dialogue_style: str = ""
    clothing: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)   # other character id -> relation
    powers: list[str] = Field(default_factory=list)
    model_refs: dict[str, str] = Field(default_factory=dict)      # e.g. {"vrm": "models/arjuna.vrm", "lora": ""}
    assets: list[str] = Field(default_factory=list)               # asset ids this character depends on
    notes: str = ""


def connect(db: Path | None = None) -> sqlite3.Connection:
    path = db or settings().db
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS characters (id TEXT PRIMARY KEY, kind TEXT NOT NULL, rights_status TEXT NOT NULL, data TEXT NOT NULL, updated TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, kind TEXT NOT NULL, rights_status TEXT NOT NULL, data TEXT NOT NULL, updated TEXT NOT NULL)")
    return con


def _put(table: str, item: BaseModel, db: Path | None) -> None:
    with connect(db) as con:
        con.execute(f"INSERT INTO {table} (id, kind, rights_status, data, updated) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, rights_status=excluded.rights_status, data=excluded.data, updated=excluded.updated",
                    (item.id, item.kind, item.rights_status, item.model_dump_json(), date.today().isoformat()))


def put_asset(asset: Asset, db: Path | None = None) -> None:
    if asset.rights_status in ("cleared", "conditional") and not (asset.rights_basis and asset.evidence):
        raise RightsError(f"asset '{asset.id}' cannot be marked {asset.rights_status} without a rights basis and evidence")
    _put("assets", asset, db)


def put_character(ch: Character, db: Path | None = None) -> None:
    if ch.rights_status in ("cleared", "conditional") and not ch.rights_basis:
        raise RightsError(f"character '{ch.id}' cannot be marked {ch.rights_status} without a rights basis")
    if ch.kind == "adapted" and not ch.source:
        raise RightsError(f"adapted character '{ch.id}' must name its source work")
    _put("characters", ch, db)


def get_asset(asset_id: str, db: Path | None = None) -> Asset | None:
    with connect(db) as con:
        row = con.execute("SELECT data FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return Asset.model_validate_json(row[0]) if row else None


def get_character(char_id: str, db: Path | None = None) -> Character | None:
    with connect(db) as con:
        row = con.execute("SELECT data FROM characters WHERE id = ?", (char_id,)).fetchone()
    return Character.model_validate_json(row[0]) if row else None


def list_characters(db: Path | None = None, kind: str | None = None) -> list[Character]:
    with connect(db) as con:
        rows = con.execute("SELECT data FROM characters" + (" WHERE kind = ?" if kind else "") + " ORDER BY id", (kind,) if kind else ()).fetchall()
    return [Character.model_validate_json(r[0]) for r in rows]


def _allowed(territories: list[str], territory: str) -> bool:
    return WORLD in territories or territory in territories


def why_not(char_id: str, territory: str = WORLD, accept_conditions: bool = False, db: Path | None = None) -> list[str]:
    """Every reason this character may not be cast for that territory. Empty means go."""
    ch = get_character(char_id, db)
    if ch is None:
        return [f"'{char_id}' is not in the character database"]
    out: list[str] = []
    if ch.rights_status in ("pending", "blocked"):
        out.append(f"{ch.name}: rights are {ch.rights_status}" + (f" ({ch.rights_basis})" if ch.rights_basis else ""))
    if ch.rights_status == "conditional" and not accept_conditions:
        out.append(f"{ch.name}: usable only under conditions that have not been accepted: " + " | ".join(ch.conditions))
    if not _allowed(ch.territories, territory):
        out.append(f"{ch.name}: not cleared for {territory} (cleared for {', '.join(ch.territories)})")
    for asset_id in [*ch.assets, *([ch.voice.reference_asset] if ch.voice.reference_asset else [])]:
        a = get_asset(asset_id, db)
        if a is None:
            out.append(f"{ch.name}: depends on asset '{asset_id}', which is not registered")
        elif a.rights_status in ("pending", "blocked"):
            out.append(f"{ch.name}: asset '{asset_id}' is {a.rights_status}")
        elif a.rights_status == "conditional" and not accept_conditions:
            out.append(f"{ch.name}: asset '{asset_id}' has conditions that have not been accepted: " + " | ".join(a.conditions))
        elif not _allowed(a.territories, territory):
            out.append(f"{ch.name}: asset '{asset_id}' is not cleared for {territory}")
    return out


def require_character(char_id: str, territory: str = WORLD, accept_conditions: bool = False, db: Path | None = None) -> Character:
    reasons = why_not(char_id, territory, accept_conditions, db)
    if reasons:
        raise RightsError("cannot cast: " + "; ".join(reasons))
    return get_character(char_id, db)  # type: ignore[return-value]


# ---------------------------------------------------------------- what this repo already uses

PIXIV_CC0 = "pixiv Inc. states the model is CC0 and that it 'has waived all copyright and related or neighboring rights to this model'."
EPIC_CONDITIONS = ["Use only our own design. Never copy a film, TV, game or comic depiction of this character.",
                   "Tell stories from the epic respectfully. Characters worshipped as deities are sacred to living traditions, and laws on offending religious feeling apply in India and elsewhere: review every episode before publishing."]


def seed(db: Path | None = None) -> dict:
    """Register the assets and the epic cast the existing pipeline uses. Safe to run again."""
    from services.host import epic_cast

    today = "2026-11-11"
    assets = [
        Asset(id="vrm-hairsample-male", kind="model3d", path="video-engine/public/models/host.vrm", source="VRoid Project (pixiv Inc.), HairSample_Male", source_url="https://opengameart.org/content/vroid-studio-cc0-models",
              license="CC0", rights_status="cleared", rights_basis=PIXIV_CC0, evidence="https://vroid.pixiv.help/hc/en-us/articles/4402614652569 (lists HairSample_Male under CC0 models); VRM metadata licenseName CC0", verified_on=today),
        Asset(id="vrm-sakurada-fumiriya", kind="model3d", path="video-engine/public/models/fumiriya.vrm", source="VRoid Project (pixiv Inc.), Sakurada Fumiriya", source_url="https://opengameart.org/content/vroid-studio-cc0-models",
              license="CC0", rights_status="cleared", rights_basis=PIXIV_CC0, evidence="https://vroid.pixiv.help/hc/en-us/articles/360014788554-Sakurada-Fumiriya; VRM metadata allows commercial use, modification and redistribution", verified_on=today),
        Asset(id="vrm-sendagaya-shino", kind="model3d", path="video-engine/public/models/shino.vrm", source="VRoid Project (pixiv Inc.), Sendagaya Shino", source_url="https://opengameart.org/content/vroid-studio-cc0-models",
              license="CC0", rights_status="cleared", rights_basis=PIXIV_CC0, evidence="https://vroid.pixiv.help/hc/en-us/articles/360013482714-Sendagaya-Shino; VRM metadata allows commercial use, modification and redistribution", verified_on=today),
        Asset(id="voice-kokoro-hindi", kind="voice", source="Kokoro-82M stock Hindi voices hm_omega, hm_psi, hf_alpha, hf_beta", source_url="https://github.com/hexgrad/kokoro", license="Apache-2.0",
              rights_status="cleared", rights_basis="Stock synthetic voices shipped with an Apache-2.0 model; no real person's voice is cloned by us.", evidence="GitHub API licence field for hexgrad/kokoro: Apache-2.0", verified_on=today),
        Asset(id="font-space-grotesk-inter-jetbrains", kind="font", path="video-engine/public/fonts", source="Space Grotesk, Inter, JetBrains Mono", license="SIL Open Font License",
              rights_status="cleared", rights_basis="OFL fonts may be used in commercial video.", evidence="assets/fonts/OFL-*.txt in this repository", verified_on=today),
        Asset(id="music-ambient-bed", kind="music", path="video-engine/public/music/ambient_bed.wav", source="Generated in-house by services/audio/make_music_bed.py (synthesised oscillators and noise, no samples)", license="own work",
              rights_status="cleared", rights_basis="Made by our own code from scratch; contains no third-party recording.", evidence="services/audio/make_music_bed.py", verified_on=today),
        Asset(id="sfx-pack", kind="sfx", path="video-engine/public/sfx", source="Sound effects shipped with the original insta-bot repository", license="not recorded",
              rights_status="pending", rights_basis="", evidence="", conditions=["Find and record the origin and licence of these files, or replace them."], verified_on=""),
        # AnimeForge GPU pipeline (2026-11-12)
        Asset(id="images-arjunaforge-training", kind="image", path="ada:~/animeforge/out/lora-arjuna-chidiya-ki-aankh/train-arjunaforge (33 pictures; list in training_set.json)",
              source="Drawn by this project with Animagine XL 4.0 and IP-Adapter Plus from our own prompts (animeforge/cluster/lora_set.py); 33 of 64 chosen by eye", license="own work",
              rights_status="conditional", rights_basis="Generated by us from our own text description of an original design; no third-party image was used as input.",
              evidence="candidates.json and selected.txt beside the pictures record every prompt, seed and the choice", conditions=["Output of Animagine XL 4.0: its licence conditions carry over."], verified_on="2026-11-12"),
        Asset(id="lora-arjunaforge", kind="lora", path="ada:~/animeforge/loras/arjunaforge-step00000800.safetensors (copy on share6)",
              source="Trained by this project with Kohya sd-scripts v0.12.3 on images-arjunaforge-training", license="own work on Animagine XL 4.0",
              rights_status="conditional", rights_basis="Trained only on pictures we generated ourselves; the base checkpoint's licence governs use.",
              evidence="animeforge/cluster/lora_train.sbatch; benchmark in animeforge/registry/models.json (kohya-sd-scripts)", conditions=["Inherits the Animagine XL 4.0 licence conditions."], verified_on="2026-11-12"),
        Asset(id="voice-chatterbox-builtin-hi", kind="voice", source="Chatterbox Multilingual built-in voice, Hindi, no reference clip", source_url="https://github.com/resemble-ai/chatterbox", license="MIT",
              rights_status="cleared", rights_basis="Stock synthetic voice of an MIT model; we give it no reference recording, so no person's voice is cloned by us. Output carries the PerTh watermark.",
              evidence="animeforge/registry/models.json (chatterbox-multilingual)", verified_on="2026-11-12"),
        Asset(id="font-noto-sans-devanagari", kind="font", path="assets/fonts/NotoSansDevanagari.ttf", source="Noto Sans Devanagari (Google)", license="SIL Open Font License",
              rights_status="cleared", rights_basis="OFL fonts may be used in commercial video.", evidence="assets/fonts/NotoSansDevanagari-OFL.txt", verified_on="2026-11-12"),
    ]
    for a in assets:
        put_asset(a, db)
    base_asset = {"host": "vrm-hairsample-male", "fumiriya": "vrm-sakurada-fumiriya", "shino": "vrm-sendagaya-shino"}
    ramayana = {"rama", "lakshmana", "ravana"}
    lore = {"narada", "parashurama", "durga", "kali"}
    count = 0
    for name, spec in epic_cast.CAST.items():
        work = "Ramayana" if name in ramayana else "Hindu mythology (Puranas and the epics)" if name in lore else "Mahabharata"
        put_character(Character(
            id=name, name=spec["label"], kind="adapted", source=f"{work}: an ancient work in the public domain",
            rights_status="conditional", rights_basis="The character comes from an ancient public-domain text; the visual design is ours, built on a CC0 base model; the voice is a stock synthetic voice.",
            conditions=EPIC_CONDITIONS,
            appearance=f"Stylised anime figure on the '{spec['base']}' base model; palette and costume in services/host/epic_cast.py and video-engine/src/design/epicCast.ts.",
            voice=VoiceProfile(engine="kokoro", voice=spec["voice"], pitch=spec.get("pitch", 1.0), speed=spec.get("speed", 1.0), description="Stock synthetic Hindi voice, pitch-shifted to suit the character."),
            clothing="See the costume entry for this name in video-engine/src/design/epicCast.ts.",
            model_refs={"vrm": f"models/{name}.vrm"}, assets=[base_asset[spec["base"]], "voice-kokoro-hindi"],
            notes="No legal review has been done. Personality, relationships and powers are not filled in yet."), db)
        count += 1
    return {"assets": len(assets), "characters": count}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    cmd = args[0] if args else "list"
    if cmd == "seed":
        print(json.dumps(seed()))
    elif cmd == "check" and len(args) > 1:
        territory = args[args.index("--territory") + 1] if "--territory" in args else WORLD
        reasons = why_not(args[1], territory, accept_conditions="--accept-conditions" in args)
        print("OK to cast" if not reasons else "NOT cleared:\n  " + "\n  ".join(reasons))
        return 1 if reasons else 0
    else:
        for c in list_characters():
            print(f"{c.id:14s} {c.kind:9s} {c.rights_status:11s} {c.source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
