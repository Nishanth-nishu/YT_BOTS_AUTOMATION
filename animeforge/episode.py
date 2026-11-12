"""An AnimeForge episode: a list of five-second shots with one Hindi line each.

    python -m animeforge.episode check <id>       # rules, rights and licences
    python -m animeforge.episode produce <id>     # cluster job, fetch, assemble, QA
    python -m animeforge.episode assemble <id>    # re-cut from shots already fetched

The episode file is animeforge/cluster/episodes/<id>.json. The GPU work runs
on the cluster (`animeforge.slurm`); cutting, subtitles and QA run here with
ffmpeg.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel, Field

from animeforge import log, registry, rights, shotqa, slurm
from animeforge.config import ROOT, settings

EPISODES = Path(__file__).parent / "cluster" / "episodes"
FONT = ROOT / "assets" / "fonts" / "NotoSansDevanagari.ttf"
SHOT_SECONDS = 121 / 24
MODELS = ("animagine-xl-4", "ipadapter-plus", "wan2.2-ti2v-5b", "chatterbox-multilingual", "whisper-large-v3")
ACK = ("animagine-xl-4", "ipadapter-plus", "chatterbox-multilingual")
# Names that would steer the image model to someone else's design.
FORBIDDEN = ("naruto", "goku", "pokemon", "ghibli", "disney", "marvel", "one piece", "demon slayer", "artist:", "style of")
MAX_CER = 0.25


class CharacterLook(BaseModel):
    id: str
    tags: str
    reference_seed: int = 11
    reference_scene: str = "upper body, simple background, looking at viewer"


class Shot(BaseModel):
    id: str
    subject: str                      # tags for the still
    motion: str                       # sentence for the video model
    line: str = ""                    # Hindi, Devanagari
    use_reference: bool = True
    seed: int | None = None
    continues: bool = False           # same scene: start from the previous clip's last frame, and cut without a fade


class EpisodeSpec(BaseModel):
    id: str
    title: str
    source: str = ""
    character: CharacterLook
    shots: list[Shot] = Field(min_length=1)
    steps: int = 50
    reference_scale: float = 0.6
    caption: str = ""
    crossfade: float = 0.4            # seconds of dissolve between scenes; 0 for hard cuts
    lora: str = ""                    # file name under ~/animeforge/loras on the cluster
    lora_scale: float = 0.9
    lora_trigger: str = ""            # word the LoRA was trained on; added to shots that use the reference
    hashtags: list[str] = Field(default_factory=list)


def load(ep_id: str) -> EpisodeSpec:
    return EpisodeSpec.model_validate_json((EPISODES / f"{ep_id}.json").read_text(encoding="utf-8"))


def check(spec: EpisodeSpec, db: Path | None = None) -> list[str]:
    """Everything that must be true before GPU time is spent."""
    bad: list[str] = []
    ids = [s.id for s in spec.shots]
    if len(set(ids)) != len(ids):
        bad.append("shot ids repeat")
    for s in spec.shots:
        if not slurm.SAFE.match(s.id):
            bad.append(f"{s.id}: id must be letters, digits, dot, dash, underscore")
        text = f"{s.subject} {s.motion} {spec.character.tags}".lower()
        for word in FORBIDDEN:
            if word in text:
                bad.append(f"{s.id}: prompt names {word.strip()!r}; prompts describe only our own designs")
        if s.line and not any("ऀ" <= c <= "ॿ" for c in s.line):
            bad.append(f"{s.id}: the line is not in Devanagari")
        if len(s.line.split()) > 16:
            bad.append(f"{s.id}: line has {len(s.line.split())} words; a five-second shot holds about 16")
        if "original" not in s.subject.lower():
            bad.append(f"{s.id}: subject must carry the 'original' tag")
    if spec.shots[0].continues:
        bad.append(f"{spec.shots[0].id}: the first shot has nothing to continue from")
    if spec.lora and not slurm.SAFE.match(spec.lora):
        bad.append("lora: file name must be letters, digits, dot, dash, underscore")
    if spec.lora:
        try:
            registry.require("kohya-sd-scripts", acknowledged=(*ACK, "kohya-sd-scripts"))
        except registry.LicenceError as e:
            bad.append(f"model kohya-sd-scripts: {str(e).splitlines()[0]}")
    bad += [f"character: {p}" for p in rights.why_not(spec.character.id, accept_conditions=True, db=db)]
    for m in MODELS:
        try:
            registry.require(m, acknowledged=ACK)
        except registry.LicenceError as e:
            bad.append(f"model {m}: {str(e).splitlines()[0]}")
    return bad


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def timeline(spec: EpisodeSpec, folder: Path, lead: float = 0.3, tail: float = 0.4) -> list[dict]:
    """Each shot lasts its clip, or longer when its line needs more time."""
    t, rows = 0.0, []
    for s in spec.shots:
        v = folder / s.id / "voice.wav"
        voice = wav_seconds(v) if v.exists() else 0.0
        dur = round(max(SHOT_SECONDS, lead + voice + tail), 3)
        rows.append({"id": s.id, "start": round(t, 3), "duration": dur, "voice": round(voice, 3),
                     "voice_at": round(t + lead, 3), "line": s.line})
        t += dur
    return rows


def ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def subtitles(rows: list[dict]) -> str:
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: hi,Noto Sans Devanagari,64,&H00FFFFFF,&H00101010,&H80000000,1,1,4,1,2,40,40,170,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Text\n")
    lines = [f"Dialogue: 0,{ass_time(r['voice_at'] - 0.1)},{ass_time(r['voice_at'] + r['voice'] + 0.25)},hi,{r['line']}"
             for r in rows if r["line"] and r["voice"] > 0]
    return head + "\n".join(lines) + "\n"


def assemble(spec: EpisodeSpec, folder: Path, out: Path, run=subprocess.run) -> dict:
    """Cut the shots together with voices and burned-in Hindi subtitles (720x1280, 24 fps)."""
    rows = timeline(spec, folder)
    work = folder / "_cut"
    work.mkdir(exist_ok=True)
    shutil.copy(FONT, work / FONT.name)
    (work / "subs.ass").write_text(subtitles(rows), encoding="utf-8")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for r in rows:
        cmd += ["-i", str((folder / r["id"] / "shot.mp4").resolve())]
    voiced = [r for r in rows if r["voice"] > 0]
    for r in voiced:
        cmd += ["-i", str((folder / r["id"] / "voice.wav").resolve())]
    fc = []
    # Shot i dissolves into shot i+1 over fades[i] seconds; a shot that continues the scene is a
    # plain cut (one frame). Each clip is held that much longer, so the timeline does not shrink.
    frame = 1 / 24
    fades = [frame if (spec.shots[i + 1].continues or spec.crossfade <= frame) else spec.crossfade
             for i in range(len(rows) - 1)] + [0.0]
    for i, r in enumerate(rows):
        length = r["duration"] + fades[i]
        hold = max(0.0, length - SHOT_SECONDS)
        fc.append(f"[{i}:v]fps=24,scale=720:-2,crop=720:1280,setsar=1,tpad=stop_mode=clone:stop_duration={hold:.3f},"
                  f"trim=duration={length:.3f},setpts=PTS-STARTPTS[v{i}]")
    last = "v0"
    for i in range(1, len(rows)):
        fc.append(f"[{last}][v{i}]xfade=transition=fade:duration={fades[i - 1]:.3f}:offset={rows[i]['start']:.3f}[x{i}]")
        last = f"x{i}"
    fc.append(f"[{last}]null[vc]")
    fc.append("[vc]subtitles=subs.ass:fontsdir=.[vout]")
    total = sum(r["duration"] for r in rows)
    amap = []
    if voiced:
        for k, r in enumerate(voiced):
            ms = int(r["voice_at"] * 1000)
            fc.append(f"[{len(rows) + k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{k}]")
        fc.append("".join(f"[a{k}]" for k in range(len(voiced)))
                  + f"amix=inputs={len(voiced)}:normalize=0,apad,atrim=duration={total:.3f},loudnorm=I=-16:TP=-1.5[aout]")
        amap = ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", *amap, "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24", "-movflags", "+faststart", str(out.resolve())]
    run(cmd, check=True, cwd=work)
    return {"video": str(out), "seconds": round(total, 2), "shots": rows}


def review(spec: EpisodeSpec, folder: Path, final: Path) -> dict:
    """Measured checks only. Looking at the contact sheets is still a person's job."""
    shots = []
    for s in spec.shots:
        rep = shotqa.evaluate(folder / s.id / "shot.mp4", seconds=SHOT_SECONDS, width=704, height=1280, fps=24)
        shots.append({"id": s.id, "measured_ok": rep.measured_ok, "contact_sheet": rep.contact_sheet,
                      "failed": [asdict(c) for c in rep.checks if not c.passed]})
    voice = []
    vr = folder / "voice_report.json"
    if vr.exists():
        for r in json.loads(vr.read_text(encoding="utf-8"))["lines"]:
            voice.append({**r, "ok": r["cer"] <= MAX_CER})
    info = shotqa.probe(final)
    has_audio = "audio" in subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(final)],
        capture_output=True, text=True).stdout
    return {"final": {"seconds": round(info["duration"], 2), "width": info["width"], "height": info["height"],
                      "fps": info["fps"], "has_audio": has_audio},
            "shots": shots, "voice": voice,
            "measured_ok": all(s["measured_ok"] for s in shots) and all(v["ok"] for v in voice) and has_audio,
            "human_review": "pending: open each contact sheet and compare with reference.png"}


def produce(ep_id: str, fetch_only: bool = False) -> dict:
    spec = load(ep_id)
    bad = check(spec)
    if bad:
        from animeforge.jobs import Permanent

        raise Permanent("episode refused:\n  " + "\n  ".join(bad))
    folder = settings().home / "episodes" / ep_id
    result: dict = {"episode": ep_id}
    if not fetch_only:
        slurm.push_source()
        jid = slurm.submit("episode.sbatch", {"EPISODE_ID": ep_id})
        log.event("episode.submitted", episode=ep_id, slurm_job=jid)
        final_state = slurm.wait(jid, timeout_s=7 * 3600)
        result["slurm_job"], result["state"] = jid, final_state
        if final_state != "COMPLETED":
            raise RuntimeError(f"cluster job {jid} ended {final_state}:\n{slurm.log_tail('episode', jid)}")
    if folder.exists():
        shutil.rmtree(folder)
    slurm.fetch(ep_id, folder)
    final = ROOT / "output" / "animeforge" / f"{ep_id}.mp4"
    result["cut"] = assemble(spec, folder, final)
    result["qa"] = review(spec, folder, final)
    (folder / "episode_report.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    log.event("episode.done", episode=ep_id, seconds=result["cut"]["seconds"], measured_ok=result["qa"]["measured_ok"])
    return result


def main(argv: list[str] | None = None) -> int:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Hindi text crashed the Windows console encoding
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, ep_id = argv[0], argv[1]
    spec = load(ep_id)
    if cmd == "check":
        bad = check(spec)
        print("\n".join(bad) if bad else f"{ep_id}: ok, {len(spec.shots)} shots")
        return 1 if bad else 0
    if cmd in ("produce", "fetch"):
        r = produce(ep_id, fetch_only=cmd == "fetch")
        print(json.dumps(r["qa"], indent=1, ensure_ascii=False))
        return 0 if r["qa"]["measured_ok"] else 1
    if cmd == "assemble":
        folder = settings().home / "episodes" / ep_id
        final = ROOT / "output" / "animeforge" / f"{ep_id}.mp4"
        print(json.dumps(assemble(spec, folder, final), indent=1, ensure_ascii=False))
        print(json.dumps(review(spec, folder, final), indent=1, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
