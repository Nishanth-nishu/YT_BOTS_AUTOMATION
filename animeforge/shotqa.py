"""Shot quality check: measurable defects plus a contact sheet for the human review.

    python -m animeforge.shotqa shot.mp4 [--seconds 5] [--width 1080 --height 1920] [--out reports/]

What it measures, from the pixels alone (CPU only, FFmpeg and NumPy):
    container   duration, resolution, frame rate against what the shot asked for
    freeze      runs of identical frames (a stuck generation)
    flicker     frame-to-frame brightness jumps that stand out from the shot's own motion
    jump        single frames that differ sharply from both neighbours (a popped frame)
    motion      whether anything moves at all

What it cannot measure, and leaves to the contact sheet and a person:
    facial consistency, anatomy, number of limbs, hands, costume and ornament
    consistency, object interaction, lighting continuity.
Those need the reference sheet beside the frames. The report lists them as
"review" items, never as passed: a shot is not approved until someone has
looked at the contact sheet and recorded that they did.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

FFMPEG, FFPROBE = "ffmpeg", "ffprobe"
REVIEW_ITEMS = ["facial consistency with the reference sheet", "anatomy", "number of limbs", "hand correctness", "costume consistency", "ornament consistency",
                "object interaction", "lighting continuity"]
SMALL = (96, 160)  # analysis size (w, h): enough for brightness and motion, cheap to decode


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class ShotReport:
    video: str
    checks: list[Check] = field(default_factory=list)
    review: list[str] = field(default_factory=lambda: list(REVIEW_ITEMS))
    contact_sheet: str = ""
    reviewed_by: str = ""  # filled in by a person after looking at the contact sheet

    @property
    def measured_ok(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def approved(self) -> bool:
        return self.measured_ok and bool(self.reviewed_by)


def probe(video: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    st = data["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {"width": st["width"], "height": st["height"], "fps": float(num) / float(den), "duration": float(data["format"]["duration"])}


def frames(video: Path, size: tuple[int, int] = SMALL) -> np.ndarray:
    """Every frame as small greyscale, shape (n, h, w), values 0..255."""
    w, h = size
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[: n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)


def measure(fr: np.ndarray, fps: float) -> dict:
    if len(fr) < 3:
        return {"frames": int(len(fr)), "motion": 0.0, "longest_freeze_s": 0.0, "flicker_events": 0, "jump_frames": [], "flicker_score": 0.0}
    diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))           # change between consecutive frames
    bright = fr.mean(axis=(1, 2))
    # freeze: consecutive frames that are (almost) identical
    still = diff < 0.02
    longest = run = 0
    for s in still:
        run = run + 1 if s else 0
        longest = max(longest, run)
    # flicker: brightness steps far outside the shot's own typical step
    step = np.abs(np.diff(bright))
    typical = float(np.median(step)) + 1e-6
    spread = float(np.median(np.abs(step - np.median(step)))) + 1e-6
    flicker = int(np.sum((step > typical + 8 * spread) & (step > 1.5)))
    # jump: a frame unlike both neighbours while the neighbours resemble each other
    skip = np.abs(fr[2:] - fr[:-2]).mean(axis=(1, 2))
    mid = np.minimum(diff[:-1], diff[1:])
    jumps = [int(i + 1) for i in np.where((mid > 3 * (skip + 0.5)) & (mid > 4.0))[0]]
    return {"frames": int(len(fr)), "motion": round(float(diff.mean()), 3), "longest_freeze_s": round(longest / fps, 2), "flicker_events": flicker,
            "jump_frames": jumps[:20], "flicker_score": round(float(step.mean() / (bright.mean() + 1e-6) * 100), 3)}


def contact_sheet(video: Path, out: Path, cols: int = 6, rows: int = 4, width: int = 240) -> Path:
    """Evenly spaced frames in a grid, each stamped with its time, for the human review."""
    info = probe(video)
    n = cols * rows
    every = max(info["duration"] / n, 1 / info["fps"])
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = f"fps=1/{every:.4f},scale={width}:-1,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.6,tile={cols}x{rows}"
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-vf", vf, "-frames:v", "1", str(out)], capture_output=True, text=True)
    if r.returncode != 0:  # some FFmpeg builds have no drawtext: fall back to an unstamped sheet
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{every:.4f},scale={width}:-1,tile={cols}x{rows}", "-frames:v", "1", str(out)], check=True)
    return out


def evaluate(video: Path, seconds: float | None = None, width: int | None = None, height: int | None = None, fps: float | None = None, out_dir: Path | None = None,
             max_freeze_s: float = 0.5, min_motion: float = 0.15) -> ShotReport:
    info = probe(video)
    m = measure(frames(video), info["fps"])
    rep = ShotReport(video=str(video))
    add = lambda name, ok, detail: rep.checks.append(Check(name, bool(ok), detail))
    if seconds is not None:
        add("duration", abs(info["duration"] - seconds) <= 0.25, f"{info['duration']:.2f}s, asked for {seconds:.2f}s")
    if width and height:
        add("resolution", (info["width"], info["height"]) == (width, height), f"{info['width']}x{info['height']}, asked for {width}x{height}")
    if fps:
        add("frame_rate", abs(info["fps"] - fps) < 0.01, f"{info['fps']:.2f} fps, asked for {fps:.2f}")
    add("moves", m["motion"] >= min_motion, f"mean frame change {m['motion']} (minimum {min_motion})")
    add("no_freeze", m["longest_freeze_s"] <= max_freeze_s, f"longest frozen run {m['longest_freeze_s']}s (limit {max_freeze_s}s)")
    add("no_flicker", m["flicker_events"] == 0, f"{m['flicker_events']} brightness jumps; flicker score {m['flicker_score']}")
    add("no_popped_frames", not m["jump_frames"], f"frames unlike both neighbours: {m['jump_frames'] or 'none'}")
    sheet = (out_dir or video.parent) / f"{video.stem}.contact.png"
    rep.contact_sheet = str(contact_sheet(video, sheet))
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure a shot and make its contact sheet.")
    ap.add_argument("video")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--fps", type=float)
    ap.add_argument("--out", help="folder for the report and contact sheet")
    args = ap.parse_args(argv)
    video = Path(args.video)
    out_dir = Path(args.out) if args.out else video.parent
    rep = evaluate(video, args.seconds, args.width, args.height, args.fps, out_dir)
    report = out_dir / f"{video.stem}.shotqa.json"
    report.write_text(json.dumps({**asdict(rep), "measured_ok": rep.measured_ok, "approved": rep.approved}, indent=1), encoding="utf-8")
    for c in rep.checks:
        print(f"[{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")
    print("REVIEW BY EYE (not measured):", "; ".join(rep.review))
    print("contact sheet:", rep.contact_sheet)
    print("MEASURED:", "PASS" if rep.measured_ok else "FAIL", "| APPROVED: no, until a person reviews the contact sheet ->", report)
    return 0 if rep.measured_ok else 1


if __name__ == "__main__":
    sys.exit(main())
