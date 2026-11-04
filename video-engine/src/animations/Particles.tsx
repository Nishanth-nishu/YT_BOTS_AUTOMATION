/**
 * Deterministic particle field. Positions come from a seeded hash, motion is a
 * pure function of frame, so every render is identical. Count scales with the
 * quality profile.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { seeded } from "../design/motion";
import { palettes, type StyleId } from "../design/tokens";

type ParticleFieldProps = {
  count?: number;
  scale?: number; // quality multiplier
  styleId?: StyleId;
  speed?: number;
  size?: [number, number];
  seed?: number;
  depth?: boolean; // parallax layers
  opacity?: number;
};

export const ParticleField: React.FC<ParticleFieldProps> = ({
  count = 60,
  scale = 1,
  styleId = "cinematic",
  speed = 1,
  size = [3, 9],
  seed = 1,
  depth = true,
  opacity = 0.9,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const p = palettes[styleId];
  const n = Math.max(6, Math.round(count * scale));
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      {Array.from({ length: n }).map((_, i) => {
        const r1 = seeded(seed * 1000 + i * 7.1);
        const r2 = seeded(seed * 1000 + i * 13.3 + 5);
        const r3 = seeded(seed * 1000 + i * 3.7 + 11);
        const layer = depth ? 0.4 + r3 * 0.9 : 1; // depth factor
        const sz = (size[0] + (size[1] - size[0]) * r3) * layer;
        const drift = frame * speed * 0.35 * layer;
        const x = ((r1 * width + Math.sin(frame / (40 + r2 * 40) + i) * 18 * layer) % width + width) % width;
        const y = (((r2 * height - drift) % height) + height) % height;
        const tw = 0.55 + 0.45 * Math.sin(frame / (18 + r1 * 22) + i * 1.7);
        const isHero = i % 9 === 0;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: sz,
              height: sz,
              borderRadius: "50%",
              background: isHero ? p.hero : p.textDim,
              opacity: tw * (0.25 + 0.6 * layer),
              boxShadow: isHero ? `0 0 ${sz * 3}px ${p.glow}` : undefined,
              filter: layer < 0.7 ? `blur(${(0.9 - layer) * 2.5}px)` : undefined,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/** A soft glowing orb, breathing. The one glowing hero element of a scene. */
export const Orb: React.FC<{ x: number; y: number; size: number; styleId?: StyleId; delay?: number; intensity?: number }> = ({
  x,
  y,
  size,
  styleId = "cinematic",
  delay = 0,
  intensity = 1,
}) => {
  const frame = useCurrentFrame();
  const p = palettes[styleId];
  const t = Math.max(0, frame - delay);
  const grow = 1 - Math.exp(-t / 10);
  const pulse = 1 + Math.sin(frame / 14) * 0.05;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        translate: "-50% -50%",
        scale: `${grow * pulse}`,
        borderRadius: "50%",
        background: `radial-gradient(circle at 40% 35%, ${p.text}CC, ${p.hero} 38%, ${p.hero}00 72%)`,
        boxShadow: `0 0 ${size * 0.5 * intensity}px ${p.glow}, 0 0 ${size * 1.2 * intensity}px ${p.hero}33`,
        filter: "saturate(1.1)",
      }}
    />
  );
};
