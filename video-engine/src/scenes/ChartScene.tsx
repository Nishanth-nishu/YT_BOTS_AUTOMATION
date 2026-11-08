/**
 * ChartScene: animated bar chart with counters, or a line that draws itself.
 * Values are shown exactly as given in the storyboard; nothing is rounded
 * beyond the `decimals` field.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, springs } from "../design/motion";
import { fonts, palettes, radius, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

type Series = { label: string; value: number; hero?: boolean };

const PREFIX_UNITS = new Set(["$", "₹", "€", "£"]);
/** Currency units go before the number, everything else after. */
export const fmt = (v: number, unit: string, decimals: number) => (PREFIX_UNITS.has(unit) ? `${unit}${v.toFixed(decimals)}` : `${v.toFixed(decimals)}${unit}`);

export const ChartScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const type: "bar" | "line" = scene.data.type ?? "bar";
  const series: Series[] = scene.data.series ?? [];
  const unit: string = scene.data.unit ?? "";
  const decimals: number = scene.data.decimals ?? 0;
  const note: string = scene.data.note ?? "";
  const maxV = Math.max(1, ...series.map((s) => s.value));
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const start = Math.round(audioFrames * 0.18);
  const W = 880;
  const H = 400;
  const left = 80;

  return (
    <AbsoluteFill>
      <ParticleField count={30} scale={particleScale} styleId={styleId} seed={71} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "BY THE NUMBERS"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        <div style={{ position: "absolute", left, top: 10, width: W, height: H + 110, background: `${p.surface}99`, border: `1px solid ${p.line}`, borderRadius: radius.lg, padding: "26px 30px", boxSizing: "border-box" }}>
          {type === "bar" ? (
            <div style={{ display: "flex", alignItems: "flex-end", gap: 26, height: H, paddingTop: 50 }}>
              {series.map((s, i) => {
                const g = spring({ frame: frame - start - i * 7, fps, config: springs.heavy });
                const h = interpolate(g, [0, 1], [0, (s.value / maxV) * (H - 110)]);
                const v = interpolate(g, [0, 1], [0, s.value]);
                return (
                  <div key={s.label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                    <div style={{ fontFamily: fonts.display, fontWeight: 700, fontSize: 36, color: s.hero ? p.hero : p.text, fontVariantNumeric: "tabular-nums", marginBottom: 10, opacity: g }}>
                      {fmt(v, unit, decimals)}
                    </div>
                    <div
                      style={{
                        width: "100%",
                        height: h,
                        borderRadius: 14,
                        background: s.hero ? `linear-gradient(180deg, ${p.hero}, ${p.accent})` : `${p.textMuted}66`,
                        boxShadow: s.hero ? `0 0 40px ${p.glow}` : undefined,
                      }}
                    />
                    <div style={{ marginTop: 14, fontFamily: fonts.mono, fontSize: 24, color: p.textDim, textAlign: "center", lineHeight: 1.2 }}>{s.label}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <LineChart series={series} width={W - 60} height={H - 30} start={start} unit={unit} decimals={decimals} styleId={styleId} />
          )}
          {note ? <div style={{ marginTop: 12, fontFamily: fonts.mono, fontSize: 22, color: p.textMuted }}>{note}</div> : null}
        </div>
      </Stage>
    </AbsoluteFill>
  );
};

const LineChart: React.FC<{ series: Series[]; width: number; height: number; start: number; unit: string; decimals: number; styleId: StyleId }> = ({ series, width, height, start, unit, decimals, styleId }) => {
  const frame = useCurrentFrame();
  const p = palettes[styleId];
  const maxV = Math.max(1, ...series.map((s) => s.value));
  const padL = 70;
  const padR = 70;
  const padB = 50;
  const padT = 56;
  const n = series.length;
  const pts = series.map((s, i) => ({ x: padL + (i / Math.max(1, n - 1)) * (width - padL - padR), y: padT + (1 - s.value / maxV) * (height - padT - padB) }));
  const d = pts.map((pt, i) => `${i === 0 ? "M" : "L"} ${pt.x} ${pt.y}`).join(" ");
  const draw = interpolate(frame, [start, start + 45], [0, 1], { ...clamp, easing: ease.inOut });
  const approxLen = pts.reduce((acc, pt, i) => (i === 0 ? 0 : acc + Math.hypot(pt.x - pts[i - 1].x, pt.y - pts[i - 1].y)), 0);
  return (
    <svg width={width} height={height}>
      <defs>
        <linearGradient id="lg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={p.hero} stopOpacity={0.35} />
          <stop offset="1" stopColor={p.hero} stopOpacity={0} />
        </linearGradient>
      </defs>
      {pts.length > 1 ? <path d={`${d} L ${pts[pts.length - 1].x} ${height - padB} L ${pts[0].x} ${height - padB} Z`} fill="url(#lg)" opacity={draw} /> : null}
      <path d={d} fill="none" stroke={p.hero} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={approxLen} strokeDashoffset={approxLen * (1 - draw)} />
      {pts.map((pt, i) => {
        const vis = draw >= i / Math.max(1, n - 1) - 0.01 ? 1 : 0;
        return (
          <g key={series[i].label} opacity={vis}>
            <circle cx={pt.x} cy={pt.y} r={10} fill={p.text} stroke={p.hero} strokeWidth={4} />
            <text x={pt.x} y={pt.y - 22} textAnchor="middle" fill={p.text} fontFamily={fonts.display} fontWeight={700} fontSize={28}>
              {fmt(series[i].value, unit, decimals)}
            </text>
            <text x={pt.x} y={height - 16} textAnchor="middle" fill={p.textDim} fontFamily={fonts.mono} fontSize={22}>
              {series[i].label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
