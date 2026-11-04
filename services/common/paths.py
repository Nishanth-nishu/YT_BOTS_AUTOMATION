"""Repository paths, resolved relative to this file so scripts work from any cwd."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEO_ENGINE = ROOT / "video-engine"
PUBLIC = VIDEO_ENGINE / "public"
DATA = ROOT / "data"
STORYBOARDS = DATA / "storyboards"
SCRIPTS = DATA / "scripts"
TOPICS = DATA / "topics"
DATABASE = DATA / "database" / "reelforge.sqlite"
ASSETS = ROOT / "assets"
AUDIO_CACHE = ASSETS / "audio" / "cache"
OUTPUT = ROOT / "output"
DRAFTS = OUTPUT / "drafts"
APPROVED = OUTPUT / "approved"
REJECTED = OUTPUT / "rejected"
COVERS = OUTPUT / "covers"
REPORTS = OUTPUT / "reports"
FRAMES = OUTPUT / "frames"

_WINGET_FFMPEG = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"


def _find_tool(name: str, env: str) -> str:
    """Locate ffmpeg/ffprobe: env override, PATH, then the winget install dir."""
    if os.environ.get(env):
        return os.environ[env]
    found = shutil.which(name)
    if found:
        return found
    if _WINGET_FFMPEG.exists():
        for candidate in _WINGET_FFMPEG.glob(f"Gyan.FFmpeg*/**/bin/{name}.exe"):
            return str(candidate)
    return name


FFMPEG = _find_tool("ffmpeg", "FFMPEG_BIN")
FFPROBE = _find_tool("ffprobe", "FFPROBE_BIN")


def ensure_dirs() -> None:
    for d in (STORYBOARDS, SCRIPTS, TOPICS, DATABASE.parent, AUDIO_CACHE, DRAFTS, APPROVED, REJECTED, COVERS, REPORTS, FRAMES, PUBLIC / "voice"):
        d.mkdir(parents=True, exist_ok=True)
