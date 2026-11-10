/**
 * Presenter: the animated host, a stylised male avatar drawn in SVG whose
 * mouth follows the voice track (spec.presenter.envelope, one value per
 * frame), with deterministic blinks, head bob, eyebrow lifts on loud
 * syllables and, in "hype" mood, a sweat drop and "!!" for the hook.
 *
 *   <PresenterContext.Provider value={...}>   set once in Reel
 *   <Avatar ... />                              the drawing, any size
 *   <PresenterPip ... />                        the small badge in the caption band
 *   <PresenterHero ... />                       the big version for the hook scene
 *
 * Every motion is a pure function of the frame, so renders are identical.
 */
import React, { createContext, useContext } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, seeded, springs } from "../design/motion";
import { fonts, palettes, type StyleId } from "../design/tokens";
import type { PresenterSpec } from "../schema/reelSpec";

export type PresenterData = (PresenterSpec & { styleId: StyleId }) | null;
export const PresenterContext = createContext<PresenterData>(null);
export const usePresenter = () => useContext(PresenterContext);

/** Mouth openness for a global frame, lightly smoothed. */
export const mouthAt = (env: number[], frame: number): number => {
  if (!env.length) {
    return 0;
  }
  const i = Math.max(0, Math.min(env.length - 1, Math.round(frame)));
  const a = env[Math.max(0, i - 1)];
  const b = env[i];
  const c = env[Math.min(env.length - 1, i + 1)];
  return Math.max(b, (a + b + c) / 3);
};

/** 0..1 blink amount: a 5-frame blink every 70 to 120 frames, seeded. */
export const blinkAt = (frame: number, seed: number): number => {
  let t = 30 + Math.floor(seeded(seed) * 50);
  while (t + 5 < frame) {
    t += 70 + Math.floor(seeded(seed + t) * 50);
  }
  const d = frame - t;
  if (d < 0 || d > 5) {
    return 0;
  }
  return Math.sin((d / 5) * Math.PI);
};

const SKIN = "#E9B98C";
const SKIN_DARK = "#C9935F";
const HAIR = "#1E1726";
const LIPS = "#8C4A4A";
const MOUTH = "#3A1C27";

type AvatarProps = {
  /** Global frame used for the envelope (scene-local frame + scene start). */
  globalFrame: number;
  envelope: number[];
  styleId: StyleId;
  mood: "hype" | "calm";
  size: number; // rendered height in px (viewBox is 400 x 440)
  /** Frames since this avatar appeared (for the hook's sweat drop and "!!"). */
  sinceAppear?: number;
  hero?: boolean;
  seed?: number;
};

export const Avatar: React.FC<AvatarProps> = ({ globalFrame, envelope, styleId, mood, size, sinceAppear = 9999, hero = false, seed = 7 }) => {
  const p = palettes[styleId];
  const { fps } = useVideoConfig();
  const open = mouthAt(envelope, globalFrame);
  const blink = blinkAt(globalFrame, seed);
  const talking = open > 0.08;
  // Head bob: slow idle sway plus a nod that follows speech energy.
  const bobY = Math.sin(globalFrame / 23) * 3 + open * 4;
  const rot = Math.sin(globalFrame / 41) * 1.6 + (talking ? Math.sin(globalFrame / 5) * open * 1.2 : 0);
  const browRaise = (mood === "hype" ? 4 : 1) + open * 7;
  const mouthH = 5 + open * 34;
  const closed = interpolate(open, [0, 0.12], [1, 0], clamp);
  const teethH = Math.max(0, Math.min(11, (mouthH - 10) * 0.45));
  // Hook extras: a shake in the first 18 frames, "!!" pops at frame 8, sweat drop slides 14..70.
  const shake = hero && sinceAppear < 18 ? Math.sin(sinceAppear * 2.6) * (18 - sinceAppear) * 0.5 : 0;
  const bang = hero ? spring({ frame: sinceAppear - 8, fps, config: springs.bouncy }) : 0;
  const bangFade = hero ? 1 - interpolate(sinceAppear, [70, 90], [0, 1], clamp) : 0;
  const drop = hero ? interpolate(sinceAppear, [14, 70], [0, 1], clamp) : 0;
  const dropOp = hero ? interpolate(sinceAppear, [14, 20, 62, 72], [0, 1, 1, 0], clamp) : 0;
  const w = (size * 400) / 440;

  return (
    <svg width={w} height={size} viewBox="0 0 400 440" style={{ display: "block", overflow: "visible" }}>
      {/* torso: hoodie in the hero colour */}
      <g transform={`translate(${shake} 0)`}>
        <rect x={44} y={318} width={312} height={170} rx={78} fill={p.hero} />
        <rect x={44} y={318} width={312} height={170} rx={78} fill="rgba(0,0,0,0.28)" />
        <path d="M 120 318 C 140 300, 170 296, 200 300 C 230 296, 260 300, 280 318 C 262 352, 232 366, 200 366 C 168 366, 138 352, 120 318 Z" fill={p.hero} opacity={0.9} />
        <rect x={172} y={248} width={56} height={80} rx={18} fill={SKIN_DARK} />
        {/* headphone band */}
        <g transform={`translate(0 ${bobY}) rotate(${rot} 200 190)`}>
          <path d="M 104 178 C 104 68, 296 68, 296 178" stroke={p.accent} strokeWidth={11} fill="none" strokeLinecap="round" />
          {/* ears and face */}
          <circle cx={112} cy={196} r={19} fill={SKIN} />
          <circle cx={288} cy={196} r={19} fill={SKIN} />
          <ellipse cx={200} cy={192} rx={92} ry={108} fill={SKIN} />
          {/* stubble */}
          <ellipse cx={200} cy={262} rx={64} ry={38} fill={HAIR} opacity={0.13} />
          {/* hair cap with a quiff */}
          <path d="M 108 176 C 98 64, 302 64, 292 176 C 282 136, 252 118, 200 118 C 148 118, 118 136, 108 176 Z" fill={HAIR} />
          <path d="M 150 92 C 168 44, 236 36, 268 78 C 248 66, 214 70, 196 96 Z" fill={HAIR} />
          {/* headphone cups */}
          <rect x={86} y={166} width={28} height={58} rx={12} fill={p.surface} stroke={p.accent} strokeWidth={4} />
          <rect x={286} y={166} width={28} height={58} rx={12} fill={p.surface} stroke={p.accent} strokeWidth={4} />
          {/* eyebrows */}
          <g transform={`translate(0 ${-browRaise})`}>
            <path d="M 138 152 Q 162 138 186 150" stroke={HAIR} strokeWidth={9} strokeLinecap="round" fill="none" />
            <path d="M 214 150 Q 238 138 262 152" stroke={HAIR} strokeWidth={9} strokeLinecap="round" fill="none" />
          </g>
          {/* eyes (blink by squashing) */}
          <g transform={`translate(0 ${174 * blink * 0.9}) scale(1 ${1 - blink * 0.9})`}>
            <ellipse cx={163} cy={174} rx={17} ry={12} fill="#FFFFFF" />
            <ellipse cx={237} cy={174} rx={17} ry={12} fill="#FFFFFF" />
            <circle cx={166} cy={175} r={7.5} fill={HAIR} />
            <circle cx={240} cy={175} r={7.5} fill={HAIR} />
            <circle cx={169} cy={172} r={2.6} fill="#FFFFFF" />
            <circle cx={243} cy={172} r={2.6} fill="#FFFFFF" />
          </g>
          {/* glasses */}
          <rect x={140} y={158} width={48} height={34} rx={11} stroke={p.accent} strokeWidth={4} fill="rgba(255,255,255,0.06)" />
          <rect x={212} y={158} width={48} height={34} rx={11} stroke={p.accent} strokeWidth={4} fill="rgba(255,255,255,0.06)" />
          <path d="M 188 174 L 212 174" stroke={p.accent} strokeWidth={4} />
          {/* nose */}
          <path d="M 200 186 L 193 212 L 207 212" stroke={SKIN_DARK} strokeWidth={4.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          {/* mouth: open shape plus a closed smile that fades in when quiet */}
          <rect x={172} y={238 - mouthH / 2} width={56} height={mouthH} rx={mouthH / 2} fill={MOUTH} />
          {teethH > 0 ? <rect x={177} y={238 - mouthH / 2 + 4} width={46} height={teethH} rx={4} fill="#FFFFFF" opacity={0.92} /> : null}
          <path d="M 170 238 Q 200 254 230 238" stroke={LIPS} strokeWidth={5} fill="none" strokeLinecap="round" opacity={closed} />
          {/* hype extras for the hook */}
          {hero ? (
            <>
              <path d="M 270 150 C 282 132, 292 152, 282 162 C 276 168, 266 160, 270 150 Z" fill={p.accent} opacity={dropOp} transform={`translate(0 ${drop * 58})`} />
              <text x={318} y={92} fontFamily={fonts.display} fontWeight={800} fontSize={74} fill={p.hero} opacity={bang * bangFade} transform={`rotate(12 318 92) scale(${bang})`} style={{ transformOrigin: "318px 92px" }}>
                !!
              </text>
            </>
          ) : null}
        </g>
      </g>
    </svg>
  );
};

/** Small badge at the left of the caption band, shown outside the hook scene. */
export const PresenterPip: React.FC<{ hiddenUntilFrame: number; x?: number; y?: number; size?: number }> = ({ hiddenUntilFrame, x = 58, y = 1178, size = 226 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const data = usePresenter();
  if (!data || !data.enabled) {
    return null;
  }
  const p = palettes[data.styleId];
  const enter = spring({ frame: frame - hiddenUntilFrame, fps, config: springs.bouncy });
  if (frame < hiddenUntilFrame - 2) {
    return null;
  }
  const open = mouthAt(data.envelope, frame);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width: size,
          height: size,
          borderRadius: "50%",
          overflow: "hidden",
          background: `radial-gradient(circle at 50% 30%, ${p.surface}, ${p.bgAlt})`,
          border: `4px solid ${p.hero}`,
          boxShadow: `0 0 ${28 + open * 26}px ${p.glow}, 0 14px 30px rgba(0,0,0,0.45)`,
          scale: `${interpolate(enter, [0, 1], [0.4, 1])}`,
          opacity: enter,
        }}
      >
        <div style={{ position: "absolute", left: "50%", top: 14, translate: "-50% 0" }}>
          <Avatar globalFrame={frame} envelope={data.envelope} styleId={data.styleId} mood={data.mood} size={size * 1.32} seed={11} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** The big host for the hook scene, in the stage region under the title. */
export const PresenterHero: React.FC<{ sceneStartFrame: number; top?: number; size?: number }> = ({ sceneStartFrame, top = 596, size = 590 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const data = usePresenter();
  if (!data || !data.enabled) {
    return null;
  }
  const p = palettes[data.styleId];
  const enter = spring({ frame: frame - 2, fps, config: springs.bouncy });
  const w = (size * 400) / 440;
  return (
    <div
      style={{
        position: "absolute",
        left: 540 - w / 2,
        top,
        width: w,
        height: size,
        scale: `${interpolate(enter, [0, 1], [0.7, 1])}`,
        opacity: enter,
        transformOrigin: "50% 100%",
        // soft bottom edge so the bust fades into the frame instead of a hard cut
        maskImage: "linear-gradient(180deg, black 84%, transparent 100%)",
        WebkitMaskImage: "linear-gradient(180deg, black 84%, transparent 100%)",
      }}
    >
      <div style={{ position: "absolute", left: "50%", top: size * 0.42, width: size * 0.9, height: size * 0.9, translate: "-50% -50%", borderRadius: "50%", background: `radial-gradient(circle, ${p.glow}, transparent 62%)`, filter: "blur(18px)" }} />
      <Avatar globalFrame={frame + sceneStartFrame} envelope={data.envelope} styleId={data.styleId} mood={data.mood} size={size} sinceAppear={frame} hero seed={5} />
    </div>
  );
};
