"""Job queue, GPU monitor, Slurm runner and REST API (no GPU, no network)."""
import pytest

from animeforge import jobs, slurm, vram


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIMEFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("ANIMEFORGE_DB", str(tmp_path / "af.sqlite"))
    return tmp_path / "af.sqlite"


def test_job_runs_once_and_is_done(db):
    j = jobs.enqueue("echo", {"x": 1})
    assert jobs.work({"echo": lambda p: {"got": p["x"]}}, once=True) == 1
    got = jobs.get(j["id"])
    assert got["status"] == "done" and got["result"] == {"got": 1} and got["attempts"] == 1
    assert jobs.claim() is None


def test_failed_job_waits_then_retries_then_dies(db):
    j = jobs.enqueue("boom", {}, max_attempts=2, now=1000.0)
    c = jobs.claim(now=1000.0)
    f = jobs.fail(c["id"], "first", now=1000.0)
    assert f["status"] == "failed" and f["not_before"] == 1000.0 + jobs.BACKOFF_S
    assert jobs.claim(now=1010.0) is None            # still backing off
    c = jobs.claim(now=1031.0)
    assert c["attempts"] == 2
    assert jobs.fail(c["id"], "second", now=1031.0)["status"] == "dead"
    assert jobs.claim(now=9999.0) is None
    assert jobs.retry(j["id"])["status"] == "queued"
    assert jobs.claim(now=9999.0)["attempts"] == 1


def test_permanent_refusal_is_not_retried(db):
    def refuse(_):
        raise jobs.Permanent("licence refused")

    j = jobs.enqueue("gate", {})
    jobs.work({"gate": refuse}, once=True)
    got = jobs.get(j["id"])
    assert got["status"] == "dead" and got["attempts"] == 1 and "licence refused" in got["error"]


def test_blocked_model_job_dies_at_the_licence_gate(db):
    from animeforge.handlers import HANDLERS

    j = jobs.enqueue("licence_check", {"model_id": "wav2lip"})
    ok = jobs.enqueue("licence_check", {"model_id": "wan2.2-ti2v-5b"})
    jobs.work(HANDLERS, once=True)
    assert jobs.get(j["id"])["status"] == "dead"
    assert jobs.get(ok["id"])["status"] == "done"


def test_only_one_worker_gets_a_job(db):
    jobs.enqueue("a", {})
    assert jobs.claim() is not None
    assert jobs.claim() is None
    assert jobs.recover_stale(older_than_s=-1) == 1   # a lost worker's job comes back
    assert jobs.claim() is not None


def test_vram_parse_and_refusal():
    text = "0, NVIDIA GeForce RTX 3090, 24576, 20000, 97, 71\n1, NVIDIA GeForce RTX 3090, 24576, 512, 0, 40\n"
    g = vram.sample(run=lambda: text)
    assert [x["free_gb"] for x in g] == [4.47, 23.5]
    assert vram.require_free(20, gpus=g)["index"] == 1
    with pytest.raises(vram.VramError, match="most free is 23.5"):
        vram.require_free(24, gpus=g)
    with pytest.raises(vram.VramError, match="no NVIDIA GPU"):
        vram.require_free(1, gpus=[])
    assert vram.sample(run=lambda: "garbage") == []


def test_vram_monitor_keeps_the_peak():
    seq = iter([[{"used_gb": 2.0}], [{"used_gb": 19.5}], [{"used_gb": 3.0}]])
    m = vram.Monitor(sampler=lambda: next(seq, [{"used_gb": 1.0}]))
    m._tick(); m._tick(); m._tick()
    assert m.peak_gb == 19.5 and m.samples == 3


def test_slurm_submit_wait_and_input_checks():
    calls = []

    def fake(cmd, input=None, timeout=600):
        calls.append(cmd[-1])
        c = cmd[-1]
        if "sbatch" in c:
            return "70377\n"
        if "squeue" in c:
            return "RUNNING\n" if sum("squeue" in x for x in calls) < 3 else ""
        if "sacct" in c:
            return " COMPLETED \n"
        return ""

    jid = slurm.submit("shot.sbatch", {"SHOT_ID": "arjuna-01", "SEED": "7"}, run=fake)
    assert jid == "70377" and "SHOT_ID=arjuna-01" in calls[0]
    assert slurm.wait(jid, run=fake, sleep=lambda s: None) == "COMPLETED"
    with pytest.raises(slurm.SlurmError, match="commas"):
        slurm.submit("shot.sbatch", {"PROMPT": "a, b"}, run=fake)
    with pytest.raises(slurm.SlurmError, match="bad script"):
        slurm.submit("x; rm -rf ~", run=fake)
    with pytest.raises(slurm.SlurmError, match="bad directory"):
        slurm.fetch("../etc", __import__("pathlib").Path("x"), run=fake)


def test_api(db):
    from fastapi.testclient import TestClient

    from animeforge import rights
    from animeforge.api import app

    rights.seed()
    c = TestClient(app)
    assert c.get("/health").json()["ok"] is True
    assert c.get("/models/wav2lip/allowed").json()["allowed"] is False
    assert c.get("/models/wan2.2-ti2v-5b/allowed").json()["allowed"] is True
    assert any(m["id"] == "wan2.1" for m in c.get("/models", params={"status": "cleared"}).json())
    assert len(c.get("/characters").json()) == 16
    assert c.get("/characters/arjuna/rights").json()["usable"] is True
    assert c.get("/characters/nobody/rights").status_code == 404
    assert c.post("/jobs", json={"kind": "nope"}).status_code == 422
    j = c.post("/jobs", json={"kind": "licence_check", "payload": {"model_id": "wav2lip"}}).json()
    assert c.get(f"/jobs/{j['id']}").json()["status"] == "queued"
    assert c.post(f"/jobs/{j['id']}/retry").status_code == 409
    from animeforge.handlers import HANDLERS
    jobs.work(HANDLERS, once=True)
    assert c.get(f"/jobs/{j['id']}").json()["status"] == "dead"
    assert c.post(f"/jobs/{j['id']}/retry").json()["status"] == "queued"
    assert c.get("/jobs/zzz").status_code == 404
    assert c.get("/hardware").json()["gpus"] == [] or isinstance(c.get("/hardware").json()["gpus"], list)


def test_episode_rules_timeline_and_subtitles(db, tmp_path):
    import wave

    from animeforge import episode, rights

    rights.seed()
    spec = episode.load("arjuna-chidiya-ki-aankh")
    assert episode.check(spec) == []
    assert len(spec.shots) == 6

    bad = spec.model_copy(deep=True)
    bad.shots[0].subject = "1boy, naruto, ninja"
    bad.shots[1].line = "Yeh Hindi nahin hai"
    bad.character.id = "hanuman"                      # no cleared model for him yet
    problems = "\n".join(episode.check(bad))
    assert "naruto" in problems and "Devanagari" in problems and "'original'" in problems and "character:" in problems

    # a 6.0 s line stretches its shot; a short one keeps the clip's five seconds
    for sid, secs in ((spec.shots[0].id, 6.0), (spec.shots[1].id, 2.0)):
        d = tmp_path / "ep" / sid
        d.mkdir(parents=True)
        with wave.open(str(d / "voice.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"\0\0" * int(24000 * secs))
    rows = episode.timeline(spec, tmp_path / "ep")
    assert rows[0]["duration"] == pytest.approx(6.7) and rows[1]["duration"] == pytest.approx(121 / 24, abs=1e-3)
    assert rows[1]["start"] == pytest.approx(6.7) and rows[2]["voice"] == 0
    subs = episode.subtitles(rows)
    assert subs.count("Dialogue:") == 2 and "Noto Sans Devanagari" in subs and spec.shots[0].line in subs
    assert episode.ass_time(65.25) == "0:01:05.25"


def test_cut_dissolves_between_scenes_and_cuts_inside_a_chained_one(db, tmp_path):
    from animeforge import episode, rights

    rights.seed()
    spec = episode.load("arjuna-chidiya-ki-aankh")
    assert spec.lora and spec.lora_trigger and spec.shots[-1].continues
    for s in spec.shots:
        (tmp_path / s.id).mkdir()
    seen = {}
    res = episode.assemble(spec, tmp_path, tmp_path / "out.mp4", run=lambda cmd, **kw: seen.update(cmd=cmd))
    graph = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    fades = [part for part in graph.split(";") if "xfade" in part]
    assert len(fades) == 5 and "concat" not in graph
    # scene changes dissolve for 0.4 s; the chained last shot is a one-frame cut
    assert all("duration=0.400" in f for f in fades[:4]) and "duration=0.042" in fades[4]
    # each fade starts where the next shot starts, so the dissolves do not shorten the episode
    assert [f"offset={r['start']:.3f}" in f for r, f in zip(res["shots"][1:], fades)] == [True] * 5
    assert res["seconds"] == pytest.approx(6 * 121 / 24, abs=0.01)

    first = spec.model_copy(deep=True)
    first.shots[0].continues = True
    first.lora = "bad name.safetensors"
    problems = " | ".join(episode.check(first))
    assert "nothing to continue from" in problems and "lora: file name" in problems


def test_story_engine_builds_a_checked_episode_and_feeds_problems_back(db):
    import json as _json

    from animeforge import rights, story

    rights.seed()
    sd = story.seed("karna-kavach-daan")
    n = len(sd["lines"])
    shot = {"scene": "river bank at sunrise, golden light, wide shot", "action": "Water ripples and the camera pushes in slowly."}
    good = {"shots": [{**shot, "shows_hero": i % 2 == 0} for i in range(n)]}
    bad = {"shots": good["shots"][:3]}
    replies, seen = [bad, good], []

    class Fake:
        def post(self, url, json):
            seen.append(json["messages"])
            body = replies[len(seen) - 1]

            class R:
                status_code = 200

                def json(self_inner):
                    return {"choices": [{"message": {"content": _json.dumps(body)}}]}
            return R()

    spec, problems = story.write("karna-kavach-daan", client=Fake())
    assert problems == [] and spec is not None and len(spec.shots) == n
    assert len(seen) == 2 and "one shot per line" in seen[1][-1]["content"]   # the problem went back to the model
    assert [s.line for s in spec.shots] == sd["lines"]                         # narration is the person-written text
    assert spec.shots[0].use_reference and spec.shots[0].subject.startswith(story.LOOKS["karna"])
    assert not spec.shots[1].use_reference and spec.shots[1].subject.startswith("original, ")
    for s in story.seeds():
        assert s["character"] in story.LOOKS and 5 <= len(s["lines"]) <= 7
        assert all(len(x.split()) <= 16 for x in s["lines"])
