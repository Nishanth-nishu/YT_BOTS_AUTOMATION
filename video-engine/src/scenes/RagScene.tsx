/**
 * RagScene: a left-to-right pipeline (query -> embed -> vector DB -> top-k
 * -> LLM -> answer) laid out on two rows. Stages appear in order and a
 * packet travels the path, lighting each stage as the narration reaches it.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const RagScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const stages: string[] = scene.data.stages ?? ["Query", "Embed", "Vector DB", "Top-k docs", "LLM", "Answer"];
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const travelStart = Math.round(audioFrames * 0.25);
  const travelEnd = Math.round(audioFrames * 0.95);
  const prog = interpolate(frame, [travelStart, travelEnd], [0, stages.length - 1], { ...clamp, easing: ease.inOut });

  // Snake layout: 3 per row, second row reversed.
  const perRow = 3;
  const colW = 300;
  const x0 = 540 - colW;
  const rows = [90, 330];
  const pos = stages.map((_, i) => {
    const row = Math.floor(i / perRow);
    const col = i % perRow;
    const c = row % 2 === 0 ? col : perRow - 1 - col;
    return { x: x0 + c * colW, y: rows[Math.min(row, rows.length - 1)] };
  });
  const seg = Math.floor(prog);
  const t = prog - seg;
  const a = pos[Math.min(seg, pos.length - 1)];
  const b = pos[Math.min(seg + 1, pos.length - 1)];
  const px = a.x + (b.x - a.x) * t;
  const py = a.y + (b.y - a.y) * t;

  return (
    <AbsoluteFill>
      <ParticleField count={30} scale={particleScale} styleId={styleId} seed={91} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "RETRIEVAL AUGMENTED GENERATION"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        <svg width={1080} height={560} style={{ position: "absolute", left: 0, top: 0 }}>
          <defs>
            <filter id="ragglow"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>
          {pos.slice(0, -1).map((s, i) => {
            const e = pos[i + 1];
            const vis = interpolate(frame, [10 + i * 6, 22 + i * 6], [0, 1], clamp);
            const lit = prog >= i + 1;
            return <line key={i} x1={s.x} y1={s.y} x2={e.x} y2={e.y} stroke={lit ? p.hero : p.line} strokeWidth={4} strokeDasharray="12 10" strokeDashoffset={-frame * 1.2} opacity={vis} />;
          })}
          {frame >= travelStart ? <circle cx={px} cy={py} r={14} fill={p.text} filter="url(#ragglow)" /> : null}
        </svg>
        {stages.map((label, i) => {
          const s = spring({ frame: frame - 6 - i * 6, fps, config: springs.smooth });
          const active = Math.round(prog) === i && frame >= travelStart;
          const done = prog > i + 0.5;
          return (
            <div
              key={label}
              style={{
                position: "absolute",
                left: pos[i].x,
                top: pos[i].y,
                translate: "-50% -50%",
                scale: `${s}`,
                opacity: s,
                minWidth: 220,
                padding: "18px 22px",
                textAlign: "center",
                borderRadius: radius.md,
                background: active ? p.hero : p.surface,
                border: `2px solid ${active || done ? p.hero : p.line}`,
                color: active ? p.bg : done ? p.hero : p.text,
                fontFamily: fonts.display,
                fontWeight: 700,
                fontSize: 32,
                boxShadow: active ? `0 0 46px ${p.glow}` : "0 16px 36px rgba(0,0,0,0.4)",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ fontFamily: fonts.mono, fontSize: 20, color: active ? p.bg : p.textMuted, marginRight: 10 }}>{i + 1}</span>
              {label}
            </div>
          );
        })}
      </Stage>
    </AbsoluteFill>
  );
};
