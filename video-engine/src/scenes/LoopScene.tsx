/**
 * LoopScene: "a chatbot answers once, an agent runs a loop".
 * Left: a single chat bubble that answers once and goes still.
 * Then a ring with Think / Act / Observe nodes draws itself and a pulse
 * travels around it forever.
 */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { Entrance } from "../animations/Entrance";
import { ParticleField } from "../animations/Particles";
import { Body } from "../typography/Text";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const LoopScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const nodes: string[] = scene.data.nodes ?? ["Think", "Act", "Observe"];
  const loopStart = Math.round(1.3 * fps);
  const draw = interpolate(frame, [loopStart, loopStart + 40], [0, 1], { ...clamp, easing: ease.inOut });
  const cx = 540;
  const cy = 290;
  const R = 215;
  const circumference = 2 * Math.PI * R;
  const pulseAngle = ((frame - loopStart) / 60) * Math.PI * 2;

  return (
    <AbsoluteFill>
      <ParticleField count={40} scale={particleScale} styleId={styleId} seed={5} speed={0.6} />
      <SceneTitle kicker="AI EXPLAINED / 02" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />

      <Stage>
        {/* The chatbot: one bubble, one reply, then still */}
        <Entrance delay={6} from="left" exitAt={loopStart + 30} style={{ position: "absolute", left: 80, top: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ alignSelf: "flex-start", background: p.surface, border: `1px solid ${p.line}`, borderRadius: 24, padding: "16px 24px", fontFamily: fonts.body, fontSize: 32, color: p.textDim }}>
              What is an agent?
            </div>
            <Entrance delay={18} from="left">
              <div style={{ alignSelf: "flex-start", background: p.hero, borderRadius: 24, padding: "16px 24px", fontFamily: fonts.body, fontSize: 32, color: p.bg, fontWeight: 600 }}>
                An agent is...
              </div>
            </Entrance>
            <Entrance delay={28} from="none">
              <Body size={30} styleId={styleId}>answers once. done.</Body>
            </Entrance>
          </div>
        </Entrance>

        {/* The loop ring */}
        <svg width={1080} height={560} style={{ position: "absolute", left: 0, top: 0, opacity: draw > 0 ? 1 : 0 }}>
          <defs>
            <filter id="glow"><feGaussianBlur stdDeviation="6" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>
          <circle cx={cx} cy={cy} r={R} fill="none" stroke={p.line} strokeWidth={3} />
          <circle
            cx={cx}
            cy={cy}
            r={R}
            fill="none"
            stroke={p.hero}
            strokeWidth={6}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - draw)}
            transform={`rotate(-90 ${cx} ${cy})`}
            filter="url(#glow)"
          />
          {/* Travelling pulse */}
          {draw >= 1 ? (
            <circle cx={cx + Math.cos(pulseAngle - Math.PI / 2) * R} cy={cy + Math.sin(pulseAngle - Math.PI / 2) * R} r={14} fill={p.text} filter="url(#glow)" />
          ) : null}
          {/* Arrow heads along the ring */}
          {[0, 1, 2].map((i) => {
            const a = -Math.PI / 2 + (i * 2 * Math.PI) / 3 + Math.PI / 3;
            const ax = cx + Math.cos(a) * R;
            const ay = cy + Math.sin(a) * R;
            const vis = draw > (i + 0.5) / 3 ? 1 : 0;
            return (
              <polygon key={i} points="-14,-10 14,0 -14,10" fill={p.hero} opacity={vis} transform={`translate(${ax} ${ay}) rotate(${(a * 180) / Math.PI + 90})`} />
            );
          })}
        </svg>
        {nodes.map((label, i) => {
          const a = -Math.PI / 2 + (i * 2 * Math.PI) / 3;
          const nx = cx + Math.cos(a) * R;
          const ny = cy + Math.sin(a) * R;
          const s = spring({ frame: frame - loopStart - 12 - i * 10, fps, config: springs.bouncy });
          const near = Math.abs(((pulseAngle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2) - ((i * 2 * Math.PI) / 3)) < 0.35 && draw >= 1;
          return (
            <div
              key={label}
              style={{
                position: "absolute",
                left: nx,
                top: ny,
                translate: "-50% -50%",
                scale: `${s}`,
                padding: "18px 34px",
                borderRadius: 999,
                background: near ? p.hero : p.surface,
                border: `2px solid ${near ? p.hero : p.line}`,
                color: near ? p.bg : p.text,
                fontFamily: fonts.display,
                fontWeight: 700,
                fontSize: 40,
                boxShadow: near ? `0 0 50px ${p.glow}` : "0 20px 40px rgba(0,0,0,0.4)",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </div>
          );
        })}
      </Stage>
    </AbsoluteFill>
  );
};
