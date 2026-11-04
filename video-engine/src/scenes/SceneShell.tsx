/**
 * SceneShell: wraps a scene with entry and exit motion that obey the vector
 * law. The seam describes how THIS scene exits; the next scene reads the
 * previous scene's seam to decide how it enters (same axis, same direction,
 * cut mid-motion on both sides).
 */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, dur, ease } from "../design/motion";
import type { SeamVector } from "../design/motion";
import { WordReveal, Kicker } from "../typography/Text";
import type { StyleId } from "../design/tokens";
import { Entrance } from "../animations/Entrance";

/**
 * Vertical layout for 1080x1920 (all scenes share it):
 *   kicker + title   340 .. ~610   (title auto-sizes to at most 2 or 3 lines)
 *   stage            620 .. 1180
 *   captions        1230 .. 1400
 *   platform UI     1420 .. 1920   (never place content here)
 */
export const LAYOUT = { titleTop: 340, stageTop: 620, stageHeight: 560, captionTop: 1230 } as const;

/** Headline size from character count so titles never exceed ~3 lines. */
export const titleSize = (text: string, hero = false) => {
  const n = text.length;
  if (hero) {
    return n <= 22 ? 112 : n <= 32 ? 96 : n <= 42 ? 84 : 72;
  }
  return n <= 22 ? 96 : n <= 34 ? 84 : n <= 46 ? 72 : 62;
};

type Props = {
  enterFrom: SeamVector | null; // the previous scene's seam
  exitWith: SeamVector | null; // this scene's seam (null for the last scene)
  children: React.ReactNode;
};

const ENTER = 14;
const EXIT = 10;

export const SceneShell: React.FC<Props> = ({ enterFrom, exitWith, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  const e = enterFrom === null ? 1 : interpolate(frame, [0, ENTER], [0, 1], { ...clamp, easing: ease.out });
  const x = exitWith === null ? 0 : interpolate(frame, [durationInFrames - EXIT, durationInFrames], [0, 1], { ...clamp, easing: ease.in });

  let tx = 0;
  let ty = 0;
  let sc = 1;
  let blur = 0;
  let op = 1;

  // Entry: continue the previous scene's vector.
  switch (enterFrom) {
    case "current":
      tx += (1 - e) * width * 0.55;
      op *= interpolate(e, [0, 0.5], [0, 1], clamp);
      break;
    case "up":
      ty += (1 - e) * height * 0.35;
      op *= interpolate(e, [0, 0.5], [0, 1], clamp);
      break;
    case "zoomIn":
      sc *= interpolate(e, [0, 1], [0.86, 1]);
      op *= interpolate(e, [0, 0.6], [0, 1], clamp);
      blur += (1 - e) * 10;
      break;
    case "zoomOut":
      sc *= interpolate(e, [0, 1], [1.16, 1]);
      op *= interpolate(e, [0, 0.6], [0, 1], clamp);
      blur += (1 - e) * 8;
      break;
    case "burst":
      ty += (1 - e) * -height * 0.3;
      sc *= interpolate(e, [0, 1], [1.3, 1]);
      op *= interpolate(e, [0, 0.5], [0, 1], clamp);
      break;
    default:
      break;
  }

  // Exit: start this scene's vector.
  switch (exitWith) {
    case "current":
      tx += x * -width * 0.55;
      op *= 1 - interpolate(x, [0.4, 1], [0, 1], clamp);
      break;
    case "up":
      ty += x * -height * 0.35;
      op *= 1 - interpolate(x, [0.4, 1], [0, 1], clamp);
      break;
    case "zoomIn":
      sc *= interpolate(x, [0, 1], [1, 1.18]);
      op *= 1 - interpolate(x, [0.3, 1], [0, 1], clamp);
      blur += x * 10;
      break;
    case "zoomOut":
      sc *= interpolate(x, [0, 1], [1, 0.86]);
      op *= 1 - interpolate(x, [0.3, 1], [0, 1], clamp);
      blur += x * 8;
      break;
    case "burst":
      sc *= interpolate(x, [0, 1], [1, 1.6]);
      op *= 1 - interpolate(x, [0.2, 1], [0, 1], clamp);
      blur += x * 16;
      break;
    default:
      break;
  }

  return (
    <AbsoluteFill
      style={{
        translate: `${tx}px ${ty}px`,
        scale: `${sc}`,
        opacity: op,
        filter: blur > 0.2 ? `blur(${blur}px)` : undefined,
        transformOrigin: "50% 45%",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

/** Standard title block at the top of the safe zone. */
export const TitleBlock: React.FC<{ children: React.ReactNode; top?: number }> = ({ children, top = LAYOUT.titleTop }) => (
  <div style={{ position: "absolute", top, left: 80, right: 120 }}>{children}</div>
);

/** Kicker + auto-sized kinetic headline, shared by every scene. */
export const SceneTitle: React.FC<{
  kicker: string;
  title: string;
  highlight: string[];
  styleId: StyleId;
  hero?: boolean;
  strike?: string[];
  strikeAt?: number;
  top?: number;
}> = ({ kicker, title, highlight, styleId, hero = false, strike, strikeAt, top }) => (
  <TitleBlock top={top}>
    <Entrance delay={0} from="left">
      <Kicker styleId={styleId}>{kicker}</Kicker>
    </Entrance>
    <div style={{ height: hero ? 34 : 26 }} />
    <WordReveal
      text={title}
      delay={hero ? 8 : 4}
      per={3}
      size={titleSize(title, hero)}
      highlight={highlight}
      styleId={styleId}
      maxWidth={880}
      strike={strike}
      strikeAt={strikeAt}
    />
  </TitleBlock>
);

/** Visual stage region between title and captions. */
export const Stage: React.FC<{ children: React.ReactNode; top?: number; height?: number }> = ({ children, top = LAYOUT.stageTop, height = LAYOUT.stageHeight }) => (
  <div style={{ position: "absolute", top, left: 0, width: 1080, height, overflow: "visible" }}>{children}</div>
);

export const exitFrameFor = (durationInFrames: number) => durationInFrames - dur.exit;
