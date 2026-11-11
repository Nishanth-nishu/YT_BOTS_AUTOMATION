"""Run AnimeForge GPU work as Slurm jobs on a remote cluster over SSH.

The laptop has no GPU, so a GPU job here means: copy the package, submit an
sbatch script with its inputs as environment variables, wait for the job to
leave the queue, read its final state, and copy the results back.

Every command goes through `run`, which tests replace.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from animeforge.config import ROOT

HOST = os.environ.get("ANIMEFORGE_SSH_HOST", "ada")
REMOTE = "animeforge"          # under the remote home: src/, logs/, out/
SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")


class SlurmError(RuntimeError):
    pass


def run(cmd: list[str], input: bytes | None = None, timeout: float = 600) -> str:
    p = subprocess.run(cmd, input=input, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise SlurmError(f"{' '.join(cmd[:3])}... failed: {p.stderr.decode(errors='replace')[-600:]}")
    return p.stdout.decode(errors="replace")


def ssh(command: str, host: str = HOST, run=run, timeout: float = 600) -> str:
    return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", host, command], timeout=timeout)


def push_source(host: str = HOST, run=run) -> None:
    """Copy the animeforge package to the cluster (small, no models)."""
    tar = subprocess.run(["tar", "--exclude=__pycache__", "-czf", "-", "animeforge"],
                         cwd=ROOT, capture_output=True, check=True).stdout
    run(["ssh", "-o", "BatchMode=yes", host,
         f"mkdir -p ~/{REMOTE}/src ~/{REMOTE}/logs ~/{REMOTE}/out && tar -xzf - -C ~/{REMOTE}/src && "
         f"sed -i 's/\\r$//' ~/{REMOTE}/src/animeforge/cluster/*.sh ~/{REMOTE}/src/animeforge/cluster/*.sbatch"],
        input=tar)


def submit(script: str, env: dict[str, str] | None = None, host: str = HOST, run=run) -> str:
    """sbatch a script from animeforge/cluster; returns the job id."""
    if not SAFE.match(script):
        raise SlurmError(f"bad script name {script!r}")
    exports = "ALL"
    for k, v in (env or {}).items():
        if not SAFE.match(k):
            raise SlurmError(f"bad variable name {k!r}")
        if "," in str(v) or "\n" in str(v):
            raise SlurmError(f"{k}: commas and newlines cannot be passed through sbatch --export; put the text in a file")
        exports += f",{k}={v}"
    out = ssh(f"cd ~ && sbatch --parsable --export={shlex.quote(exports)} "
              f"~/{REMOTE}/src/animeforge/cluster/{script}", host, run)
    jid = out.strip().split(";")[0]
    if not jid.isdigit():
        raise SlurmError(f"sbatch did not return a job id: {out!r}")
    return jid


def state(jid: str, host: str = HOST, run=run) -> str:
    """PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT, CANCELLED, OUT_OF_MEMORY ..."""
    q = ssh(f"squeue -h -j {int(jid)} -o %T 2>/dev/null || true", host, run).strip()
    if q:
        return q.split()[0]
    a = ssh(f"sacct -j {int(jid)} -X -n -o State", host, run).strip()
    return a.split()[0] if a else "UNKNOWN"


def wait(jid: str, host: str = HOST, run=run, poll_s: float = 30, timeout_s: float = 4 * 3600,
         sleep=time.sleep) -> str:
    t = 0.0
    while True:
        s = state(jid, host, run)
        if s not in ("PENDING", "RUNNING", "CONFIGURING", "COMPLETING"):
            return s
        if t >= timeout_s:
            raise SlurmError(f"job {jid} still {s} after {timeout_s:.0f} s")
        sleep(poll_s)
        t += poll_s


def fetch(remote_dir: str, local_dir: Path, host: str = HOST, run=run) -> Path:
    """Copy ~/animeforge/out/<remote_dir> back."""
    if not SAFE.match(remote_dir):
        raise SlurmError(f"bad directory name {remote_dir!r}")
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["scp", "-q", "-r", "-o", "BatchMode=yes", f"{host}:{REMOTE}/out/{remote_dir}", str(local_dir.parent)])
    return local_dir


def log_tail(script_log: str, jid: str, lines: int = 30, host: str = HOST, run=run) -> str:
    return ssh(f"tail -n {int(lines)} ~/{REMOTE}/logs/{script_log}_{int(jid)}.log 2>&1 | tr '\\r' '\\n' | tail -n {int(lines)}", host, run)
