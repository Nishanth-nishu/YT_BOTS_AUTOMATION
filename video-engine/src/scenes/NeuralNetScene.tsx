/**
 * NeuralNetScene: a layered network draws itself in reading order and an
 * activation wave travels from input to output, lighting the nodes it
 * passes. Layer sizes and labels come from the storyboard.
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { clamp, ease, seeded, springs } from "../design/motion";
import { fonts, palettes, type StyleId } from "../design/tokens";
import type { TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

export const NeuralNetScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const layers: number[] = scene.data.layers ?? [4, 6, 6, 3];
  const labels: string[] = scene.data.labels ?? [];
  const W = 1080;
  const H = 520;
  const padX = 150;
  const audioFrames = ((scene.audioEndMs - scene.startMs) / 1000) * fps;
  const waveStart = Math.round(audioFrames * 0.35);
  const wavePeriod = 70;
  const wave = frame >= waveStart ? ((frame - waveStart) % wavePeriod) / wavePeriod : -1; // 0..1 across layers

  const pos = layers.map((n, li) => {
    const x = padX + (li / Math.max(1, layers.length - 1)) * (W - padX * 2);
    const spacing = Math.min(70, (H - 100) / Math.max(1, n));
    const y0 = H / 2 - ((n - 1) * spacing) / 2;
    return Array.from({ length: n }).map((_, ni) => ({ x, y: y0 + ni * spacing }));
  });

  return (
    <AbsoluteFill>
      <ParticleField count={30} scale={particleScale} styleId={styleId} seed={81} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "NEURAL NETWORK"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 20 }}>
          <defs>
            <filter id="nnglow"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>
          {pos.slice(0, -1).map((layer, li) =>
            layer.map((a, ai) =>
              pos[li + 1].map((b, bi) => {

                const edgeIn = interpolate(frame, [10 + li * 12, 24 + li * 12], [0, 1], { ...clamp, easing: ease.out });
                const lit = wave >= 0 && Math.abs(wave * (layers.length - 1) - (li + 0.5)) < 0.55;
                const w = 0.6 + seeded(li * 100 + ai * 10 + bi) * 1.6;
                return <line key={`${li}-${ai}-${bi}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={lit ? p.hero : p.line} strokeWidth={lit ? w + 1 : w} opacity={edgeIn * (lit ? 0.95 : 0.7)} />;
              }),
            ),
          )}
          {pos.map((layer, li) =>
            layer.map((n, ni) => {
              const s = spring({ frame: frame - 6 - li * 12 - ni * 2, fps, config: springs.snappy });
              const lit = wave >= 0 && Math.abs(wave * (layers.length - 1) - li) < 0.5;
              const isOut = li === layers.length - 1;
              const r = (isOut ? 18 : 14) * s;
              return (
                <g key={`${li}-${ni}`}>
                  <circle cx={n.x} cy={n.y} r={r} fill={lit ? p.hero : p.surface} stroke={lit ? p.hero : p.textMuted} strokeWidth={2.5} filter={lit ? "url(#nnglow)" : undefined} />
                </g>
              );
            }),
          )}
          {labels.map((label, li) => (
            <text key={label} x={pos[li]?.[0]?.x ?? 0} y={H - 10} textAnchor="middle" fill={p.textDim} fontFamily={fonts.mono} fontSize={22} letterSpacing={1}>
              {label}
            </text>
          ))}
        </svg>
      </Stage>
    </AbsoluteFill>
  );
};
