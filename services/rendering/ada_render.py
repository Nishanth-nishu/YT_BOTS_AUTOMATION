"""Submit Reel renders to the Ada cluster, wait, fetch, and finish locally.

    python -m services.rendering.ada_render --ids gpt6-cyber,latent-tool-compression [--profile standard] [--cpus 16] [--concurrency 16]

Steps per reel:
  1. sync video-engine (no node_modules) and infra to ~/reelforge on Ada
  2. write runs/<id>/props.json, sbatch infra/ada/render_job.sh (gnode118 excluded)
  3. poll sacct until COMPLETED or FAILED
  4. scp the MP4 (or the raw render if the remote encode failed) and, when
     needed, encode locally with libx264 + two-pass loudnorm
  5. write output/reports/<id>.<profile>.benchmark.json
Never passes --nodelist; never touches gnode118.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from services.common import paths
from services.rendering.local_render import loudnorm_filter

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=25", "ada"]
NOISE = re.compile(r"post-quantum|store now|openssh.com/pq")


def ssh(cmd: str, timeout: int = 120) -> str:
    r = subprocess.run([*SSH, cmd], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if not NOISE.search(l))
    if r.returncode != 0 and "sacct" not in cmd:
        raise RuntimeError(f"ssh failed ({cmd[:60]}): {out[-400:]}")
    return out


def sync_engine() -> None:
    tar = subprocess.Popen(["tar", "czf", "-", "--exclude=node_modules", "--exclude=out", "--exclude=.remotion", "video-engine", "infra"], cwd=paths.ROOT, stdout=subprocess.PIPE)
    r = subprocess.run([*SSH, "tar xzf - -C ~/reelforge && sed -i 's/\\r$//' ~/reelforge/infra/ada/*.sh"], stdin=tar.stdout, capture_output=True, text=True, timeout=600)
    tar.wait()
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])


def submit(reel_id: str, profile: str, cpus: int, concurrency: int, mem: str) -> str:
    spec = json.loads((paths.STORYBOARDS / f"{reel_id}.timed.json").read_text(encoding="utf-8"))
    props = paths.DRAFTS / f"{reel_id}.ada.props.json"
    props.write_text(json.dumps({"specFile": None, "spec": spec, "quality": profile}), encoding="utf-8")
    ssh(f"mkdir -p ~/reelforge/runs/{reel_id}")
    subprocess.run(["scp", "-q", str(props), f"ada:~/reelforge/runs/{reel_id}/props.json"], check=True, capture_output=True)
    out = ssh(
        f"cd ~/reelforge && rm -f runs/{reel_id}/{reel_id}.{profile}.mp4 runs/{reel_id}/{reel_id}.{profile}.raw.mp4 && "
        f"sbatch --parsable --cpus-per-task={cpus} --mem={mem} --export=ALL,COMP=Reel,PROPS=runs/{reel_id}/props.json,"
        f"OUT=runs/{reel_id}/{reel_id}.{profile}.mp4,PROFILE={profile},CONCURRENCY={concurrency} infra/ada/render_job.sh"
    )
    job = out.strip().splitlines()[-1].split(";")[0]
    if not job.isdigit():
        raise RuntimeError(f"sbatch did not return a job id: {out}")
    return job


def wait(jobs: dict[str, str], poll: int = 40, timeout: int = 5400) -> dict[str, str]:
    t0 = time.time()
    states: dict[str, str] = {}
    pending = dict(jobs)
    while pending and time.time() - t0 < timeout:
        ids = ",".join(pending.values())
        out = ssh(f"sacct -j {ids} --format=JobID,State -P -n")
        for line in out.splitlines():
            if "|" not in line:
                continue
            jid, state = line.split("|")[:2]
            if "." in jid:
                continue
            for rid, j in list(pending.items()):
                if j == jid and state.split()[0] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"):
                    states[rid] = state.split()[0]
                    pending.pop(rid)
        if pending:
            time.sleep(poll)
    for rid in pending:
        states[rid] = "TIMEOUT_LOCAL"
    return states


def fetch_and_finish(reel_id: str, profile: str, job: str) -> dict:
    remote = f"~/reelforge/runs/{reel_id}/{reel_id}.{profile}.mp4"
    raw_remote = f"~/reelforge/runs/{reel_id}/{reel_id}.{profile}.raw.mp4"
    out = paths.DRAFTS / f"{reel_id}.{profile}.mp4"
    log = ssh(f"grep -E 'RENDER_SECONDS|ENCODER=|JOB_OK|NVENC failed' ~/reelforge/logs/render_{job}.log; sort -n ~/reelforge/logs/mem_{job}.txt 2>/dev/null | tail -1")
    size = ssh(f"stat -c %s {remote} 2>/dev/null || echo 0").strip().splitlines()[-1]
    encoded_remotely = size.isdigit() and int(size) > 1000
    if encoded_remotely:
        subprocess.run(["scp", "-q", f"ada:{remote}", str(out)], check=True, capture_output=True)
        encoder = "ada:" + (re.search(r"ENCODER=(\w+)", log).group(1) if re.search(r"ENCODER=(\w+)", log) else "unknown")
    else:
        raw = paths.DRAFTS / f"{reel_id}.{profile}.raw.mp4"
        subprocess.run(["scp", "-q", f"ada:{raw_remote}", str(raw)], check=True, capture_output=True)
        crf = {"draft": "24", "standard": "18", "cinematic": "16"}[profile]
        enc = subprocess.run([
            paths.FFMPEG, "-y", "-v", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-af", loudnorm_filter(raw), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out),
        ], capture_output=True, text=True)
        if enc.returncode != 0:
            raise RuntimeError(enc.stderr[-400:])
        raw.unlink(missing_ok=True)
        encoder = "local:libx264"
    m = re.search(r"RENDER_SECONDS=(\d+)", log)
    peak = re.findall(r"^\s*([\d.]+)\s*$", log, re.M)
    bench = {"machine": "ada", "job": job, "profile": profile, "render_seconds": int(m.group(1)) if m else None, "encoder": encoder, "peak_rss_mb": float(peak[-1]) if peak else None, "output": str(out), "output_bytes": out.stat().st_size}
    (paths.REPORTS / f"{reel_id}.{profile}.benchmark.json").write_text(json.dumps(bench, indent=1), encoding="utf-8")
    return bench


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--profile", default="standard")
    ap.add_argument("--cpus", type=int, default=16)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--mem", default="48G")
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args(argv)
    paths.ensure_dirs()
    ids = [i for i in args.ids.split(",") if i]
    if not args.no_sync:
        sync_engine()
        print("synced engine to ada")
    jobs = {rid: submit(rid, args.profile, args.cpus, args.concurrency, args.mem) for rid in ids}
    print("submitted:", jobs, flush=True)
    states = wait(jobs)
    print("states:", states, flush=True)
    results = {}
    for rid, state in states.items():
        try:
            results[rid] = fetch_and_finish(rid, args.profile, jobs[rid]) if state in ("COMPLETED", "FAILED") else {"error": state}
        except Exception as exc:  # noqa: BLE001
            results[rid] = {"error": str(exc)[-300:], "state": state}
    print(json.dumps(results, indent=1))
    return 0 if all("error" not in r for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
