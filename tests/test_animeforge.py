"""AnimeForge Phase 1: licence gate, storage guard, rights database, reference sheets, audit verdict, shot QA."""
from __future__ import annotations

import json
import struct
import subprocess
import zlib
from pathlib import Path

import numpy as np
import pytest

from animeforge import audit, references, registry, rights, shotqa, storage
from animeforge.config import settings


# ---------------------------------------------------------------- model licence registry

def test_registry_is_well_formed_and_records_no_unmeasured_benchmarks():
    models = registry.load()
    assert registry.problems(models) == []
    for mid in ("wan2.1", "wan2.2-animate", "wan2.2-fun-control", "ltx-video", "animatediff", "indicf5", "indic-parler-tts", "chatterbox-multilingual", "indic-speak",
                "latentsync", "musetalk", "wav2lip", "comfyui", "ipadapter-plus", "pulid", "controlnet-union-sdxl", "kohya-sd-scripts", "blender", "remotion", "ffmpeg"):
        assert mid in models, mid
    # a benchmark is a record of a real run: GPU ones must say when and on which card
    cpu = {"kokoro", "remotion"}
    for m in models.values():
        if m["benchmark"] and m["id"] not in cpu:
            assert m["benchmark"].get("date") and "RTX 3090" in m["benchmark"].get("gpu", ""), m["id"]
    # models that were never run on the GPU must not carry numbers
    for mid in ("wan2.1", "wan2.2-animate", "wan2.2-fun-control", "ltx-video", "animatediff", "latentsync", "musetalk"):
        assert not models[mid]["benchmark"], mid


def test_blocked_and_unverified_models_are_refused_and_there_is_no_fallback():
    with pytest.raises(registry.LicenceError, match="blocked"):
        registry.require("wav2lip")
    with pytest.raises(registry.LicenceError, match="blocked"):
        registry.require("insightface-models")
    with pytest.raises(registry.LicenceError, match="not been cleared"):
        registry.require("ltx-video")
    with pytest.raises(registry.LicenceError, match="not in the model registry"):
        registry.require("some-new-model")
    assert registry.require("wan2.1")["weight_license"] == "Apache-2.0"


def test_conditional_models_need_their_conditions_acknowledged():
    with pytest.raises(registry.LicenceError, match="ANIMEFORGE_ACK"):
        registry.require("wan2.2-animate")
    entry = registry.require("wan2.2-animate", acknowledged=["wan2.2-animate"])
    assert "80 GB" in " ".join(entry["conditions"]) and "67.4 GB" in entry["checkpoint"]
    assert settings({"ANIMEFORGE_ACK": "comfyui, wan2.2-animate"}).acknowledged == ("comfyui", "wan2.2-animate")


def test_registry_problems_catch_a_bad_entry():
    bad = {"x": {"id": "x", "status": "conditional", "conditions": [], "sources": []}}
    found = registry.problems(bad)
    assert any("missing field" in p for p in found) and any("must list its conditions" in p for p in found) and any("cite where" in p for p in found)


# ---------------------------------------------------------------- storage guard

def test_download_is_refused_when_it_would_eat_the_reserve(tmp_path):
    assert storage.ensure_space(tmp_path / "models" / "not-yet-there", need_gb=67.4, what="Wan 2.2 Animate", reserve_gb=20, free=100.0) == pytest.approx(32.6)
    with pytest.raises(storage.StorageError, match=r"needs 67.4 GB.*has 80.0 GB free.*20 GB must stay free"):
        storage.ensure_space(tmp_path, need_gb=67.4, what="Wan 2.2 Animate", reserve_gb=20, free=80.0)
    with pytest.raises(ValueError):
        storage.ensure_space(tmp_path, need_gb=-1, free=10)
    assert storage.free_gb(tmp_path / "a" / "b" / "c") > 0  # checks the nearest folder that exists


# ---------------------------------------------------------------- rights database

def test_seed_registers_the_cast_as_adapted_and_conditional(tmp_path):
    db = tmp_path / "af.sqlite"
    assert rights.seed(db) == {"assets": 7, "characters": 16}
    krishna = rights.get_character("krishna", db)
    assert krishna.kind == "adapted" and "Mahabharata" in krishna.source and krishna.rights_status == "conditional"
    assert krishna.assets == ["vrm-sakurada-fumiriya", "voice-kokoro-hindi"] and krishna.voice.voice == "hm_psi"
    assert rights.get_character("rama", db).source.startswith("Ramayana")
    assert len(rights.list_characters(db, kind="adapted")) == 16 and rights.list_characters(db, kind="original") == []
    assert rights.seed(db) == {"assets": 7, "characters": 16}  # running it again changes nothing


def test_casting_needs_cleared_rights_territory_and_cleared_assets(tmp_path):
    db = tmp_path / "af.sqlite"
    rights.seed(db)
    with pytest.raises(rights.RightsError, match="conditions that have not been accepted"):
        rights.require_character("arjuna", "IN", db=db)
    assert rights.require_character("arjuna", "IN", accept_conditions=True, db=db).name == "Arjun"
    assert rights.why_not("gandalf", db=db) == ["'gandalf' is not in the character database"]
    rights.put_asset(rights.Asset(id="voice-clone", kind="voice", rights_status="pending"), db)
    rights.put_character(rights.Character(id="hero", name="Hero", kind="original", rights_status="cleared", rights_basis="Invented for this channel.", territories=["IN"],
                                          voice=rights.VoiceProfile(reference_asset="voice-clone"), assets=["sfx-pack"]), db)
    reasons = rights.why_not("hero", "US", db=db)
    assert any("not cleared for US" in r for r in reasons) and any("'voice-clone' is pending" in r for r in reasons) and any("'sfx-pack' is pending" in r for r in reasons)


def test_nothing_is_marked_usable_without_a_stated_basis(tmp_path):
    db = tmp_path / "af.sqlite"
    with pytest.raises(rights.RightsError, match="without a rights basis"):
        rights.put_character(rights.Character(id="x", name="X", kind="original", rights_status="cleared"), db)
    with pytest.raises(rights.RightsError, match="must name its source work"):
        rights.put_character(rights.Character(id="x", name="X", kind="adapted", rights_status="pending"), db)
    with pytest.raises(rights.RightsError, match="rights basis and evidence"):
        rights.put_asset(rights.Asset(id="a", kind="image", rights_status="cleared", rights_basis="trust me"), db)


# ---------------------------------------------------------------- character reference sheets

def png(path: Path, w: int, h: int) -> None:
    raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def complete_sheet(root: Path, char_id: str = "durga") -> Path:
    references.new(char_id, "Durga", root)
    d = references.character_dir(char_id, root)
    spec = json.loads((d / "character.json").read_text(encoding="utf-8"))
    spec.update(kind="adapted", source="Hindu mythology, public domain", rights_status="conditional", rights_basis="Ancient tradition; our own design.", appearance="Serene warrior goddess.",
                defining={"skin": "golden", "hair": "long black", "eyes": "dark brown", "arms": 8, "build": "tall", "costume": "red sari with gold border", "ornaments": ["crown", "necklace"], "attributes": ["trident", "lion"]},
                palette={"skin": "#E8B27A", "hair": "#1A1820", "primary": "#C8102E", "secondary": "#FFC83D", "metal": "#FFC83D", "aura": "#FFE9A8"})
    (d / "character.json").write_text(json.dumps(spec), encoding="utf-8")
    for view in references.VIEWS:
        png(d / f"{view}.png", 800, 1000)
    return d


def test_a_fresh_sheet_lists_everything_that_is_missing(tmp_path):
    references.new("durga", "Durga", tmp_path)
    problems = references.check("durga", tmp_path)
    assert any("missing front-facing reference" in p for p in problems) and any("missing facial expression sheet" in p for p in problems)
    assert any("rights are 'pending'" in p for p in problems) and any("defining.arms" in p or "defining.skin" in p for p in problems)
    assert references.check("nobody", tmp_path)[0].startswith("no character.json")


def test_a_complete_sheet_passes_and_small_or_fake_images_fail(tmp_path):
    d = complete_sheet(tmp_path)
    assert references.check("durga", tmp_path) == []
    png(d / "side.png", 400, 500)
    (d / "poses.png").write_bytes(b"not an image")
    problems = references.check("durga", tmp_path)
    assert any("side.png is 400x500" in p for p in problems) and any("poses.png is not a PNG" in p for p in problems)


def test_a_shot_may_not_change_a_defining_attribute_without_a_story_reason(tmp_path):
    spec = json.loads((complete_sheet(tmp_path) / "character.json").read_text(encoding="utf-8"))
    assert references.diff_defining(spec, {"defining": {"arms": 8}}) == []
    assert references.diff_defining(spec, {"defining": {"arms": 4}}) == ["shot changes defining.arms from 8 to 4 without a story reason"]
    assert references.diff_defining(spec, {"defining": {"arms": 2}, "story_reason": {"arms": "she appears in mortal disguise"}}) == []


# ---------------------------------------------------------------- audit verdict

def machine(gpus, ram=64.0, cuda=True, free=400.0):
    return {"gpus": gpus, "ram_gb": ram, "torch": {"torch": "2", "cuda": cuda}, "disks": [{"drive": "D:", "free_gb": free, "total_gb": 1000, "used_for": ["models"]}]}


def test_verdict_says_plainly_what_a_machine_cannot_do():
    laptop = audit.verdict(machine([{"name": "Intel UHD Graphics 770", "vendor": "other", "vram_gb": None}], ram=15.7, cuda=False, free=165.0))
    assert laptop["gpu_ready"] is False and any("no NVIDIA GPU" in g for g in laptop["gaps"]) and any("15.7 GB RAM" in g for g in laptop["gaps"])
    assert any("Phase 4" in x for x in laptop["needs_gpu"]) and any("Kokoro" in x for x in laptop["can_run_here"])
    small = audit.verdict(machine([{"name": "RTX 3060", "vendor": "NVIDIA", "vram_gb": 12.0}]))
    assert small["gpu_ready"] is False and "12.0 GB VRAM" in small["gaps"][0]
    target = audit.verdict(machine([{"name": "RTX 3090", "vendor": "NVIDIA", "vram_gb": 24.0}]))
    assert target == {**target, "gpu_ready": True, "gaps": [], "needs_gpu": []}


# ---------------------------------------------------------------- shot QA (real FFmpeg, tiny synthetic clips)

def clip(path: Path, frames: np.ndarray, fps: int = 16) -> Path:
    """Encode greyscale frames (n, h, w) losslessly enough for measurement."""
    n, h, w = frames.shape
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)],
                       input=frames.astype(np.uint8).tobytes(), capture_output=True)
    assert p.returncode == 0, p.stderr.decode()[:300]
    return path


def moving(n: int = 48, w: int = 96, h: int = 160) -> np.ndarray:
    """A bright bar sliding steadily across a mid-grey frame."""
    f = np.full((n, h, w), 90, dtype=np.float32)
    for i in range(n):
        f[i, :, (i * 2) % (w - 12): (i * 2) % (w - 12) + 12] = 200
    return f


def test_a_clean_moving_shot_passes_the_measured_checks_and_gets_a_contact_sheet(tmp_path):
    rep = shotqa.evaluate(clip(tmp_path / "ok.mp4", moving()), seconds=3.0, width=96, height=160, fps=16)
    assert rep.measured_ok, [(c.name, c.detail) for c in rep.checks if not c.passed]
    assert Path(rep.contact_sheet).exists() and rep.approved is False  # measured is not approved: a person has not looked yet
    rep.reviewed_by = "nishanth"
    assert rep.approved is True and "number of limbs" in rep.review


def test_freeze_flicker_and_a_popped_frame_are_each_caught(tmp_path):
    frozen = moving()
    frozen[20:] = frozen[20]
    assert not next(c for c in shotqa.evaluate(clip(tmp_path / "freeze.mp4", frozen)).checks if c.name == "no_freeze").passed
    flick = moving()
    flick[10] += 45
    flick[30] += 45
    assert not next(c for c in shotqa.evaluate(clip(tmp_path / "flicker.mp4", flick)).checks if c.name == "no_flicker").passed
    popped = moving()
    popped[25] = np.random.default_rng(1).integers(0, 255, popped[25].shape)
    assert not next(c for c in shotqa.evaluate(clip(tmp_path / "pop.mp4", popped)).checks if c.name == "no_popped_frames").passed
    still = np.full((32, 160, 96), 120, dtype=np.float32)
    assert not next(c for c in shotqa.evaluate(clip(tmp_path / "still.mp4", still)).checks if c.name == "moves").passed
    wrong = shotqa.evaluate(clip(tmp_path / "ok.mp4", moving()), seconds=5.0, width=1080, height=1920)
    assert {c.name for c in wrong.checks if not c.passed} == {"duration", "resolution"}
