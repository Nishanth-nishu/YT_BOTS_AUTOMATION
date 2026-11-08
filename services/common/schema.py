"""Pydantic schemas shared across services. Mirrors video-engine/src/schema/reelSpec.ts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StyleId = Literal["cinematic", "explainer", "experimental"]
SceneKind = Literal["hook", "loop", "reasoning", "toolCall", "memory", "workflow", "payoff", "concept", "code", "terminal", "chart", "neuralNet", "rag"]
Seam = Literal["current", "up", "zoomIn", "zoomOut", "burst"]


class VoiceConfig(BaseModel):
    provider: Literal["kokoro", "piper"] = "kokoro"
    voice: str = "af_heart"
    speed: float = 1.0


class MusicConfig(BaseModel):
    file: str
    volume: float = 0.2
    bpm: Optional[float] = None


class StoryboardScene(BaseModel):
    id: str
    kind: SceneKind
    narration: str
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
    music: Optional[MusicConfig] = None
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
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
    music: Optional[MusicConfig] = None
    captions: list[Caption]
    captionMode: Literal["word", "sentence"] = "word"
    scenes: list[TimedScene]
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
