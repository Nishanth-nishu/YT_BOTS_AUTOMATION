/**
 * HookScene (Style A, cinematic): the boldest claim of the reel.
 * Movement within the first 15 frames: a glowing orb blooms, particles drift,
 * the hook lands word by word with the key words in the hero colour, and any
 * `data.strike` words are crossed out as the narration contradicts them.
 * With the presenter enabled, the host appears big under the title and says
 * the hook (sweat drop and "!!" for the anxious-funny opening).
 */
import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { ParticleField, Orb } from "../animations/Particles";
import type { StyleId } from "../design/tokens";
import { PresenterHero, usePresenter } from "../layers/Presenter";
import { msToFrames, type TimedScene } from "../schema/reelSpec";
import { SceneTitle } from "./SceneShell";

export const HookScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const { fps } = useVideoConfig();
  const presenter = usePresenter();
  const withHost = Boolean(presenter && presenter.enabled);
  // The strike-through lands when the narration reaches "It isn't" (~72% through the audio).
  const strikeAt = Math.round(((scene.audioEndMs - scene.startMs) / 1000) * fps * 0.72);
  const title = scene.title ?? scene.narration;
  const strike: string[] = scene.data.strike ?? [];

  return (
    <AbsoluteFill>
      <ParticleField count={withHost ? 40 : 70} scale={particleScale} styleId={styleId} seed={3} />
      <Orb x={820} y={1780} size={560} styleId={styleId} delay={0} />
      <SceneTitle kicker={scene.data.kicker ?? "AI EXPLAINED"} title={title} highlight={scene.highlight} styleId={styleId} hero strike={strike} strikeAt={strikeAt} top={withHost ? 300 : 520} />
      {withHost ? <PresenterHero sceneStartFrame={msToFrames(scene.startMs, fps)} /> : null}
    </AbsoluteFill>
  );
};
