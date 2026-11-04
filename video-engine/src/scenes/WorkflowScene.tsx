/**
 * WorkflowScene: the full agent loop as an animated diagram. Four stages on a
 * rounded track, a packet cycling through them, and a "Done" node that
 * lights up when the narration says the loop ends.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const WorkflowScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const stages: string[] = scene.data.stages ?? ["Reason", "Call tool", "Observe", "Remember"];
  const goal: string = scene.data.goal ?? "Done";
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const doneAt = Math.round(audioFrames * 0.72);

  // Stage boxes on a 2x2 track.
  const pos = [
    { x: 290, y: 70 },
    { x: 790, y: 70 },
    { x: 790, y: 320 },
    { x: 290, y: 320 },
  ];
  const build = (i: number) => spring({ frame: frame - 8 - i * 7, fps, config: springs.smooth });
  // Packet travels around the track: 4 legs, 26 frames each.
  const legLen = 26;
  const cycle = Math.max(0, frame - 36);
  const leg = Math.floor(cycle / legLen) % 4;
  const t = interpolate(cycle % legLen, [0, legLen], [0, 1], { ...clamp, easing: ease.inOut });
  const a = pos[leg];
  const b = pos[(leg + 1) % 4];
  const px = a.x + (b.x - a.x) * t;
  const py = a.y + (b.y - a.y) * t;
  const done = spring({ frame: frame - doneAt, fps, config: springs.bouncy });

  return (
    <AbsoluteFill>
      <ParticleField count={40} scale={particleScale} styleId={styleId} seed={33} speed={0.5} />
      <SceneTitle kicker="THE AGENT LOOP" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />

      <Stage>
        <svg width={1080} height={560} style={{ position: "absolute", left: 0, top: 0 }}>
          <defs>
            <filter id="wglow"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>
          {pos.map((a0, i) => {
            const b0 = pos[(i + 1) % 4];
            const vis = interpolate(build(i + 1), [0, 1], [0, 1]);
            return <line key={i} x1={a0.x} y1={a0.y} x2={b0.x} y2={b0.y} stroke={p.line} strokeWidth={4} strokeDasharray="14 12" strokeDashoffset={-frame * 1.5} opacity={vis} />;
          })}
          {/* exit arrow to Done */}
          <line x1={540} y1={320} x2={540} y2={470} stroke={p.success} strokeWidth={4} opacity={done} />
          {/* packet */}
          {frame > 36 ? <circle cx={px} cy={py} r={16} fill={p.text} filter="url(#wglow)" /> : null}
        </svg>
        {stages.map((label, i) => {
          const s = build(i);
          const active = leg === i && t < 0.25 && frame > 36;
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
                width: 330,
                padding: "22px 0",
                textAlign: "center",
                borderRadius: radius.md,
                background: active ? p.hero : p.surface,
                border: `2px solid ${active ? p.hero : p.line}`,
                color: active ? p.bg : p.text,
                fontFamily: fonts.display,
                fontWeight: 700,
                fontSize: 40,
                boxShadow: active ? `0 0 50px ${p.glow}` : "0 20px 40px rgba(0,0,0,0.4)",
              }}
            >
              <span style={{ fontFamily: fonts.mono, fontSize: 24, color: active ? p.bg : p.textMuted, marginRight: 14 }}>{i + 1}</span>
              {label}
            </div>
          );
        })}
        <div
          style={{
            position: "absolute",
            left: 540,
            top: 500,
            translate: "-50% -50%",
            scale: `${done}`,
            opacity: done,
            padding: "18px 44px",
            borderRadius: 999,
            background: p.success,
            color: p.bg,
            fontFamily: fonts.display,
            fontWeight: 700,
            fontSize: 44,
            boxShadow: `0 0 60px ${p.success}66`,
          }}
        >
          {goal}
        </div>
      </Stage>
    </AbsoluteFill>
  );
};
