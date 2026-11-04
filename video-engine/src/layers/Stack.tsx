/**
 * The five-layer stack every scene sits in, bottom to top:
 *   1. BgMesh      animated gradient mesh, never a flat solid
 *   2. (scene)     assets, graphics, type
 *   3. Grade       colour grade unifying everything
 *   4. Grain       procedural film grain, no asset file
 *   5. Vignette    topmost
 * <ReelFrame> composes them so a scene only renders its own content.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { palettes, type StyleId } from "../design/tokens";

export const BgMesh: React.FC<{ style?: StyleId; intensity?: number }> = ({
  style = "cinematic",
  intensity = 1,
}) => {
  const frame = useCurrentFrame();
  const p = palettes[style];
  const d1 = Math.sin(frame / 55) * 60 * intensity;
  const d2 = Math.cos(frame / 70) * 50 * intensity;
  const d3 = Math.sin(frame / 90 + 1.3) * 40 * intensity;
  return (
    <AbsoluteFill style={{ background: p.bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: 1400,
          height: 1400,
          borderRadius: "50%",
          top: -520 + d2,
          left: -420 + d1,
          filter: "blur(60px)",
          background: `radial-gradient(circle, ${p.hero}40, transparent 62%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1100,
          height: 1100,
          borderRadius: "50%",
          bottom: -480 - d1,
          right: -380 - d2,
          filter: "blur(80px)",
          background: `radial-gradient(circle, ${p.accent}2A, transparent 65%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          top: 900 + d3,
          left: 200 - d3,
          filter: "blur(90px)",
          background: `radial-gradient(circle, ${p.accent2}18, transparent 70%)`,
        }}
      />
    </AbsoluteFill>
  );
};

export const Grade: React.FC<{ style?: StyleId; opacity?: number }> = ({
  style = "cinematic",
  opacity = 0.2,
}) => {
  const p = palettes[style];
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          backgroundColor: p.hero,
          mixBlendMode: "soft-light",
          opacity,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.12), transparent 26%, transparent 72%, rgba(0,0,0,0.26))",
        }}
      />
    </AbsoluteFill>
  );
};

const NOISE = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='220' height='220'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='220' height='220' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E")`;

export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.06 }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        backgroundImage: NOISE,
        backgroundSize: "220px",
        backgroundPosition: `${(frame * 7) % 220}px ${(frame * 13) % 220}px`,
        opacity,
        mixBlendMode: "overlay",
      }}
    />
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.28 }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(ellipse at center, transparent 52%, rgba(0,0,0,${strength}) 100%)`,
    }}
  />
);

/** Subtle animated grid for tech backgrounds. */
export const GridLines: React.FC<{ style?: StyleId; size?: number; opacity?: number; drift?: number }> = ({
  style = "cinematic",
  size = 90,
  opacity = 0.12,
  drift = 0.35,
}) => {
  const frame = useCurrentFrame();
  const p = palettes[style];
  const offset = (frame * drift) % size;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity,
        backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`,
        backgroundSize: `${size}px ${size}px`,
        backgroundPosition: `${offset}px ${offset}px`,
        maskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
        WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
      }}
    />
  );
};

export const ReelFrame: React.FC<{
  style?: StyleId;
  children: React.ReactNode;
  grid?: boolean;
  meshIntensity?: number;
}> = ({ style = "cinematic", children, grid = false, meshIntensity = 1 }) => {
  return (
    <AbsoluteFill style={{ fontFamily: "Inter, sans-serif" }}>
      <BgMesh style={style} intensity={meshIntensity} />
      {grid ? <GridLines style={style} /> : null}
      <AbsoluteFill>{children}</AbsoluteFill>
      <Grade style={style} />
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};
