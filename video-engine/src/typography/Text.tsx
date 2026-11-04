/**
 * Kinetic typography primitives.
 *  - WordReveal: word-by-word spring entrance with optional highlighted words
 *  - CharReveal: character cascade for short hero words
 *  - Headline / Kicker / Mono: styled text with the design tokens
 *  - Counter: tabular number counting up on a heavy spring
 *  - HighlightPill: a pill scaling in behind one word a beat after it lands
 */
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, dur, ease, springs } from "../design/motion";
import { fonts, palettes, type, type StyleId } from "../design/tokens";

type Common = {
  style?: React.CSSProperties;
  styleId?: StyleId;
};

export const Headline: React.FC<Common & { size?: number; weight?: number; children: React.ReactNode; dim?: boolean; align?: "left" | "center" }> = ({
  size = type.h1,
  weight = 700,
  children,
  dim = false,
  align = "left",
  styleId = "cinematic",
  style,
}) => {
  const p = palettes[styleId];
  return (
    <div
      style={{
        fontFamily: fonts.display,
        fontSize: size,
        fontWeight: weight,
        letterSpacing: type.trackingTight,
        lineHeight: type.lineTight,
        color: dim ? p.textDim : p.text,
        textAlign: align,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Body: React.FC<Common & { size?: number; children: React.ReactNode; align?: "left" | "center" }> = ({
  size = type.body,
  children,
  align = "left",
  styleId = "cinematic",
  style,
}) => {
  const p = palettes[styleId];
  return (
    <div
      style={{
        fontFamily: fonts.body,
        fontSize: size,
        fontWeight: 450,
        lineHeight: type.lineNormal,
        color: p.textDim,
        textAlign: align,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Kicker: React.FC<Common & { children: React.ReactNode }> = ({ children, styleId = "cinematic", style }) => {
  const p = palettes[styleId];
  return (
    <div
      style={{
        fontFamily: fonts.mono,
        fontSize: type.small,
        fontWeight: 500,
        letterSpacing: type.trackingWide,
        color: p.accent,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Mono: React.FC<Common & { size?: number; children: React.ReactNode; color?: string }> = ({
  size = type.mono,
  children,
  color,
  styleId = "cinematic",
  style,
}) => {
  const p = palettes[styleId];
  return (
    <span
      style={{
        fontFamily: fonts.mono,
        fontSize: size,
        fontWeight: 500,
        color: color ?? p.text,
        ...style,
      }}
    >
      {children}
    </span>
  );
};

type WordRevealProps = Common & {
  text: string;
  delay?: number;
  per?: number;
  size?: number;
  weight?: number;
  highlight?: string[]; // words to render in the hero colour
  exitAt?: number;
  align?: "left" | "center";
  lineHeight?: number;
  maxWidth?: number;
  strike?: string[]; // words crossed out with an animated line
  strikeAt?: number; // frame at which the strike draws
};

export const WordReveal: React.FC<WordRevealProps> = ({
  text,
  delay = 0,
  per = dur.staggerWord,
  size = type.h1,
  weight = 700,
  highlight = [],
  exitAt,
  align = "left",
  lineHeight = type.lineTight,
  maxWidth,
  strike = [],
  strikeAt,
  styleId = "cinematic",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const words = text.split(" ");
  const hl = new Set(highlight.map((w) => w.toLowerCase().replace(/[^a-z0-9]/g, "")));
  const st = new Set(strike.map((w) => w.toLowerCase().replace(/[^a-z0-9]/g, "")));
  const strikeP = strikeAt === undefined ? 0 : interpolate(frame, [strikeAt, strikeAt + 9], [0, 1], { ...clamp, easing: ease.out });
  const exit =
    exitAt === undefined
      ? 1
      : interpolate(frame, [exitAt - dur.exit, exitAt], [1, 0], { ...clamp, easing: ease.in });
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: align === "center" ? "center" : "flex-start",
        columnGap: Math.round(size * 0.24),
        rowGap: 0,
        fontFamily: fonts.display,
        fontSize: size,
        fontWeight: weight,
        letterSpacing: type.trackingTight,
        lineHeight,
        color: p.text,
        maxWidth,
        opacity: exit,
        translate: `0px ${(1 - exit) * -24}px`,
        ...style,
      }}
    >
      {words.map((word, i) => {
        const pr = spring({ frame: frame - delay - i * per, fps, config: springs.snappy });
        const key = word.toLowerCase().replace(/[^a-z0-9]/g, "");
        const isHero = hl.has(key);
        const isStruck = st.has(key) && strikeP > 0;
        return (
          <span
            key={`${word}-${i}`}
            style={{
              display: "inline-block",
              position: "relative",
              opacity: pr,
              translate: `0px ${interpolate(pr, [0, 1], [size * 0.35, 0])}px`,
              scale: `${interpolate(pr, [0, 1], [0.92, 1])}`,
              color: isHero && !isStruck ? p.hero : isStruck ? p.textMuted : undefined,
              textShadow: isHero && !isStruck ? `0 0 40px ${p.glow}` : undefined,
            }}
          >
            {word}
            {st.has(key) ? (
              <span
                style={{
                  position: "absolute",
                  left: "-4%",
                  top: "50%",
                  height: Math.max(6, size * 0.08),
                  width: `${108 * strikeP}%`,
                  borderRadius: 6,
                  background: p.accent2,
                  boxShadow: `0 0 24px ${p.accent2}88`,
                  rotate: "-4deg",
                  translate: "0px -50%",
                }}
              />
            ) : null}
          </span>
        );
      })}
    </div>
  );
};

export const CharReveal: React.FC<Common & { text: string; delay?: number; per?: number; size?: number; weight?: number; color?: string }> = ({
  text,
  delay = 0,
  per = 1.5,
  size = type.hero,
  weight = 700,
  color,
  styleId = "cinematic",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  return (
    <div
      style={{
        fontFamily: fonts.display,
        fontSize: size,
        fontWeight: weight,
        letterSpacing: type.trackingTight,
        lineHeight: 1,
        color: color ?? p.text,
        display: "flex",
        ...style,
      }}
    >
      {text.split("").map((ch, i) => {
        const pr = spring({ frame: frame - delay - i * per, fps, config: springs.snappy });
        return (
          <span
            key={`${ch}-${i}`}
            style={{
              display: "inline-block",
              whiteSpace: "pre",
              opacity: pr,
              translate: `0px ${interpolate(pr, [0, 1], [size * 0.5, 0])}px`,
              rotate: `${interpolate(pr, [0, 1], [8, 0])}deg`,
              filter: `blur(${interpolate(pr, [0, 1], [8, 0])}px)`,
            }}
          >
            {ch}
          </span>
        );
      })}
    </div>
  );
};

export const Counter: React.FC<Common & { to: number; from?: number; delay?: number; decimals?: number; suffix?: string; prefix?: string; size?: number }> = ({
  to,
  from = 0,
  delay = 0,
  decimals = 0,
  suffix = "",
  prefix = "",
  size = type.hero,
  styleId = "cinematic",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const pr = spring({ frame: frame - delay, fps, config: springs.heavy });
  const v = interpolate(pr, [0, 1], [from, to]);
  return (
    <span
      style={{
        fontFamily: fonts.display,
        fontSize: size,
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums",
        letterSpacing: type.trackingTight,
        color: p.hero,
        textShadow: `0 0 50px ${p.glow}`,
        ...style,
      }}
    >
      {prefix}
      {v.toFixed(decimals)}
      {suffix}
    </span>
  );
};

/** A pill that scales in behind a word a beat after the word lands. */
export const HighlightPill: React.FC<Common & { delay?: number; children: React.ReactNode; color?: string }> = ({
  delay = 0,
  children,
  color,
  styleId = "cinematic",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const pr = spring({ frame: frame - delay - 5, fps, config: springs.bouncy });
  return (
    <span style={{ position: "relative", display: "inline-block", ...style }}>
      <span
        style={{
          position: "absolute",
          inset: "-0.08em -0.18em",
          borderRadius: 999,
          background: color ?? p.hero,
          opacity: 0.9,
          scale: `${interpolate(pr, [0, 1], [0.6, 1])} ${interpolate(pr, [0, 1], [0.3, 1])}`,
          transformOrigin: "left center",
          zIndex: 0,
        }}
      />
      <span style={{ position: "relative", zIndex: 1, color: p.bg }}>{children}</span>
    </span>
  );
};
