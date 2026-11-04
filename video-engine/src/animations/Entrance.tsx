/**
 * Entrance / exit / stagger primitives. Every entrance moves 2 or 3
 * properties together (opacity + translate + scale). Exits are faster.
 */
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, dur, ease, springs } from "../design/motion";

type EntranceProps = {
  delay?: number; // frames, relative to the enclosing Sequence
  from?: "below" | "above" | "left" | "right" | "scale" | "none";
  distance?: number;
  config?: Record<string, number>;
  exitAt?: number; // frame at which the exit should be complete
  exitLength?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
};

export const Entrance: React.FC<EntranceProps> = ({
  delay = 0,
  from = "below",
  distance = 44,
  config = springs.smooth,
  exitAt,
  exitLength = dur.exit,
  style,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config });
  const exit =
    exitAt === undefined
      ? 1
      : interpolate(frame, [exitAt - exitLength, exitAt], [1, 0], {
          ...clamp,
          easing: ease.in,
        });

  const x = from === "left" ? -distance : from === "right" ? distance : 0;
  const y = from === "below" ? distance : from === "above" ? -distance : 0;
  const tx = interpolate(p, [0, 1], [x, 0]);
  const ty = interpolate(p, [0, 1], [y, 0]) + (1 - exit) * -28;
  const sc = from === "scale" ? interpolate(p, [0, 1], [0.86, 1]) : interpolate(p, [0, 1], [0.95, 1]);

  return (
    <div
      style={{
        opacity: p * exit,
        translate: `${tx}px ${ty}px`,
        scale: `${sc * (0.96 + 0.04 * exit)}`,
        willChange: "transform, opacity",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

type StaggerProps = {
  start?: number;
  step?: number;
  from?: EntranceProps["from"];
  config?: Record<string, number>;
  exitAt?: number;
  style?: React.CSSProperties;
  children: React.ReactNode[];
};

export const Stagger: React.FC<StaggerProps> = ({
  start = 0,
  step = dur.staggerItem,
  from = "below",
  config,
  exitAt,
  style,
  children,
}) => (
  <>
    {React.Children.map(children, (child, i) => (
      <Entrance
        delay={start + i * step}
        from={from}
        config={config}
        exitAt={exitAt === undefined ? undefined : exitAt + i * 1}
        style={style}
      >
        {child}
      </Entrance>
    ))}
  </>
);

/** Wrap a whole scene so it exits before its sequence ends. */
export const SceneExit: React.FC<{ length?: number; children: React.ReactNode }> = ({
  length = dur.exit,
  children,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = interpolate(frame, [durationInFrames - length, durationInFrames - 1], [1, 0], {
    ...clamp,
    easing: ease.in,
  });
  const y = interpolate(frame, [durationInFrames - length, durationInFrames - 1], [0, -30], {
    ...clamp,
    easing: ease.in,
  });
  return (
    <div style={{ position: "absolute", inset: 0, opacity: o, translate: `0px ${y}px` }}>
      {children}
    </div>
  );
};

/** Deterministic idle motion for anything that stays on screen for a while. */
export const Breathe: React.FC<{ period?: number; amount?: number; floatPx?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  period = 24,
  amount = 0.012,
  floatPx = 3,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const s = 1 + Math.sin(frame / period) * amount;
  const y = Math.sin(frame / (period * 1.37)) * floatPx;
  return (
    <div style={{ scale: `${s}`, translate: `0px ${y}px`, ...style }}>{children}</div>
  );
};
