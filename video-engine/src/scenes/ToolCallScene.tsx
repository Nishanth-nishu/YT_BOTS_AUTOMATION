/**
 * ToolCallScene: a JSON request card flies from the Agent node to the Tool
 * node, the tool spins while it runs, and a response card flies back.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

const Node: React.FC<{ x: number; y: number; label: string; sub: string; active: boolean; p: ReturnType<typeof getP>; delay: number }> = ({ x, y, label, sub, active, p, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: springs.bouncy });
  return (
    <div style={{ position: "absolute", left: x, top: y, translate: "-50% -50%", scale: `${s}`, textAlign: "center" }}>
      <div
        style={{
          width: 170,
          height: 170,
          borderRadius: 48,
          background: active ? `linear-gradient(135deg, ${p.hero}, ${p.accent})` : p.surface,
          border: `2px solid ${active ? p.hero : p.line}`,
          boxShadow: active ? `0 0 70px ${p.glow}` : "0 20px 50px rgba(0,0,0,0.45)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: fonts.display,
          fontWeight: 700,
          fontSize: 38,
          color: active ? p.bg : p.text,
        }}
      >
        {label}
      </div>
      <div style={{ marginTop: 14, fontFamily: fonts.mono, fontSize: 26, color: p.textMuted }}>{sub}</div>
    </div>
  );
};

const getP = (s: StyleId) => palettes[s];

const JsonCard: React.FC<{ lines: string[]; x: number; y: number; opacity: number; scale: number; p: ReturnType<typeof getP>; accent: string; title: string }> = ({ lines, x, y, opacity, scale, p, accent, title }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      translate: "-50% -50%",
      opacity,
      scale: `${scale}`,
      width: 520,
      background: `${p.bgAlt}F2`,
      border: `1px solid ${accent}66`,
      borderRadius: radius.md,
      padding: "18px 24px",
      boxShadow: `0 30px 60px -20px rgba(0,0,0,0.7), 0 0 40px ${accent}22`,
      fontFamily: fonts.mono,
      fontSize: 27,
      lineHeight: 1.45,
      color: p.text,
      whiteSpace: "pre",
    }}
  >
    <div style={{ fontSize: 22, color: accent, letterSpacing: "0.1em", marginBottom: 6 }}>{title}</div>
    {lines.map((l, i) => (
      <div key={i}>{l}</div>
    ))}
  </div>
);

export const ToolCallScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const tool: string = scene.data.tool ?? "search";
  const req = scene.data.request ?? {};
  const res = scene.data.response ?? {};
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;

  const t1 = Math.round(audioFrames * 0.3); // request appears
  const t2 = t1 + 26; // request starts flying
  const t3 = t2 + 22; // arrives, tool runs
  const t4 = Math.round(audioFrames * 0.78); // response flies back
  const t5 = t4 + 22;

  const ax = 300;
  const tx = 800;
  const ny = 150;
  const fly = interpolate(frame, [t2, t3], [0, 1], { ...clamp, easing: ease.inOut });
  const reqIn = spring({ frame: frame - t1, fps, config: springs.smooth });
  const reqX = interpolate(fly, [0, 1], [ax + 40, tx - 40]);
  const reqY = interpolate(fly, [0, 0.5, 1], [ny + 230, ny + 150, ny + 230]);
  const reqOpacity = reqIn * (frame < t3 + 4 ? 1 : interpolate(frame, [t3 + 4, t3 + 10], [1, 0], clamp));
  const running = frame >= t3 && frame < t4;
  const back = interpolate(frame, [t4, t5], [0, 1], { ...clamp, easing: ease.inOut });
  const resX = interpolate(back, [0, 1], [tx - 40, ax + 40]);
  const resY = interpolate(back, [0, 0.5, 1], [ny + 230, ny + 330, ny + 250]);
  const resOpacity = frame >= t4 ? 1 : 0;

  const reqLines = [`{`, ...Object.entries(req).map(([k, v], i, arr) => `  "${k}": ${JSON.stringify(v)}${i < arr.length - 1 ? "," : ""}`), `}`];
  const resLines = [`{`, ...Object.entries(res).map(([k, v], i, arr) => `  "${k}": ${JSON.stringify(v)}${i < arr.length - 1 ? "," : ""}`), `}`];

  return (
    <AbsoluteFill>
      <ParticleField count={36} scale={particleScale} styleId={styleId} seed={12} speed={0.5} />
      <SceneTitle kicker="STEP 2 / ACT" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />

      <Stage>
        {/* connection */}
        <svg width={1080} height={560} style={{ position: "absolute", left: 0, top: 0 }}>
          <line x1={ax + 95} y1={ny} x2={tx - 95} y2={ny} stroke={p.line} strokeWidth={3} strokeDasharray="10 14" strokeDashoffset={-frame * 1.2} />
        </svg>
        <Node x={ax} y={ny} label="Agent" sub="llm + loop" active={!running} p={p} delay={6} />
        <Node x={tx} y={ny} label={tool} sub="real program" active={running} p={p} delay={14} />
        {/* spinner while the tool runs */}
        {running ? (
          <div style={{ position: "absolute", left: tx, top: ny, translate: "-50% -50%", width: 210, height: 210, borderRadius: "50%", border: `4px solid transparent`, borderTopColor: p.text, rotate: `${(frame - t3) * 14}deg` }} />
        ) : null}
        <JsonCard title={`REQUEST  tool: ${tool}`} lines={reqLines} x={reqX} y={reqY} opacity={reqOpacity} scale={interpolate(reqIn, [0, 1], [0.9, 1])} p={p} accent={p.hero} />
        <JsonCard title="RESPONSE" lines={resLines} x={resX} y={resY} opacity={resOpacity} scale={1} p={p} accent={p.success} />
      </Stage>
    </AbsoluteFill>
  );
};
