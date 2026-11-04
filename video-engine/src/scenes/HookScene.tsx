/**
 * HookScene (Style A, cinematic): the boldest claim of the reel.
 * Movement within the first 15 frames: a glowing orb blooms, particles drift,
 * the hook lands word by word with the key words in the hero colour, and the
 * word "chatbot" is crossed out as the narration says "It isn't".
 */
import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { ParticleField, Orb } from "../animations/Particles";
import type { StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle } from "./SceneShell";

export const HookScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const { fps } = useVideoConfig();
  // The strike-through lands when the narration reaches "It isn't" (~72% through the audio).
  const strikeAt = Math.round(((scene.audioEndMs - scene.startMs) / 1000) * fps * 0.72);
  const title = scene.title ?? scene.narration;
  const strike: string[] = scene.data.strike ?? [];

  return (
    <AbsoluteFill>
      <ParticleField count={70} scale={particleScale} styleId={styleId} seed={3} />
      <Orb x={800} y={1640} size={600} styleId={styleId} delay={0} />
      <SceneTitle kicker="AI EXPLAINED / 01" title={title} highlight={scene.highlight} styleId={styleId} hero strike={strike} strikeAt={strikeAt} top={520} />
    </AbsoluteFill>
  );
};
