"""Pydantic schemas shared across services. Mirrors video-engine/src/schema/reelSpec.ts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StyleId = Literal["cinematic", "explainer", "experimental"]
SceneKind = Literal["hook", "loop", "reasoning", "toolCall", "memory", "workflow", "payoff", "concept", "code", "terminal", "chart", "neuralNet", "rag"]
Seam = Literal["current", "up", "zoomIn", "zoomOut", "burst"]


class VoiceConfig(BaseModel):
    """House voice: Kokoro's male American English voice `am_fenrir`. Voices
    starting with `h` would use the Hindi pipeline (kept for experiments; the
    Hindi voices were judged too weak for the house format)."""

    provider: Literal["kokoro", "piper"] = "kokoro"
    voice: str = "am_fenrir"
    speed: float = 1.05


class MusicConfig(BaseModel):
    file: str
    volume: float = 0.2
    bpm: Optional[float] = None


class PresenterConfig(BaseModel):
    """The animated host: a male avatar whose mouth follows the voice track.
    Big in the hook scene, a small picture-in-picture badge everywhere else."""

    enabled: bool = True
    name: str = "host"
    mood: Literal["hype", "calm"] = "hype"


class StoryboardScene(BaseModel):
    id: str
    kind: SceneKind
    narration: str
    # Optional caption override (same sentence and word count as `narration`);
    # only needed when the narration carries non-Latin text the fonts lack.
    captionText: Optional[str] = None
    title: Optional[str] = None
    lines: list[str] = Field(default_factory=list)
    highlight: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    transition: Seam = "current"
    cta: Optional[str] = None
    leadInMs: int = 150
    padAfterMs: int = 350
    minDurationMs: int = 2500


class Storyboard(BaseModel):
    """Authoring-time storyboard: narration only, no timing yet."""

    id: str
    title: str
    style: StyleId = "cinematic"
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    presenter: PresenterConfig = Field(default_factory=PresenterConfig)
    music: Optional[MusicConfig] = None
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    # Comment-to-DM gate: the reel never shows the link; viewers comment the
    # keyword and the DM bot sends `dmLink` (defaults to sources[0]).
    dmKeyword: str = "LETS GO"
    dmLink: Optional[str] = None
    scenes: list[StoryboardScene]


class Caption(BaseModel):
    """Remotion @remotion/captions Caption shape."""

    text: str
    startMs: int
    endMs: int
    timestampMs: Optional[int] = None
    confidence: Optional[float] = None


class TimedScene(StoryboardScene):
    startMs: int
    endMs: int
    audioStartMs: int
    audioEndMs: int


class PresenterSpec(PresenterConfig):
    # Per-frame mouth openness 0..1 at `fps`, measured from the voice track.
    fps: int = 30
    envelope: list[float] = Field(default_factory=list)


class ReelSpec(BaseModel):
    """Render-time spec: everything Remotion needs as input props."""

    id: str
    title: str
    style: StyleId
    fps: int = 30
    width: int = 1080
    height: int = 1920
    durationMs: int
    voice: dict[str, Any]
    presenter: Optional[PresenterSpec] = None
    music: Optional[MusicConfig] = None
    captions: list[Caption]
    captionMode: Literal["word", "sentence"] = "word"
    scenes: list[TimedScene]
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    dmKeyword: str = "LETS GO"
    dmLink: Optional[str] = None
