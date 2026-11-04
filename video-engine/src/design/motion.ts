/**
 * Motion tokens: easings, spring presets, durations and transition presets.
 * Rules (from the remotion-motion-graphics craft rules):
 *  - never linear; every interpolate() is clamped both sides
 *  - entrances animate 2 or 3 properties, exits are faster than entrances
 *  - stagger 3 to 6 frames, never simultaneous entrances
 *  - the current (default seam direction) is LEFT; other vectors mean something
 */
import { Easing, interpolate, spring } from "remotion";

export const ease = {
  out: Easing.bezier(0.16, 1, 0.3, 1), // easeOutExpo, entrances
  inOut: Easing.bezier(0.83, 0, 0.17, 1), // easeInOutQuint, camera moves
  in: Easing.bezier(0.7, 0, 0.84, 0), // exits only
  soft: Easing.bezier(0.33, 1, 0.68, 1), // easeOutCubic, subtle
  snap: Easing.bezier(0.2, 0.9, 0.1, 1),
} as const;

export const springs = {
  snappy: { damping: 14, stiffness: 160, mass: 0.6 },
  smooth: { damping: 20, stiffness: 90, mass: 1 },
  bouncy: { damping: 11, stiffness: 170, mass: 0.7 },
  heavy: { damping: 26, stiffness: 60, mass: 1.4 },
  settle: { damping: 200 }, // no overshoot
} as const;

/** Durations in frames at 30fps. Scale with fps / 30 when needed. */
export const dur = {
  entrance: 20,
  exit: 10,
  staggerWord: 3,
  staggerItem: 5,
  staggerBlock: 7,
  holdShort: 15,
  holdLong: 24,
  transition: 12,
  transitionSlow: 18,
} as const;

export const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

/** Progress 0..1 for an entrance beginning at `start` (frames), spring driven. */
export const enterSpring = (
  frame: number,
  fps: number,
  start: number,
  config: Record<string, number> = springs.smooth,
) => spring({ frame: frame - start, fps, config, durationInFrames: undefined });

/** Progress 0..1 for a bezier entrance over `length` frames. */
export const enterEase = (
  frame: number,
  start: number,
  length: number = dur.entrance,
  easing = ease.out,
) => interpolate(frame, [start, start + length], [0, 1], { ...clamp, easing });

/** Progress 1..0 for an exit that ends at `end` (frames) and lasts `length`. */
export const exitEase = (
  frame: number,
  end: number,
  length: number = dur.exit,
) =>
  interpolate(frame, [end - length, end], [1, 0], { ...clamp, easing: ease.in });

/** Deterministic micro-motion for anything on screen longer than 2 seconds. */
export const breathe = (frame: number, period = 22, amount = 0.015) =>
  1 + Math.sin(frame / period) * amount;

export const floatY = (frame: number, period = 30, px = 3) =>
  Math.sin(frame / period) * px;

/** Frames per music beat for cut-on-beat placement. */
export const framesPerBeat = (fps: number, bpm: number) => (fps * 60) / bpm;

/** Seeded pseudo-random, deterministic per frame and index. */
export const seeded = (seed: number) => {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
};

/**
 * Transition presets (the "vector law"): exit and entry share an axis and a
 * direction. "current" is the neutral forward beat, others are reserved.
 */
export type SeamVector = "current" | "up" | "zoomIn" | "zoomOut" | "burst";

export const seams: Record<SeamVector, { direction: "from-right" | "from-bottom" | "from-left" | "from-top"; frames: number; meaning: string }> = {
  current: { direction: "from-right", frames: dur.transition, meaning: "next beat" },
  up: { direction: "from-bottom", frames: dur.transition, meaning: "elevation, a reveal rises" },
  zoomIn: { direction: "from-right", frames: dur.transitionSlow, meaning: "pushing deeper into the same thought" },
  zoomOut: { direction: "from-left", frames: dur.transitionSlow, meaning: "arrival, something bigger lands" },
  burst: { direction: "from-top", frames: dur.transition, meaning: "leaving a world" },
};
