"""What each job kind does. Used by `python -m animeforge.jobs work` and the API.

GPU kinds run on the cluster through `animeforge.slurm`; the gates (licence,
character rights) run first and refuse permanently, so a refused job is never
retried.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from animeforge import registry, rights, shotqa, slurm
from animeforge.config import settings
from animeforge.jobs import Permanent

SHOT_MODEL = "wan2.2-ti2v-5b"
STILL_MODEL = "animagine-xl-4"


def _gate_models(*ids: str) -> None:
    try:
        for i in ids:
            registry.require(i, acknowledged=settings().acknowledged)
    except registry.LicenceError as e:
        raise Permanent(str(e)) from e


def _gate_character(char_id: str) -> None:
    try:
        rights.require_character(char_id, accept_conditions=True)
    except rights.RightsError as e:
        raise Permanent(str(e)) from e


def licence_check(p: dict) -> dict:
    _gate_models(p["model_id"])
    return {"model_id": p["model_id"], "allowed": True}


def shot_qa(p: dict) -> dict:
    video = Path(p["video"])
    if not video.exists():
        raise Permanent(f"no such video: {video}")
    rep = shotqa.evaluate(video, p.get("seconds"), p.get("width"), p.get("height"), p.get("fps"))
    return {**asdict(rep), "measured_ok": rep.measured_ok, "approved": rep.approved}


def _cluster(script: str, log_name: str, env: dict, out_name: str, local: Path) -> dict:
    slurm.push_source()
    jid = slurm.submit(script, env)
    final = slurm.wait(jid)
    if final != "COMPLETED":
        raise RuntimeError(f"cluster job {jid} ended {final}:\n{slurm.log_tail(log_name, jid)}")
    slurm.fetch(out_name, local)
    return {"slurm_job": jid, "state": final, "output": str(local)}


def shot(p: dict) -> dict:
    """One shot: {id, character, still_prompt_file | image, prompt_file, seed, frames, steps}.

    Prompts travel as files under animeforge/cluster/prompts/ because sbatch
    cannot pass text with commas in --export.
    """
    _gate_character(p["character"])
    _gate_models(SHOT_MODEL, STILL_MODEL)
    sid = p["id"]
    env = {"SHOT_ID": sid, "SEED": str(p.get("seed", 7)), "FRAMES": str(p.get("frames", 121)),
           "STEPS": str(p.get("steps", 50))}
    out = settings().home / "shots" / sid
    res = _cluster("shot.sbatch", "shot", env, sid, out)
    video = out / "shot.mp4"
    rep = shotqa.evaluate(video, seconds=p.get("frames", 121) / 24, fps=24)
    res["qa"] = {"measured_ok": rep.measured_ok, "checks": [asdict(c) for c in rep.checks],
                 "contact_sheet": rep.contact_sheet, "approved": rep.approved}
    return res


def episode(p: dict) -> dict:
    """A whole episode: {id}. The episode file is animeforge/cluster/episodes/<id>.json."""
    from animeforge import episode as ep

    return ep.produce(p["id"])


HANDLERS = {"licence_check": licence_check, "shot_qa": shot_qa, "shot": shot, "episode": episode}
