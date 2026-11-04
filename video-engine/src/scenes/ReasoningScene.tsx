/**
 * ReasoningScene: the model turns a goal into steps. A thought panel with the
 * goal, then plan steps type themselves in one by one and get ticked, while a
 * model node pulses beside the panel.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { Mono } from "../typography/Text";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

const Typewriter: React.FC<{ text: string; start: number; cps?: number; color?: string; size?: number }> = ({ text, start, cps = 1.1, color, size = 34 }) => {
  const frame = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor((frame - start) * cps)));
  const done = n >= text.length;
  const caret = !done && Math.floor(frame / 8) % 2 === 0;
  return (
    <span style={{ fontFamily: fonts.mono, fontSize: size, color }}>
      {text.slice(0, n)}
      <span style={{ opacity: caret ? 1 : 0 }}>▍</span>
    </span>
  );
};

export const ReasoningScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const goal: string = scene.data.goal ?? "";
  const steps: string[] = scene.data.steps ?? [];
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  // Steps appear across the second half of the narration.
  const stepStart = Math.round(audioFrames * 0.45);
  const stepGap = Math.round((audioFrames * 0.5) / Math.max(1, steps.length));
  const panelIn = spring({ frame: frame - 10, fps, config: springs.smooth });

  return (
    <AbsoluteFill>
      <ParticleField count={36} scale={particleScale} styleId={styleId} seed={8} speed={0.5} />
      <SceneTitle kicker="STEP 1 / REASON" title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />

      <Stage>
        {/* Model node */}
        <div style={{ position: "absolute", left: 120, top: 40, translate: "-50% -50%", scale: `${panelIn}` }}>
          <div
            style={{
              width: 120,
              height: 120,
              borderRadius: 36,
              background: `linear-gradient(135deg, ${p.hero}, ${p.accent})`,
              boxShadow: `0 0 ${50 + Math.sin(frame / 9) * 14}px ${p.glow}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: fonts.display,
              fontWeight: 700,
              fontSize: 30,
              color: p.bg,
            }}
          >
            LLM
          </div>
        </div>

        {/* Thought panel */}
        <div
          style={{
            position: "absolute",
            left: 200,
            top: 0,
            width: 790,
            opacity: panelIn,
            translate: `${interpolate(panelIn, [0, 1], [40, 0])}px 0px`,
            background: `${p.surface}E6`,
            border: `1px solid ${p.line}`,
            borderRadius: radius.lg,
            padding: "30px 36px",
            boxShadow: "0 40px 80px -20px rgba(0,0,0,0.6)",
            backdropFilter: "blur(10px)",
          }}
        >
          <div style={{ fontFamily: fonts.mono, fontSize: 26, color: p.textMuted, letterSpacing: "0.08em" }}>GOAL</div>
          <div style={{ marginTop: 8, fontFamily: fonts.body, fontSize: 36, fontWeight: 600, color: p.text, lineHeight: 1.2 }}>{goal}</div>
          <div style={{ height: 1, background: p.line, margin: "26px 0" }} />
          <div style={{ fontFamily: fonts.mono, fontSize: 26, color: p.textMuted, letterSpacing: "0.08em" }}>PLAN</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 14 }}>
            {steps.map((s, i) => {
              const start = stepStart + i * stepGap;
              const typed = Math.min(1, Math.max(0, (frame - start) / (s.length / 1.1)));
              const tick = spring({ frame: frame - start - Math.ceil(s.length / 1.1) - 4, fps, config: springs.bouncy });
              const rowIn = interpolate(frame, [start - 4, start + 4], [0, 1], { ...clamp, easing: ease.out });
              return (
                <div key={s} style={{ display: "flex", alignItems: "center", gap: 20, opacity: rowIn, translate: `${(1 - rowIn) * 20}px 0px` }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      border: `2px solid ${tick > 0.5 ? p.success : p.line}`,
                      background: tick > 0.5 ? p.success : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      scale: `${0.8 + 0.2 * Math.min(1, tick)}`,
                    }}
                  >
                    <svg width={24} height={24} viewBox="0 0 24 24" style={{ opacity: tick }}>
                      <path d="M4 12.5 L9.5 18 L20 6" fill="none" stroke={p.bg} strokeWidth={3.4} strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <Mono size={34} color={typed >= 1 ? p.text : p.textDim} styleId={styleId}>
                    <Typewriter text={s} start={start} color={typed >= 1 ? p.text : p.textDim} />
                  </Mono>
                  <span style={{ marginLeft: "auto", fontFamily: fonts.mono, fontSize: 24, color: p.textMuted }}>{i + 1}/{steps.length}</span>
                </div>
              );
            })}
          </div>
        </div>
      </Stage>
    </AbsoluteFill>
  );
};
