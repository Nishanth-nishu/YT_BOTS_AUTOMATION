/**
 * SmokeTest: the Phase 1 acceptance composition.
 * Proves fonts, the layer stack, kinetic type, a counter, SFX and audio
 * all render frame-accurately on this machine. 6 seconds at 30 fps.
 */
import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import "../design/fonts";
import { ReelFrame } from "../layers/Stack";
import { Entrance, Stagger, Breathe } from "../animations/Entrance";
import { WordReveal, Kicker, Counter, Body, CharReveal } from "../typography/Text";
import { palettes, safeZone, spacing } from "../design/tokens";
import { clamp, ease } from "../design/motion";

export type SmokeTestProps = {
  title: string;
  styleId: "cinematic" | "explainer";
};

const OrbitRing: React.FC<{ styleId: "cinematic" | "explainer" }> = ({ styleId }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const grow = interpolate(frame, [0, 1.2 * fps], [0, 1], { ...clamp, easing: ease.out });
  const rot = frame * 0.6;
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: 1500,
        width: 520,
        height: 520,
        translate: "-50% -50%",
        scale: `${grow}`,
        rotate: `${rot}deg`,
        borderRadius: "50%",
        border: `2px solid ${p.line}`,
        boxShadow: `0 0 80px ${p.glow}`,
      }}
    >
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 16,
            height: 16,
            borderRadius: 8,
            background: i === 0 ? p.hero : p.textMuted,
            translate: "-50% -50%",
            transform: `rotate(${i * 45}deg) translateX(260px)`,
          }}
        />
      ))}
    </div>
  );
};

export const SmokeTest: React.FC<SmokeTestProps> = ({ title, styleId }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const p = palettes[styleId];
  return (
    <ReelFrame style={styleId} grid>
      <Audio src={staticFile("sfx/riser.ogg")} volume={0.5} />
      <Sequence from={12} layout="none">
        <Audio src={staticFile("sfx/whoosh.ogg")} volume={0.7} />
      </Sequence>
      <Sequence from={Math.round(2.4 * fps) - 3} layout="none">
        <Audio src={staticFile("sfx/impact.ogg")} volume={0.8} />
      </Sequence>

      <AbsoluteFill style={{ padding: `${safeZone.top}px ${spacing.xl}px 0` }}>
        <Entrance delay={4} from="left">
          <Kicker styleId={styleId}>REELFORGE / PHASE 1 SMOKE TEST</Kicker>
        </Entrance>

        <div style={{ height: spacing.lg }} />

        <WordReveal
          text={title}
          delay={14}
          size={118}
          highlight={["render"]}
          styleId={styleId}
          exitAt={durationInFrames - 2}
        />

        <div style={{ height: spacing.xl }} />

        <Stagger start={Math.round(1.6 * fps)} step={5} from="below">
          <Body styleId={styleId}>Fonts loaded from public/fonts</Body>
          <Body styleId={styleId}>Five-layer stack, kinetic type, SFX</Body>
          <Body styleId={styleId}>Deterministic frame-by-frame animation</Body>
        </Stagger>

        <div style={{ height: spacing.xxl }} />

        <Entrance delay={Math.round(2.4 * fps)} from="scale">
          <Breathe>
            <div style={{ display: "flex", alignItems: "baseline", gap: 24 }}>
              <Counter to={1080} delay={Math.round(2.4 * fps)} size={150} styleId={styleId} />
              <CharReveal text="x1920" delay={Math.round(2.9 * fps)} size={72} color={p.textDim} styleId={styleId} />
            </div>
          </Breathe>
        </Entrance>
      </AbsoluteFill>

      <OrbitRing styleId={styleId} />
    </ReelFrame>
  );
};
