"""Job queue in SQLite: enqueue, claim, retry with backoff, dead-letter.

A job has a kind and a JSON payload. A worker claims the oldest runnable job,
runs the handler registered for its kind, and marks it done or failed. A failed
job goes back to the queue after a delay that doubles each attempt, until
max_attempts, after which it is 'dead' and waits for a manual retry. A job a
handler rejects with `Permanent` (a licence or rights refusal, bad input) is
never retried: repeating it cannot change the answer.

    python -m animeforge.jobs list
    python -m animeforge.jobs work --once
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Callable

from animeforge import log
from animeforge.config import settings

STATES = ("queued", "running", "done", "failed", "dead")
BACKOFF_S = 30.0


class Permanent(Exception):
    """Raise from a handler when retrying cannot help."""


def connect(db: Path | None = None) -> sqlite3.Connection:
    path = db or settings().db
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists jobs(
        id text primary key, kind text not null, payload text not null,
        status text not null, attempts integer not null default 0,
        max_attempts integer not null default 3, not_before real not null default 0,
        error text, result text, created real not null, updated real not null)""")
    return con


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["payload"] = json.loads(d["payload"])
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def enqueue(kind: str, payload: dict, max_attempts: int = 3, db: Path | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    jid = uuid.uuid4().hex[:12]
    con = connect(db)
    con.execute("insert into jobs(id,kind,payload,status,max_attempts,created,updated) values(?,?,?,?,?,?,?)",
                (jid, kind, json.dumps(payload, ensure_ascii=False), "queued", max_attempts, now, now))
    log.event("job.queued", id=jid, kind=kind)
    return get(jid, db)


def get(jid: str, db: Path | None = None) -> dict | None:
    return _row(connect(db).execute("select * from jobs where id=?", (jid,)).fetchone())


def list_jobs(status: str | None = None, limit: int = 100, db: Path | None = None) -> list[dict]:
    con = connect(db)
    if status:
        rows = con.execute("select * from jobs where status=? order by created desc limit ?", (status, limit))
    else:
        rows = con.execute("select * from jobs order by created desc limit ?", (limit,))
    return [_row(r) for r in rows]


def claim(kinds: list[str] | None = None, db: Path | None = None, now: float | None = None) -> dict | None:
    """Atomically take the oldest runnable job."""
    now = time.time() if now is None else now
    con = connect(db)
    con.execute("begin immediate")
    try:
        q = "select id from jobs where status in ('queued','failed') and not_before<=?"
        args: list = [now]
        if kinds:
            q += f" and kind in ({','.join('?' * len(kinds))})"
            args += kinds
        r = con.execute(q + " order by created limit 1", args).fetchone()
        if r is None:
            con.execute("commit")
            return None
        con.execute("update jobs set status='running', attempts=attempts+1, updated=? where id=?", (now, r["id"]))
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return get(r["id"], db)


def complete(jid: str, result: dict | None = None, db: Path | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    connect(db).execute("update jobs set status='done', result=?, error=null, updated=? where id=?",
                        (json.dumps(result or {}, ensure_ascii=False, default=str), now, jid))
    log.event("job.done", id=jid)
    return get(jid, db)


def fail(jid: str, error: str, permanent: bool = False, db: Path | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    job = get(jid, db)
    dead = permanent or job["attempts"] >= job["max_attempts"]
    delay = BACKOFF_S * 2 ** (job["attempts"] - 1)
    connect(db).execute("update jobs set status=?, error=?, not_before=?, updated=? where id=?",
                        ("dead" if dead else "failed", error[-4000:], now + (0 if dead else delay), now, jid))
    log.event("job.dead" if dead else "job.retry", id=jid, attempts=job["attempts"],
              retry_in_s=None if dead else delay, error=error[-300:])
    return get(jid, db)


def retry(jid: str, db: Path | None = None, now: float | None = None) -> dict | None:
    """Manual retry of a dead or failed job; resets the attempt count."""
    now = time.time() if now is None else now
    connect(db).execute("update jobs set status='queued', attempts=0, not_before=0, updated=? "
                        "where id=? and status in ('dead','failed')", (now, jid))
    return get(jid, db)


def recover_stale(older_than_s: float = 6 * 3600, db: Path | None = None, now: float | None = None) -> int:
    """Jobs left 'running' by a worker that died go back to the queue."""
    now = time.time() if now is None else now
    cur = connect(db).execute("update jobs set status='failed', error='worker lost', not_before=? "
                              "where status='running' and updated<?", (now, now - older_than_s))
    return cur.rowcount


def work(handlers: dict[str, Callable[[dict], dict | None]], once: bool = False, poll_s: float = 5.0,
         db: Path | None = None, max_jobs: int | None = None) -> int:
    done = 0
    while True:
        job = claim(list(handlers), db)
        if job is None:
            if once:
                return done
            time.sleep(poll_s)
            continue
        log.event("job.start", id=job["id"], kind=job["kind"], attempt=job["attempts"])
        try:
            complete(job["id"], handlers[job["kind"]](job["payload"]), db)
        except Permanent as e:
            fail(job["id"], str(e), permanent=True, db=db)
        except Exception:
            fail(job["id"], traceback.format_exc(), db=db)
        done += 1
        if max_jobs and done >= max_jobs:
            return done


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        for j in list_jobs():
            print(f"{j['id']}  {j['status']:8} {j['attempts']}/{j['max_attempts']}  {j['kind']:16} {(j['error'] or '').strip().splitlines()[-1][:80] if j['error'] else ''}")
        return 0
    if cmd == "work":
        from animeforge.handlers import HANDLERS

        n = work(HANDLERS, once="--once" in argv)
        print(f"{n} job(s) processed")
        return 0
    if cmd == "retry" and len(argv) > 1:
        print(retry(argv[1]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
