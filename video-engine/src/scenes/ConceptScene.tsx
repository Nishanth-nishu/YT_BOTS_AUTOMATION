/**
 * ConceptScene: a title and up to four numbered points that stagger in,
 * each lighting up in turn as the narration progresses. The generic
 * educational beat for any explainer.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const ConceptScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const lines: string[] = (scene.lines && scene.lines.length ? scene.lines : scene.data.lines) ?? [];
  const kicker: string = scene.data.kicker ?? "CONCEPT";
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const first = Math.round(audioFrames * 0.2);
  const gap = Math.round((audioFrames * 0.7) / Math.max(1, lines.length));
  const activeIndex = Math.min(lines.length - 1, Math.floor((frame - first) / Math.max(1, gap)));

  return (
    <AbsoluteFill>
      <ParticleField count={34} scale={particleScale} styleId={styleId} seed={51} speed={0.45} />
      <SceneTitle kicker={kicker} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        <div style={{ position: "absolute", left: 80, top: 10, width: 880, display: "flex", flexDirection: "column", gap: 18 }}>
          {lines.map((line, i) => {
            const s = spring({ frame: frame - first - i * gap, fps, config: springs.smooth });
            const active = i === activeIndex && frame >= first;
            const done = i < activeIndex;
            return (
              <div
                key={line}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  opacity: s,
                  translate: `${interpolate(s, [0, 1], [-40, 0])}px 0px`,
                  scale: `${interpolate(s, [0, 1], [0.96, 1]) * (active ? 1.02 : 1)}`,
                  background: active ? `${p.surface}F2` : `${p.surface}99`,
                  border: `1.5px solid ${active ? p.hero : p.line}`,
                  borderRadius: radius.md,
                  padding: "22px 26px",
                  boxShadow: active ? `0 0 46px ${p.glow}` : "0 16px 36px rgba(0,0,0,0.35)",
                }}
              >
                <div
                  style={{
                    width: 54,
                    height: 54,
                    borderRadius: 16,
                    flexShrink: 0,
                    background: active || done ? p.hero : "transparent",
                    border: `2px solid ${active || done ? p.hero : p.line}`,
                    color: active || done ? p.bg : p.textMuted,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: fonts.mono,
                    fontWeight: 600,
                    fontSize: 28,
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div style={{ fontFamily: fonts.body, fontWeight: 550, fontSize: 36, lineHeight: 1.2, color: active ? p.text : done ? p.textDim : p.textDim }}>{line}</div>
              </div>
            );
          })}
        </div>
      </Stage>
    </AbsoluteFill>
  );
};
