"""Phase 1: hardware and dependency audit.

    python -m animeforge.audit                    # this machine
    python -m animeforge.audit --ssh-host ada     # also probe a remote GPU host (read-only)
    python -m animeforge.audit --out docs/animeforge/AUDIT.md

Reports the GPU, VRAM, RAM, disks, WSL and the tools each engine needs, then
says plainly which phases this machine can run. It only reads: it installs
nothing, and the remote probe runs a handful of status commands and never
submits a job.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psutil

from animeforge.config import TARGET, settings
from animeforge.storage import report as storage_report

TOOLS = {
    "python": (["python", "--version"], "everything"),
    "git": (["git", "--version"], "everything"),
    "git-lfs": (["git-lfs", "--version"], "model downloads"),
    "ffmpeg": (["ffmpeg", "-version"], "rendering, audio"),
    "node": (["node", "--version"], "Remotion rendering"),
    "blender": (["blender", "--version"], "Blender rendering"),
    "ollama": (["ollama", "--version"], "story engine (local LLM)"),
    "docker": (["docker", "--version"], "optional: containerised services"),
}
REMOTE_PROBE = "hostname; echo ---; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -4; echo ---; sinfo -o '%P %a %D %G' 2>/dev/null | head -8; echo ---; df -h ~ 2>/dev/null | tail -1"


def run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or p.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 127, type(exc).__name__


def gpus() -> list[dict]:
    """NVIDIA cards from nvidia-smi; on Windows, any other adapter from the OS so the report is not blank."""
    found: list[dict] = []
    code, out = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if code == 0:
        for line in out.splitlines():
            name, mem, driver = [x.strip() for x in line.split(",")][:3]
            found.append({"name": name, "vendor": "NVIDIA", "vram_gb": round(float(mem) / 1024, 1), "driver": driver})
    if not found and platform.system() == "Windows":
        code, out = run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"])
        if code == 0:
            found = [{"name": n.strip(), "vendor": "NVIDIA" if "nvidia" in n.lower() else "other", "vram_gb": None, "driver": None} for n in out.splitlines() if n.strip()]
    return found


def torch_cuda() -> dict:
    try:
        import torch

        return {"torch": torch.__version__, "cuda": bool(torch.cuda.is_available())}
    except Exception:  # noqa: BLE001 - torch is optional for the audit
        return {"torch": None, "cuda": False}


def wsl() -> str:
    if platform.system() != "Windows":
        return "not Windows"
    code, out = run(["wsl.exe", "-l", "-q"])
    names = [line.replace("\x00", "").strip() for line in out.splitlines()]
    names = [n for n in names if n and "not installed" not in n.lower() and "aka.ms" not in n.lower()]
    return ", ".join(names) if code == 0 and names else "not installed"


def collect(ssh_host: str | None = None) -> dict:
    vm = psutil.virtual_memory()
    tools = {}
    for name, (cmd, used_for) in TOOLS.items():
        code, out = (run(cmd) if shutil.which(cmd[0]) else (127, ""))
        tools[name] = {"found": code == 0, "version": out.splitlines()[0][:80] if code == 0 and out else None, "used_for": used_for}
    data = {
        "when": datetime.now().isoformat(timespec="seconds"),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": {"name": platform.processor(), "cores": psutil.cpu_count(logical=False), "threads": psutil.cpu_count()},
        "ram_gb": round(vm.total / 1024 ** 3, 1), "ram_free_gb": round(vm.available / 1024 ** 3, 1),
        "gpus": gpus(), "torch": torch_cuda(), "wsl": wsl(), "tools": tools, "disks": storage_report(),
        "paths": {k: str(v) for k, v in vars(settings()).items() if k in ("home", "models_dir", "cache_dir", "db")},
        "remote": None,
    }
    if ssh_host:
        code, out = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_host, REMOTE_PROBE], timeout=40)
        parts = [p.strip() for p in out.split("---")] if code == 0 else []
        data["remote"] = {"host": ssh_host, "reachable": code == 0, "hostname": parts[0].splitlines()[-1] if parts and parts[0] else None,
                          "gpus_on_login_node": parts[1] if len(parts) > 1 else "", "partitions": parts[2] if len(parts) > 2 else "", "home_disk": parts[3] if len(parts) > 3 else "",
                          "error": None if code == 0 else out[:200]}
    return data


def verdict(data: dict) -> dict:
    """What this machine can and cannot do, against config.TARGET."""
    nvidia = [g for g in data["gpus"] if g["vendor"] == "NVIDIA"]
    best = max((g["vram_gb"] or 0 for g in nvidia), default=0)
    free_disk = max((d["free_gb"] for d in data["disks"]), default=0)
    gaps = []
    if not nvidia:
        gaps.append(f"no NVIDIA GPU (found: {', '.join(g['name'] for g in data['gpus']) or 'none'})")
    elif best < TARGET["min_vram_gb"]:
        gaps.append(f"largest NVIDIA GPU has {best} GB VRAM, target is {TARGET['min_vram_gb']} GB")
    if nvidia and not data["torch"]["cuda"]:
        gaps.append("PyTorch here is a CPU build: install a CUDA build")
    if data["ram_gb"] < TARGET["min_ram_gb"]:
        gaps.append(f"{data['ram_gb']} GB RAM, target is {TARGET['min_ram_gb']} GB")
    if free_disk < TARGET["min_free_disk_gb"]:
        gaps.append(f"{free_disk} GB free on the AnimeForge drive, target is {TARGET['min_free_disk_gb']} GB")
    gpu_ready = bool(nvidia) and best >= TARGET["min_vram_gb"]
    return {
        "gpu_ready": gpu_ready, "gaps": gaps,
        "can_run_here": ["story engine (local LLM on CPU)", "character and rights database", "Kokoro Hindi voice (CPU)", "Remotion and FFmpeg rendering (CPU)", "REST API, job queue, QA on audio and files"],
        "needs_gpu": [] if gpu_ready else ["ComfyUI image generation, IPAdapter, ControlNet, LoRA training (Phase 3)", "Wan2.1 / LTX-Video / AnimateDiff benchmarks and animation (Phase 4)",
                                           "LatentSync / MuseTalk lip-sync (Phase 5)", "IndicF5, Indic Parler-TTS, Chatterbox at usable speed (Phase 2 benchmarks)"],
    }


def markdown(data: dict) -> str:
    v = verdict(data)
    lines = [f"# AnimeForge hardware and dependency audit", "", f"Run: {data['when']}", "",
             "## Verdict", "",
             ("This machine meets the GPU target." if v["gpu_ready"] else "**This machine cannot run the GPU phases.**"), ""]
    lines += [f"- {g}" for g in v["gaps"]] or ["- no gaps against the target"]
    lines += ["", "Can run here:", *[f"- {x}" for x in v["can_run_here"]]]
    if v["needs_gpu"]:
        lines += ["", "Needs a machine with an NVIDIA GPU of 24 GB or more:", *[f"- {x}" for x in v["needs_gpu"]]]
    gpu_text = "; ".join(g["name"] + (" (%s GB)" % g["vram_gb"] if g["vram_gb"] else "") for g in data["gpus"]) or "none found"
    lines += ["", "## Machine", "", "| Item | Value |", "|---|---|", f"| OS | {data['os']} |", f"| CPU | {data['cpu']['name']} ({data['cpu']['cores']} cores, {data['cpu']['threads']} threads) |",
              f"| RAM | {data['ram_gb']} GB ({data['ram_free_gb']} GB free at audit time) |",
              f"| GPU | {gpu_text} |",
              f"| PyTorch | {data['torch']['torch'] or 'not installed'}, CUDA {'yes' if data['torch']['cuda'] else 'no'} |", f"| WSL | {data['wsl']} |"]
    lines += [f"| Disk {d['drive']} | {d['free_gb']} GB free of {d['total_gb']} GB (used for {', '.join(d['used_for'])}) |" for d in data["disks"]]
    lines += ["", "## Tools", "", "| Tool | Found | Version | Needed for |", "|---|---|---|---|"]
    lines += [f"| {n} | {'yes' if t['found'] else 'no'} | {t['version'] or ''} | {t['used_for']} |" for n, t in data["tools"].items()]
    r = data.get("remote")
    if r:
        lines += ["", f"## Remote host `{r['host']}`", ""]
        if r["reachable"]:
            lines += [f"- reachable as `{r['hostname']}`", f"- GPUs visible on the login node: {r['gpus_on_login_node'] or 'none (compute nodes are reached through the scheduler)'}",
                      "- scheduler partitions:", "", "```", r["partitions"] or "(none reported)", "```", "", f"- home directory: `{r['home_disk']}`"]
        else:
            lines += [f"- not reachable: {r['error']}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AnimeForge hardware and dependency audit (read-only).")
    ap.add_argument("--ssh-host", help="also probe this SSH host alias (status commands only)")
    ap.add_argument("--out", help="write the Markdown report here")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead of Markdown")
    args = ap.parse_args(argv)
    data = collect(args.ssh_host)
    text = json.dumps({**data, "verdict": verdict(data)}, indent=1) if args.json else markdown(data)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(markdown(data), encoding="utf-8")
    print(text)
    return 0 if verdict(data)["gpu_ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
