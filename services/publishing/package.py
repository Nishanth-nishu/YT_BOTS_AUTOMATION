"""Build a publication package for manual Instagram upload.

    python -m services.publishing.package --spec data/storyboards/<id>.timed.json --video output/drafts/<id>.standard.mp4 --cover output/covers/<id>.png [--qa output/reports/<id>.standard.technical.json]

Creates output/approved/<date>/<id>/ with:
    <id>.mp4, cover.png, caption.txt, hashtags.txt, sources.txt, checklist.md, package.json

Nothing is uploaded. The checklist is for the human who publishes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from services.common import paths


def build_package(spec_path: Path, video: Path, cover: Path | None, qa: Path | None, out_root: Path | None = None) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir = (out_root or paths.APPROVED) / date.today().isoformat() / spec["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, out_dir / f"{spec['id']}.mp4")
    if cover and cover.exists():
        shutil.copy(cover, out_dir / "cover.png")
    caption = spec.get("caption", "").strip()
    hashtags = spec.get("hashtags", [])
    (out_dir / "caption.txt").write_text(caption + "\n\n" + " ".join(hashtags) + "\n", encoding="utf-8")
    (out_dir / "hashtags.txt").write_text("\n".join(hashtags) + "\n", encoding="utf-8")
    (out_dir / "sources.txt").write_text("\n".join(spec.get("sources", [])) + "\n", encoding="utf-8")
    qa_summary = "not run"
    if qa and qa.exists():
        q = json.loads(qa.read_text(encoding="utf-8"))
        qa_summary = "PASS" if q.get("passed") else "FAIL: " + ", ".join(c["name"] for c in q.get("checks", []) if not c["passed"])
    checklist = f"""# Publication checklist: {spec['title']}

- [ ] Watched the full video with sound on a phone.
- [ ] Captions readable, nothing hidden under the Instagram UI.
- [ ] Facts checked against sources.txt.
- [ ] Technical QA: {qa_summary}
- [ ] Cover image chosen (cover.png) or a frame selected in the app.
- [ ] Caption pasted from caption.txt (first line is the hook).
- [ ] Hashtags: {len(hashtags)} (keep 3 to 6).
- [ ] Posted as a Reel, 9:16, original audio kept.
- [ ] Record the post URL in package.json after publishing.

Duration: {spec['durationMs'] / 1000:.1f} s. Style: {spec['style']}. Voice: {spec['voice'].get('provider')}/{spec['voice'].get('voice')}.
"""
    (out_dir / "checklist.md").write_text(checklist, encoding="utf-8")
    (out_dir / "package.json").write_text(json.dumps({
        "id": spec["id"], "title": spec["title"], "video": f"{spec['id']}.mp4", "cover": "cover.png" if cover else None,
        "duration_s": spec["durationMs"] / 1000, "qa": qa_summary, "status": "ready_for_manual_upload", "post_url": None,
    }, indent=1), encoding="utf-8")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--cover", default=None)
    ap.add_argument("--qa", default=None)
    args = ap.parse_args(argv)
    paths.ensure_dirs()
    out = build_package(Path(args.spec), Path(args.video), Path(args.cover) if args.cover else None, Path(args.qa) if args.qa else None)
    print("package:", out)
    for f in sorted(out.iterdir()):
        print("  ", f.name, f.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
