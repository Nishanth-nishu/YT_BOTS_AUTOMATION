/**
 * PayoffScene: the biggest typographic moment, a glowing CTA, and a particle
 * bloom. Everything stays inside the safe zone.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Breathe } from "../animations/Entrance";
import { ParticleField, Orb } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle } from "./SceneShell";

export const PayoffScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const ctaAt = Math.round(audioFrames * 0.62);
  const cta = spring({ frame: frame - ctaAt, fps, config: springs.bouncy });
  const bloom = interpolate(frame, [0, 30], [0, 1], { ...clamp, easing: ease.out });

  return (
    <AbsoluteFill>
      <ParticleField count={90} scale={particleScale * bloom} styleId={styleId} seed={44} speed={1.4} size={[3, 11]} />
      <Orb x={800} y={1560} size={640} styleId={styleId} delay={0} intensity={0.8} />
      <SceneTitle kicker="SO WHAT IS AN AGENT?" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} hero top={440} />
      {scene.cta ? (
        <div style={{ position: "absolute", left: 80, top: 960, width: 880, display: "flex" }}>
          <Breathe period={20} amount={0.02} floatPx={4}>
            <div
              style={{
                scale: `${cta}`,
                opacity: cta,
                padding: "20px 38px",
                borderRadius: 999,
                background: p.hero,
                color: p.bg,
                fontFamily: fonts.display,
                fontWeight: 700,
                fontSize: 38,
                lineHeight: 1.15,
                maxWidth: 860,
                boxShadow: `0 0 70px ${p.glow}, 0 20px 40px rgba(0,0,0,0.4)`,
              }}
            >
              {scene.cta}
            </div>
          </Breathe>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
