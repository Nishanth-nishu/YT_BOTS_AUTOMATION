/**
 * TerminalScene: a terminal window types a command, then output lines
 * stream in. For developer-tool and repo reels.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

type Line = { text: string; kind?: "out" | "ok" | "warn" | "dim" };

export const TerminalScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const command: string = scene.data.command ?? "";
  const lines: Line[] = (scene.data.lines ?? []).map((l: string | Line) => (typeof l === "string" ? { text: l } : l));
  const title: string = scene.data.windowTitle ?? "terminal";
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const typeStart = 12;
  const cps = 1.4;
  const typed = Math.max(0, Math.min(command.length, Math.floor((frame - typeStart) * cps)));
  const typingDone = typeStart + Math.ceil(command.length / cps) + 8;
  const outStart = Math.max(typingDone, Math.round(audioFrames * 0.35));
  const outGap = Math.max(4, Math.round((audioFrames * 0.55) / Math.max(1, lines.length)));
  const win = spring({ frame: frame - 2, fps, config: springs.smooth });
  const caret = Math.floor(frame / 8) % 2 === 0;
  const colour = (k?: string) => (k === "ok" ? p.success : k === "warn" ? p.warn : k === "dim" ? p.textMuted : p.textDim);

  return (
    <AbsoluteFill>
      <ParticleField count={30} scale={particleScale} styleId={styleId} seed={61} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "DEV TOOLS"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        <div
          style={{
            position: "absolute",
            left: 80,
            top: 10,
            width: 880,
            opacity: win,
            translate: `0px ${interpolate(win, [0, 1], [40, 0])}px`,
            scale: `${interpolate(win, [0, 1], [0.96, 1])}`,
            background: "#0B0D16F5",
            border: `1px solid ${p.line}`,
            borderRadius: radius.lg,
            boxShadow: "0 40px 80px -20px rgba(0,0,0,0.7)",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 22px", borderBottom: `1px solid ${p.line}` }}>
            {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
              <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />
            ))}
            <div style={{ marginLeft: 14, fontFamily: fonts.mono, fontSize: 24, color: p.textMuted }}>{title}</div>
          </div>
          <div style={{ padding: "22px 26px 26px", fontFamily: fonts.mono, fontSize: 30, lineHeight: 1.5, color: p.text, minHeight: 300 }}>
            <div>
              <span style={{ color: p.hero }}>$ </span>
              {command.slice(0, typed)}
              {frame < outStart ? <span style={{ opacity: caret ? 1 : 0 }}>▍</span> : null}
            </div>
            {lines.map((l, i) => {
              const at = outStart + i * outGap;
              const o = interpolate(frame, [at, at + 5], [0, 1], { ...clamp, easing: ease.out });
              return (
                <div key={`${l.text}-${i}`} style={{ opacity: o, translate: `${(1 - o) * 10}px 0px`, color: colour(l.kind), whiteSpace: "pre-wrap" }}>
                  {l.text}
                </div>
              );
            })}
          </div>
        </div>
      </Stage>
    </AbsoluteFill>
  );
};
