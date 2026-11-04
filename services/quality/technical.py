"""Technical QA for a rendered reel.

Checks (ffprobe): valid MP4, H.264 video, resolution and aspect ratio, fps,
duration within tolerance of the spec, audio present (AAC), pixel format,
loudness (ebur128 integrated LUFS and true peak), and a static-section scan
(consecutive frames with near-zero difference). Writes a JSON report and a
contact sheet PNG.

Usage:
    python -m services.quality.technical output/drafts/x.mp4 --spec data/storyboards/x.timed.json --expect-width 1080 --expect-height 1920
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from services.common import paths


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class TechnicalReport:
    file: str
    checks: list[Check] = field(default_factory=list)
    probe: dict = field(default_factory=dict)
    loudness: dict = field(default_factory=dict)
    contact_sheet: str = ""

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: Path) -> dict:
    r = _run([paths.FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def loudness(path: Path) -> dict:
    r = _run([paths.FFMPEG, "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    text = r.stderr
    out: dict[str, float] = {}
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", text.split("Summary:")[-1])
    if m:
        out["integrated_lufs"] = float(m.group(1))
    m = re.search(r"Peak:\s+(-?[\d.]+) dBFS", text.split("Summary:")[-1])
    if m:
        out["true_peak_dbfs"] = float(m.group(1))
    m = re.search(r"LRA:\s+(-?[\d.]+) LU", text.split("Summary:")[-1])
    if m:
        out["lra_lu"] = float(m.group(1))
    return out


def static_sections(path: Path, threshold: float = 0.0004, min_seconds: float = 2.5) -> list[tuple[float, float]]:
    """Find stretches where consecutive frames barely change (dead video)."""
    r = _run([paths.FFMPEG, "-nostats", "-i", str(path), "-vf", "scale=96:-1,signalstats", "-f", "null", "-", "-v", "info", "-show_entries", "frame=pts_time"])
    # signalstats via showinfo is heavy; fall back to freezedetect which is built for this.
    r = _run([paths.FFMPEG, "-nostats", "-i", str(path), "-vf", f"freezedetect=n=0.003:d={min_seconds}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", r.stderr)]
    pairs = list(zip(starts, ends))
    if len(starts) > len(ends):
        pairs.append((starts[-1], -1.0))
    return pairs


def contact_sheet(path: Path, out: Path, cols: int = 4, rows: int = 4, width: int = 270) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    duration = float(info["format"]["duration"])
    n = cols * rows
    step = duration / n
    r = _run([
        paths.FFMPEG, "-y", "-v", "error", "-i", str(path),
        "-vf", f"fps=1/{step:.4f},scale={width}:-1,tile={cols}x{rows}:padding=6:margin=6:color=0x101018",
        "-frames:v", "1", str(out),
    ])
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return out


def run_technical(video: Path, spec: dict | None, expect_w: int, expect_h: int, expect_fps: int = 30) -> TechnicalReport:
    rep = TechnicalReport(file=str(video))
    info = probe(video)
    rep.probe = {"format": info["format"].get("format_name"), "duration": float(info["format"]["duration"]), "size": int(info["format"]["size"])}
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    rep.checks.append(Check("valid_mp4", "mp4" in (info["format"].get("format_name") or ""), info["format"].get("format_name", "")))
    rep.checks.append(Check("video_stream", v is not None, v["codec_name"] if v else "missing"))
    if v:
        rep.probe.update({"codec": v["codec_name"], "width": v["width"], "height": v["height"], "pix_fmt": v.get("pix_fmt"), "r_frame_rate": v.get("r_frame_rate"), "color_range": v.get("color_range")})
        rep.checks.append(Check("h264", v["codec_name"] == "h264", v["codec_name"]))
        rep.checks.append(Check("resolution", v["width"] == expect_w and v["height"] == expect_h, f"{v['width']}x{v['height']} expected {expect_w}x{expect_h}"))
        ratio = v["width"] / v["height"]
        rep.checks.append(Check("aspect_9_16", abs(ratio - 9 / 16) < 0.01, f"{ratio:.4f}"))
        num, den = v.get("r_frame_rate", "0/1").split("/")
        fps = float(num) / float(den)
        rep.checks.append(Check("fps", abs(fps - expect_fps) < 0.01, f"{fps:.2f}"))
        rep.checks.append(Check("pix_fmt_yuv420p", v.get("pix_fmt") in ("yuv420p", "yuvj420p"), str(v.get("pix_fmt"))))
    rep.checks.append(Check("audio_stream", a is not None, a["codec_name"] if a else "missing"))
    if a:
        rep.probe.update({"audio_codec": a["codec_name"], "sample_rate": a.get("sample_rate"), "channels": a.get("channels")})
        rep.checks.append(Check("aac", a["codec_name"] == "aac", a["codec_name"]))
    dur = float(info["format"]["duration"])
    if spec:
        expected = spec["durationMs"] / 1000
        rep.checks.append(Check("duration_matches_spec", abs(dur - expected) < 0.25, f"{dur:.2f}s vs spec {expected:.2f}s"))
    rep.checks.append(Check("duration_20_to_60s", 20 <= dur <= 61, f"{dur:.2f}s"))
    rep.loudness = loudness(video)
    if "integrated_lufs" in rep.loudness:
        lufs = rep.loudness["integrated_lufs"]
        rep.checks.append(Check("loudness_target", -20 <= lufs <= -12, f"{lufs} LUFS (target -16 +/- 4)"))
    if "true_peak_dbfs" in rep.loudness:
        rep.checks.append(Check("true_peak", rep.loudness["true_peak_dbfs"] <= -1.0, f"{rep.loudness['true_peak_dbfs']} dBFS"))
    frozen = static_sections(video)
    rep.checks.append(Check("no_static_sections", len(frozen) == 0, f"{frozen}" if frozen else "none over 2.5s"))
    sheet = contact_sheet(video, paths.REPORTS / f"{video.stem}.contact.png")
    rep.contact_sheet = str(sheet)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--spec", default=None)
    ap.add_argument("--expect-width", type=int, default=1080)
    ap.add_argument("--expect-height", type=int, default=1920)
    ap.add_argument("--expect-fps", type=int, default=30)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    paths.ensure_dirs()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8")) if args.spec else None
    rep = run_technical(Path(args.video), spec, args.expect_width, args.expect_height, args.expect_fps)
    out = Path(args.out) if args.out else paths.REPORTS / f"{Path(args.video).stem}.technical.json"
    out.write_text(json.dumps({**asdict(rep), "passed": rep.passed}, indent=1), encoding="utf-8")
    for c in rep.checks:
        print(f"[{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")
    print("loudness:", rep.loudness)
    print("contact sheet:", rep.contact_sheet)
    print("OVERALL:", "PASS" if rep.passed else "FAIL", "->", out)
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
