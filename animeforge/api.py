"""REST API for AnimeForge. Local only by default.

    python -m animeforge.api            # http://127.0.0.1:8765, docs at /docs

It reads the registry, the rights database, the job queue and the GPU state,
and queues work. It never runs GPU work itself: a worker
(`python -m animeforge.jobs work`) does that.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from animeforge import audit, jobs, registry, rights, storage, vram
from animeforge.config import settings

app = FastAPI(title="AnimeForge", version="0.2")
KINDS = ("licence_check", "shot_qa", "shot", "episode")


class NewJob(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=10)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "queued": len(jobs.list_jobs("queued")), "running": len(jobs.list_jobs("running")),
            "dead": len(jobs.list_jobs("dead"))}


@app.get("/hardware")
def hardware() -> dict:
    return {"gpus": vram.sample(), "storage": storage.report()}


@app.get("/audit")
def run_audit() -> dict:
    return audit.collect(None)


@app.get("/models")
def models(status: str | None = None) -> list[dict]:
    return [m for m in registry.load().values() if status is None or m["status"] == status]


@app.get("/models/{model_id}/allowed")
def model_allowed(model_id: str) -> dict:
    try:
        registry.require(model_id, acknowledged=settings().acknowledged)
        return {"model_id": model_id, "allowed": True, "reason": ""}
    except registry.LicenceError as e:
        return {"model_id": model_id, "allowed": False, "reason": str(e)}


@app.get("/characters")
def characters() -> list[dict]:
    return [c.model_dump() for c in rights.list_characters()]


@app.get("/characters/{char_id}/rights")
def character_rights(char_id: str, territory: str = "WORLD") -> dict:
    if rights.get_character(char_id) is None:
        raise HTTPException(404, f"no character {char_id!r}")
    problems = rights.why_not(char_id, territory, accept_conditions=True)
    return {"character": char_id, "territory": territory, "usable": not problems, "problems": problems}


@app.post("/jobs", status_code=201)
def new_job(job: NewJob) -> dict:
    if job.kind not in KINDS:
        raise HTTPException(422, f"unknown kind {job.kind!r}; one of {', '.join(KINDS)}")
    return jobs.enqueue(job.kind, job.payload, job.max_attempts)


@app.get("/jobs")
def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    if status and status not in jobs.STATES:
        raise HTTPException(422, f"status must be one of {', '.join(jobs.STATES)}")
    return jobs.list_jobs(status, limit)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "no such job")
    return j


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict:
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "no such job")
    if j["status"] not in ("dead", "failed"):
        raise HTTPException(409, f"job is {j['status']}; only dead or failed jobs can be retried")
    return jobs.retry(job_id)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
