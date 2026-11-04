/**
 * Cover: a Still used as the Instagram cover image for a reel.
 */
import React from "react";
import { AbsoluteFill } from "remotion";
import "../design/fonts";
import { ReelFrame } from "../layers/Stack";
import { ParticleField, Orb } from "../animations/Particles";
import { Headline, Kicker } from "../typography/Text";
import { fonts, palettes, type StyleId } from "../design/tokens";

export type CoverProps = { title: string; kicker: string; styleId: StyleId; highlight: string[] };

export const Cover: React.FC<CoverProps> = ({ title, kicker, styleId, highlight }) => {
  const p = palettes[styleId];
  const hl = new Set(highlight.map((w) => w.toLowerCase()));
  return (
    <ReelFrame style={styleId}>
      <ParticleField count={70} scale={1} styleId={styleId} seed={9} />
      <Orb x={760} y={1250} size={620} styleId={styleId} delay={-100} />
      <AbsoluteFill style={{ padding: "520px 100px 0 80px" }}>
        <Kicker styleId={styleId}>{kicker}</Kicker>
        <div style={{ height: 40 }} />
        <Headline size={132} styleId={styleId} style={{ maxWidth: 900 }}>
          {title.split(" ").map((w, i) => (
            <span key={i} style={{ color: hl.has(w.toLowerCase().replace(/[^a-z0-9]/g, "")) ? p.hero : undefined, textShadow: hl.has(w.toLowerCase().replace(/[^a-z0-9]/g, "")) ? `0 0 40px ${p.glow}` : undefined }}>
              {w}{" "}
            </span>
          ))}
        </Headline>
        <div style={{ position: "absolute", bottom: 560, left: 80, fontFamily: fonts.mono, fontSize: 30, color: p.textMuted, letterSpacing: "0.12em" }}>REELFORGE</div>
      </AbsoluteFill>
    </ReelFrame>
  );
};
