/**
 * Word-highlight captions driven by ReelSpec captions (Remotion Caption[]).
 * Pages of up to 4 words are built per scene: a page breaks on a gap over
 * 600 ms, on sentence punctuation, or at a scene boundary, so a page never
 * mixes two sentences or two scenes. The active word is the hero colour.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { fonts, palettes, safeZone, type StyleId } from "../design/tokens";
import { clamp, springs } from "../design/motion";
import type { CaptionItem, TimedScene } from "../schema/reelSpec";

type Token = { text: string; fromMs: number; toMs: number };
type Page = { startMs: number; endMs: number; tokens: Token[] };

const MAX_WORDS = 4;
const GAP_MS = 600;
const LINGER_MS = 160;

export const buildPages = (captions: CaptionItem[], scenes: TimedScene[], mode: "word" | "sentence"): Page[] => {
  if (mode === "sentence") {
    return captions.map((c) => ({ startMs: c.startMs, endMs: c.endMs, tokens: [{ text: c.text.trim(), fromMs: c.startMs, toMs: c.endMs }] }));
  }
  const pages: Page[] = [];
  let current: Token[] = [];
  const flush = () => {
    if (current.length) {
      pages.push({ startMs: current[0].fromMs, endMs: current[current.length - 1].toMs, tokens: current });
      current = [];
    }
  };
  const sceneEndFor = (ms: number) => scenes.find((s) => ms >= s.startMs && ms < s.endMs)?.endMs ?? Infinity;
  let sceneEnd = Infinity;
  for (const c of captions) {
    const text = c.text.trim();
    if (!text) {
      continue;
    }
    const thisSceneEnd = sceneEndFor(c.startMs);
    const prev = current[current.length - 1];
    if (prev && (c.startMs - prev.toMs > GAP_MS || thisSceneEnd !== sceneEnd || current.length >= MAX_WORDS)) {
      flush();
    }
    sceneEnd = thisSceneEnd;
    current.push({ text, fromMs: c.startMs, toMs: c.endMs });
    if (/[.!?]$/.test(text)) {
      flush();
    }
  }
  flush();
  return pages;
};

type Props = {
  captions: CaptionItem[];
  scenes: TimedScene[];
  mode: "word" | "sentence";
  styleId: StyleId;
  y?: number;
  fontSize?: number;
  /** Horizontal band; narrowed when the presenter badge sits on the left. */
  left?: number;
  right?: number;
};

export const Captions: React.FC<Props> = ({ captions, scenes, mode, styleId, y = 1230, fontSize = 60, left = safeZone.left, right = safeZone.right }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const timeMs = (frame / fps) * 1000;
  const pages = useMemo(() => buildPages(captions, scenes, mode), [captions, scenes, mode]);
  const page = pages.find((pg) => timeMs >= pg.startMs - 40 && timeMs < pg.endMs + LINGER_MS);
  if (!page) {
    return null;
  }
  const pageStartFrame = Math.round((page.startMs / 1000) * fps);
  const enter = spring({ frame: frame - pageStartFrame + 1, fps, config: springs.snappy });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: y,
          left,
          width: right - left,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "baseline",
          columnGap: Math.round(fontSize * 0.28),
          rowGap: 6,
          fontFamily: fonts.display,
          fontWeight: 700,
          fontSize,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          textAlign: "center",
          color: p.text,
          textShadow: "0 2px 18px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)",
          opacity: interpolate(enter, [0, 1], [0, 1]),
          translate: `0px ${interpolate(enter, [0, 1], [14, 0])}px`,
          scale: `${interpolate(enter, [0, 1], [0.96, 1])}`,
        }}
      >
        {page.tokens.map((tok, i) => {
          const active = timeMs >= tok.fromMs - 40 && timeMs < tok.toMs + 60;
          const done = timeMs >= tok.toMs + 60;
          const pop = active ? 1 + 0.06 * Math.sin(Math.min(1, (timeMs - tok.fromMs) / 160) * Math.PI) : 1;
          return (
            <span
              key={`${tok.fromMs}-${i}`}
              style={{
                display: "inline-block",
                color: active ? p.hero : done ? p.text : p.textDim,
                scale: `${pop}`,
                textShadow: active ? `0 0 28px ${p.glow}, 0 2px 18px rgba(0,0,0,0.8)` : undefined,
                opacity: interpolate(timeMs, [tok.fromMs - 120, tok.fromMs], [0.55, 1], clamp),
              }}
            >
              {tok.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
