"""GPU memory monitoring through nvidia-smi.

`sample()` returns one entry per GPU, or an empty list on a machine without an
NVIDIA GPU. `Monitor` polls in a thread and keeps the peak, for jobs whose
framework does not report it. `require_free()` refuses to start a job that
would not fit.
"""
from __future__ import annotations

import shutil
import subprocess
import threading

QUERY = "index,name,memory.total,memory.used,utilization.gpu,temperature.gpu"


class VramError(RuntimeError):
    pass


def parse(text: str) -> list[dict]:
    out = []
    for line in text.strip().splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) < 6 or not p[0].isdigit():
            continue
        num = lambda s: float(s) if s.replace(".", "", 1).isdigit() else None  # noqa: E731
        total, used = num(p[2]), num(p[3])
        out.append({"index": int(p[0]), "name": p[1],
                    "total_gb": round(total / 1024, 2) if total else None,
                    "used_gb": round(used / 1024, 2) if used is not None else None,
                    "free_gb": round((total - used) / 1024, 2) if total and used is not None else None,
                    "util_pct": num(p[4]), "temp_c": num(p[5])})
    return out


def sample(run=None) -> list[dict]:
    if run is None:
        if not shutil.which("nvidia-smi"):
            return []
        run = lambda: subprocess.run(  # noqa: E731
            ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15).stdout
    try:
        return parse(run())
    except (OSError, subprocess.SubprocessError):
        return []


def require_free(need_gb: float, what: str = "job", gpus: list[dict] | None = None) -> dict:
    gpus = sample() if gpus is None else gpus
    if not gpus:
        raise VramError(f"{what} needs {need_gb} GB of GPU memory and this machine has no NVIDIA GPU")
    best = max(gpus, key=lambda g: g["free_gb"] or 0)
    if (best["free_gb"] or 0) < need_gb:
        raise VramError(f"{what} needs {need_gb} GB of GPU memory; the most free is "
                        f"{best['free_gb']} GB on GPU {best['index']} ({best['name']})")
    return best


class Monitor:
    """with Monitor() as m: ...; m.peak_gb"""

    def __init__(self, interval: float = 1.0, sampler=sample):
        self.interval, self.sampler = interval, sampler
        self.peak_gb = 0.0
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _tick(self) -> None:
        for g in self.sampler():
            self.peak_gb = max(self.peak_gb, g["used_gb"] or 0.0)
        self.samples += 1

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(self.interval)

    def __enter__(self):
        self._tick()
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        self._tick()
