/**
 * MemoryScene: results stack into a scratchpad (left), and a vector store
 * grid (right) lights up as a query finds its nearest neighbours.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, seeded, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const MemoryScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const chips: string[] = scene.data.scratchpad ?? [];
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const chipStart = Math.round(audioFrames * 0.18);
  const vecStart = Math.round(audioFrames * 0.55);
  const cols = 6;
  const rows = 6;
  const cell = 64;
  const gridX = 560;
  const gridY = 40;
  const query = { c: 3, r: 2 };
  const scan = interpolate(frame, [vecStart + 10, vecStart + 40], [0, 1], { ...clamp, easing: ease.inOut });

  return (
    <AbsoluteFill>
      <ParticleField count={36} scale={particleScale} styleId={styleId} seed={21} speed={0.4} />
      <SceneTitle kicker="STEP 3 / REMEMBER" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />

      <Stage>
        {/* Scratchpad stack */}
        <div style={{ position: "absolute", left: 80, top: 0, width: 420 }}>
          <div style={{ fontFamily: fonts.mono, fontSize: 24, color: p.textMuted, letterSpacing: "0.1em", marginBottom: 16 }}>SCRATCHPAD</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {chips.map((c, i) => {
              const s = spring({ frame: frame - chipStart - i * 7, fps, config: springs.snappy });
              return (
                <div
                  key={c}
                  style={{
                    opacity: s,
                    translate: `0px ${interpolate(s, [0, 1], [-30, 0])}px`,
                    scale: `${interpolate(s, [0, 1], [0.9, 1])}`,
                    background: i === chips.length - 1 ? p.hero : p.surface,
                    color: i === chips.length - 1 ? p.bg : p.text,
                    border: `1px solid ${p.line}`,
                    borderRadius: radius.md,
                    padding: "16px 22px",
                    fontFamily: fonts.mono,
                    fontSize: 30,
                    boxShadow: i === chips.length - 1 ? `0 0 40px ${p.glow}` : "0 14px 30px rgba(0,0,0,0.35)",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}  {c}
                </div>
              );
            })}
          </div>
        </div>

        {/* Vector store */}
        <div style={{ position: "absolute", left: gridX, top: gridY - 40 }}>
          <div style={{ fontFamily: fonts.mono, fontSize: 24, color: p.textMuted, letterSpacing: "0.1em", marginBottom: 16 }}>VECTOR STORE</div>
        </div>
        <svg width={1080} height={560} style={{ position: "absolute", left: 0, top: 0 }}>
          {Array.from({ length: rows * cols }).map((_, i) => {
            const c = i % cols;
            const r = Math.floor(i / cols);
            const cx = gridX + c * cell + cell / 2;
            const cy = gridY + r * cell + cell / 2;
            const appear = spring({ frame: frame - vecStart - (c + r) * 2, fps, config: springs.snappy });
            const dist = Math.hypot(c - query.c, r - query.r);
            const isQuery = c === query.c && r === query.r;
            const neighbour = !isQuery && dist <= 1.5;
            const lit = scan > dist / 4;
            const rad = 7 + seeded(i * 3.3) * 7;
            return (
              <g key={i} opacity={appear}>
                {neighbour && lit ? <line x1={gridX + query.c * cell + cell / 2} y1={gridY + query.r * cell + cell / 2} x2={cx} y2={cy} stroke={p.accent} strokeWidth={2} opacity={0.8} /> : null}
                <circle cx={cx} cy={cy} r={isQuery ? 16 : neighbour && lit ? rad + 3 : rad} fill={isQuery ? p.hero : neighbour && lit ? p.accent : p.textMuted} opacity={isQuery ? 1 : neighbour && lit ? 1 : 0.5} />
                {isQuery ? <circle cx={cx} cy={cy} r={16 + ((frame * 1.5) % 40)} fill="none" stroke={p.hero} strokeWidth={2} opacity={1 - ((frame * 1.5) % 40) / 40} /> : null}
              </g>
            );
          })}
        </svg>
        <div style={{ position: "absolute", left: gridX, top: gridY + rows * cell + 10, fontFamily: fonts.mono, fontSize: 26, color: p.accent, opacity: scan }}>
          query → 4 nearest
        </div>
      </Stage>
    </AbsoluteFill>
  );
};
