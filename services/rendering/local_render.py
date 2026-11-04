"""Local Remotion render with resource sampling and Instagram-safe post-encode.

    python -m services.rendering.local_render --spec data/storyboards/x.timed.json --profile draft|standard|cinematic [--out output/drafts/x.mp4] [--concurrency 2]

Samples RAM (whole machine and the render's process tree) and CPU every
second while the render runs, then re-encodes with libx264 to yuv420p
limited-range bt709 with faststart and AAC 192k. Writes a benchmark JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from services.common import paths

# Canvas size comes from the quality profile inside the Reel composition
# (calculateMetadata), so no --scale is passed (Remotion needs integer sizes).
PROFILES = {
    "draft": {"crf": 24, "width": 720, "height": 1280},
    "standard": {"crf": 18, "width": 1080, "height": 1920},
    "cinematic": {"crf": 16, "width": 1080, "height": 1920},
}


LOUDNESS_TARGET = {"I": -16.0, "TP": -1.5, "LRA": 11.0}


def loudnorm_filter(src: Path) -> str:
    """Two-pass EBU R128 normalisation: measure, then build a linear loudnorm
    filter string that lands at -16 LUFS with true peak under -1.5 dBFS."""
    measure = subprocess.run(
        [paths.FFMPEG, "-nostats", "-i", str(src), "-af", f"loudnorm=I={LOUDNESS_TARGET['I']}:TP={LOUDNESS_TARGET['TP']}:LRA={LOUDNESS_TARGET['LRA']}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = measure.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return f"loudnorm=I={LOUDNESS_TARGET['I']}:TP={LOUDNESS_TARGET['TP']}:LRA={LOUDNESS_TARGET['LRA']}"
    m = json.loads(text[start : end + 1])
    return (
        f"loudnorm=I={LOUDNESS_TARGET['I']}:TP={LOUDNESS_TARGET['TP']}:LRA={LOUDNESS_TARGET['LRA']}:"
        f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
        f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=summary"
    )


class Sampler(threading.Thread):
    def __init__(self, root_pid: int, interval: float = 1.0) -> None:
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.interval = interval
        self.samples: list[dict] = []
        self._stop_event = threading.Event()

    def run(self) -> None:
        psutil.cpu_percent(None)
        while not self._stop_event.is_set():
            tree_rss = 0
            try:
                root = psutil.Process(self.root_pid)
                for pr in [root, *root.children(recursive=True)]:
                    try:
                        tree_rss += pr.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
            vm = psutil.virtual_memory()
            self.samples.append({"t": time.time(), "cpu": psutil.cpu_percent(None), "tree_rss_mb": tree_rss / 1e6, "sys_used_mb": (vm.total - vm.available) / 1e6, "sys_avail_mb": vm.available / 1e6})
            self._stop_event.wait(self.interval)

    def stop(self) -> dict:
        self._stop_event.set()
        self.join(timeout=3)
        if not self.samples:
            return {}
        return {
            "peak_tree_rss_mb": round(max(s["tree_rss_mb"] for s in self.samples)),
            "peak_sys_used_mb": round(max(s["sys_used_mb"] for s in self.samples)),
            "min_sys_avail_mb": round(min(s["sys_avail_mb"] for s in self.samples)),
            "avg_cpu_percent": round(sum(s["cpu"] for s in self.samples) / len(self.samples), 1),
            "peak_cpu_percent": round(max(s["cpu"] for s in self.samples), 1),
            "samples": len(self.samples),
        }


def render(spec_path: Path, profile: str, out: Path, concurrency: int, composition: str = "Reel") -> dict:
    prof = PROFILES[profile]
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    props = {"specFile": None, "spec": spec, "quality": profile}
    props_path = out.with_suffix(".props.json")
    props_path.write_text(json.dumps(props), encoding="utf-8")
    raw = out.with_suffix(".raw.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    npx = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [
        npx, "remotion", "render", "src/index.ts", composition, str(raw.resolve()),
        f"--props={props_path.resolve()}", "--codec", "h264", "--crf", str(prof["crf"]),
        "--concurrency", str(concurrency), "--log=warn",
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=paths.VIDEO_ENGINE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    sampler = Sampler(proc.pid)
    sampler.start()
    log_lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        log_lines.append(line.rstrip())
    proc.wait()
    stats = sampler.stop()
    render_s = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError("remotion render failed:\n" + "\n".join(log_lines[-30:]))

    t1 = time.time()
    enc = subprocess.run([
        paths.FFMPEG, "-y", "-v", "error", "-i", str(raw),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(prof["crf"]), "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-af", loudnorm_filter(raw),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out),
    ], capture_output=True, text=True)
    if enc.returncode != 0:
        raise RuntimeError(enc.stderr)
    encode_s = time.time() - t1
    raw.unlink(missing_ok=True)

    frames = int(round(spec["durationMs"] / 1000 * spec.get("fps", 30)))
    bench = {
        "machine": "local",
        "composition": composition,
        "profile": profile,
        "concurrency": concurrency,
        "frames": frames,
        "render_seconds": round(render_s, 1),
        "encode_seconds": round(encode_s, 1),
        "frames_per_second_rendered": round(frames / render_s, 2),
        "output": str(out),
        "output_bytes": out.stat().st_size,
        "gpu": "none (Intel UHD 770, no NVENC)",
        **stats,
    }
    bench_path = paths.REPORTS / f"{out.stem}.benchmark.json"
    bench_path.write_text(json.dumps(bench, indent=1), encoding="utf-8")
    return bench


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--profile", default="draft", choices=list(PROFILES))
    ap.add_argument("--out", default=None)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--composition", default="Reel")
    args = ap.parse_args(argv)
    paths.ensure_dirs()
    spec_path = Path(args.spec)
    out = Path(args.out) if args.out else paths.DRAFTS / f"{spec_path.name.replace('.timed.json', '')}.{args.profile}.mp4"
    bench = render(spec_path, args.profile, out, args.concurrency, args.composition)
    print(json.dumps(bench, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
