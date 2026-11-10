/**
 * Presenter: the animated host, a stylised guy drawn in SVG whose mouth
 * follows the voice track (spec.presenter.envelope, one value per frame),
 * with deterministic blinks, head bob, eyebrow lifts on loud syllables and,
 * in "hype" mood, a sweat drop and "!!" for the hook.
 *
 * Looks (spec.presenter.look), all built from the same face rig:
 *   curly   big curly hair, full beard, headphones round the neck, no glasses
 *   waves   long wavy hair swept back, trimmed beard, headphones round the neck
 *   fade    short curly top with faded sides, beard, headphones on
 *   shades  curly hair and beard with dark tinted glasses
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
import { ImageHost, HOST_H, HOST_W, type Rig } from "./ImageHost";
import { VrmHost } from "./VrmHost";

export type PresenterLook = "curly" | "waves" | "fade" | "shades" | "image" | "vrm";
export const LOOKS: Exclude<PresenterLook, "image" | "vrm">[] = ["curly", "waves", "fade", "shades"];

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

const SKIN = "#C98B5E";
const SKIN_SHADE = "#A96E45";
const HAIR = "#15110F";
const HAIR_SHINE = "#3A2F2A";
const BEARD = "#1C1512";
const HOODIE = "#111115";
const HOODIE_EDGE = "#2A2A33";
const JACKET = "#1A1A20";
const JACKET_EDGE = "#30303A";
const WATCH = "#6F7278";
const WATCH_FACE = "#2A2D33";
const LIPS = "#8E5A52";
const MOUTH = "#3A1C27";
const HEAD_CY = 190;

/** Deterministic curl cluster: circles packed around an arc above the head. */
const Curls: React.FC<{ seed: number; count: number; cx: number; cy: number; rx: number; ry: number; rMin: number; rMax: number; fill: string }> = ({ seed, count, cx, cy, rx, ry, rMin, rMax, fill }) => (
  <>
    {Array.from({ length: count }).map((_, i) => {
      const a = Math.PI + (i / (count - 1)) * Math.PI; // left to right over the top
      const jitter = (seeded(seed + i) - 0.5) * 0.35;
      const x = cx + Math.cos(a + jitter) * rx;
      const y = cy + Math.sin(a + jitter) * ry;
      const r = rMin + seeded(seed * 7 + i) * (rMax - rMin);
      return <circle key={i} cx={x} cy={y} r={r} fill={fill} />;
    })}
  </>
);

type AvatarProps = {
  /** Global frame used for the envelope (scene-local frame + scene start). */
  globalFrame: number;
  envelope: number[];
  styleId: StyleId;
  mood: "hype" | "calm";
  look?: Exclude<PresenterLook, "image" | "vrm">;
  size: number; // rendered height in px (viewBox is 400 x 440)
  /** Frames since this avatar appeared (for the hook's sweat drop and "!!"). */
  sinceAppear?: number;
  hero?: boolean;
  seed?: number;
};

export const Avatar: React.FC<AvatarProps> = ({ globalFrame, envelope, styleId, mood, look = "curly", size, sinceAppear = 9999, hero = false, seed = 7 }) => {
  const p = palettes[styleId];
  const { fps } = useVideoConfig();
  const open = mouthAt(envelope, globalFrame);
  const blink = blinkAt(globalFrame, seed);
  const talking = open > 0.08;
  const bobY = Math.sin(globalFrame / 23) * 3 + open * 4;
  const rot = Math.sin(globalFrame / 41) * 1.6 + (talking ? Math.sin(globalFrame / 5) * open * 1.2 : 0);
  const browRaise = (mood === "hype" ? 3 : 0) + open * 6;
  const mouthH = 5 + open * 30;
  const closed = interpolate(open, [0, 0.12], [1, 0], clamp);
  const teethH = Math.max(0, Math.min(10, (mouthH - 10) * 0.45));
  const shake = hero && sinceAppear < 18 ? Math.sin(sinceAppear * 2.6) * (18 - sinceAppear) * 0.5 : 0;
  const bang = hero ? spring({ frame: sinceAppear - 8, fps, config: springs.bouncy }) : 0;
  const bangFade = hero ? 1 - interpolate(sinceAppear, [70, 90], [0, 1], clamp) : 0;
  const drop = hero ? interpolate(sinceAppear, [14, 70], [0, 1], clamp) : 0;
  const dropOp = hero ? interpolate(sinceAppear, [14, 20, 62, 72], [0, 1, 1, 0], clamp) : 0;
  const w = (size * 400) / 440;
  const B = look === "curly" ? 462 : 490; // bottom edge of the bust

  const headphonesOnNeck = look === "curly" || look === "waves" || look === "shades";
  const fullBeard = look !== "waves";
  const shortBeard = look === "curly"; // closer crop, reads as a few days' growth
  const beardOpacity = shortBeard ? 0.62 : 0.92;
  const smile = look === "curly" ? 1 : 0; // resting smile and slightly more open eyes
  const glasses = look === "shades" ? "shades" : "none";

  // Face with a defined jaw (not an ellipse): wide at the temples, squarer chin.
  const FACE = "M 110 150 C 112 96, 288 96, 290 150 C 296 214, 276 282, 236 300 C 214 310, 186 310, 164 300 C 124 282, 104 214, 110 150 Z";
  // Full beard following the jaw, up to the sideburns; moustache separate.
  // Outer edge follows the jaw; inner edge runs under the cheekbones and the mouth.
  const BEARD_PATH = "M 112 190 C 114 262, 146 298, 200 306 C 254 298, 286 262, 288 190 C 276 214, 264 228, 240 244 C 224 254, 212 258, 200 258 C 188 258, 176 254, 160 244 C 136 228, 124 214, 112 190 Z";
  const TRIM_BEARD = "M 126 226 C 134 272, 162 296, 200 302 C 238 296, 266 272, 274 226 C 266 258, 246 276, 226 284 C 210 290, 190 290, 174 284 C 154 276, 134 258, 126 226 Z";

  return (
    // The drawing is shifted down 80 units inside a taller viewBox so the big
    // hair never sits above y=0 (Chrome clipped it there inside transformed
    // parents); the negative margin keeps the face where a 400 x 440 drawing
    // would put it.
    <svg width={w} height={size + (80 * size) / 440} viewBox="0 0 400 520" style={{ display: "block", overflow: "visible", marginTop: -(80 * size) / 440 }}>
      <g transform={`translate(${shake} 80)`}>
        {/* black hoodie / sweater */}
        <rect x={40} y={318} width={320} height={B - 318} rx={80} fill={HOODIE} />
        <path d={`M 40 398 C 40 350, 80 318, 120 318 L 280 318 C 320 318, 360 350, 360 398 L 360 ${B} L 40 ${B} Z`} fill={HOODIE} />
        <path d="M 112 318 C 134 296, 166 288, 200 292 C 234 288, 266 296, 288 318 C 268 356, 236 374, 200 374 C 164 374, 132 356, 112 318 Z" fill={HOODIE_EDGE} />
        <path d="M 124 322 C 146 304, 172 298, 200 300 C 228 298, 254 304, 276 322 C 258 352, 232 364, 200 364 C 168 364, 142 352, 124 322 Z" fill={HOODIE} />
        <rect x={170} y={252} width={60} height={80} rx={18} fill={SKIN_SHADE} />
        {headphonesOnNeck ? (
          <g>
            {/* headphones resting round the neck, cups on the chest */}
            <path d="M 128 300 C 120 350, 160 372, 200 372 C 240 372, 280 350, 272 300" stroke="#1B1B20" strokeWidth={12} fill="none" strokeLinecap="round" />
            <ellipse cx={150} cy={356} rx={30} ry={38} fill="#0E0E12" stroke="#2C2C34" strokeWidth={4} />
            <ellipse cx={150} cy={356} rx={16} ry={22} fill="#1A1A20" />
            <ellipse cx={250} cy={356} rx={30} ry={38} fill="#0E0E12" stroke="#2C2C34" strokeWidth={4} />
            <ellipse cx={250} cy={356} rx={16} ry={22} fill="#1A1A20" />
          </g>
        ) : null}
        {look === "curly" ? (
          <g>
            {/* open zip jacket: two panels leaving a V of sweater, collar, zip teeth */}
            <path d={`M 40 400 C 40 352, 78 322, 118 318 C 150 318, 168 340, 178 372 L 168 ${B} L 40 ${B} Z`} fill={JACKET} />
            <path d={`M 360 400 C 360 352, 322 322, 282 318 C 250 318, 232 340, 222 372 L 232 ${B} L 360 ${B} Z`} fill={JACKET} />
            <path d="M 118 318 C 150 318, 168 340, 178 372" stroke={JACKET_EDGE} strokeWidth={5} fill="none" />
            <path d="M 282 318 C 250 318, 232 340, 222 372" stroke={JACKET_EDGE} strokeWidth={5} fill="none" />
            <path d={`M 178 372 L 170 ${B}`} stroke={JACKET_EDGE} strokeWidth={3} strokeDasharray="4 4" />
            <path d={`M 222 372 L 230 ${B}`} stroke={JACKET_EDGE} strokeWidth={3} strokeDasharray="4 4" />
            {/* folded arms resting on the counter, watch on the near wrist */}
            {/* near forearm in the sweater sleeve, crossing the chest left to right */}
            <path d="M 40 440 C 56 400, 120 386, 210 392 C 270 396, 300 398, 318 404 L 318 452 C 300 456, 260 458, 210 454 C 120 450, 60 456, 40 440 Z" fill={HOODIE} stroke={JACKET_EDGE} strokeWidth={3} />
            <path d="M 58 428 C 100 410, 160 404, 212 408" stroke={JACKET_EDGE} strokeWidth={3} fill="none" strokeLinecap="round" opacity={0.6} />
            {/* grey watch on the wrist */}
            <rect x={292} y={398} width={24} height={60} rx={6} fill={WATCH} />
            <circle cx={304} cy={428} r={16} fill={WATCH_FACE} stroke={WATCH} strokeWidth={4} />
            <path d="M 304 428 L 304 419 M 304 428 L 310 431" stroke="#C9CCD2" strokeWidth={2.5} strokeLinecap="round" />
            {/* hand gripping the far upper arm */}
            <path d="M 316 406 C 334 400, 356 404, 362 418 C 366 432, 360 448, 344 452 C 330 456, 318 450, 316 440 Z" fill={SKIN} />
            <path d="M 328 416 L 352 414 M 330 428 L 356 428 M 332 440 L 352 442" stroke={SKIN_SHADE} strokeWidth={2.5} strokeLinecap="round" />
          </g>
        ) : null}
        <g transform={`translate(0 ${bobY}) rotate(${rot} 200 ${HEAD_CY})`}>
          {/* hair, back layer */}
          {look === "curly" ? (
            <g>
              <Curls seed={3} count={18} cx={200} cy={146} rx={140} ry={128} rMin={38} rMax={54} fill={HAIR} />
              <Curls seed={5} count={16} cx={200} cy={140} rx={118} ry={104} rMin={36} rMax={52} fill={HAIR} />
              <Curls seed={9} count={11} cx={200} cy={124} rx={84} ry={70} rMin={36} rMax={52} fill={HAIR} />
              <ellipse cx={200} cy={128} rx={130} ry={110} fill={HAIR} />
              <path d="M 86 170 C 76 236, 92 276, 110 296 L 122 200 Z" fill={HAIR} />
              <path d="M 314 170 C 324 236, 308 276, 290 296 L 278 200 Z" fill={HAIR} />
            </g>
          ) : null}
          {look === "shades" ? (
            <g>
              <Curls seed={3} count={14} cx={200} cy={150} rx={118} ry={104} rMin={34} rMax={50} fill={HAIR} />
              <Curls seed={9} count={11} cx={200} cy={132} rx={84} ry={70} rMin={36} rMax={52} fill={HAIR} />
              <ellipse cx={200} cy={132} rx={112} ry={92} fill={HAIR} />
              <path d="M 94 170 C 86 230, 98 270, 112 290 L 122 200 Z" fill={HAIR} />
              <path d="M 306 170 C 314 230, 302 270, 288 290 L 278 200 Z" fill={HAIR} />
            </g>
          ) : null}
          {look === "waves" ? (
            <g>
              <path d="M 96 150 C 84 60, 316 60, 304 150 C 318 226, 320 296, 300 340 C 282 334, 264 322, 256 302 L 144 302 C 136 322, 118 334, 100 340 C 80 296, 82 226, 96 150 Z" fill={HAIR} />
              <path d="M 114 190 C 104 240, 108 290, 118 326" stroke={HAIR_SHINE} strokeWidth={5} fill="none" strokeLinecap="round" opacity={0.5} />
              <path d="M 286 190 C 296 240, 292 290, 282 326" stroke={HAIR_SHINE} strokeWidth={5} fill="none" strokeLinecap="round" opacity={0.5} />
            </g>
          ) : null}
          {look === "fade" ? <ellipse cx={200} cy={150} rx={94} ry={86} fill={HAIR} opacity={0.55} /> : null}
          {!headphonesOnNeck ? <path d="M 104 178 C 104 68, 296 68, 296 178" stroke={p.accent} strokeWidth={11} fill="none" strokeLinecap="round" /> : null}
          {/* ears and face */}
          <circle cx={112} cy={198} r={19} fill={SKIN} />
          <circle cx={288} cy={198} r={19} fill={SKIN} />
          <path d={FACE} fill={SKIN} />
          {/* cheek and jaw shading */}
          <path d="M 128 232 C 150 288, 250 288, 272 232 C 262 272, 236 296, 200 300 C 164 296, 138 272, 128 232 Z" fill={SKIN_SHADE} opacity={0.22} />
          {/* beard and moustache */}
          {fullBeard ? <path d={BEARD_PATH} fill={BEARD} opacity={beardOpacity} /> : <path d={TRIM_BEARD} fill={BEARD} opacity={0.5} />}
          <path d="M 168 218 C 182 208, 218 208, 232 218 C 222 224, 208 226, 200 224 C 192 226, 178 224, 168 218 Z" fill={BEARD} opacity={fullBeard ? beardOpacity : 0.55} />
          {/* hair, front layer */}
          {look === "curly" || look === "shades" ? (
            <g>
              <path d="M 108 160 C 100 100, 300 100, 292 160 C 284 128, 256 116, 200 114 C 144 116, 116 128, 108 160 Z" fill={HAIR} />
              <Curls seed={21} count={12} cx={200} cy={look === "curly" ? 116 : 128} rx={96} ry={46} rMin={28} rMax={40} fill={HAIR} />
              <Curls seed={33} count={7} cx={200} cy={look === "curly" ? 92 : 106} rx={60} ry={30} rMin={22} rMax={30} fill={HAIR_SHINE} />
              <Curls seed={34} count={7} cx={200} cy={look === "curly" ? 96 : 110} rx={60} ry={30} rMin={18} rMax={26} fill={HAIR} />
            </g>
          ) : null}
          {look === "waves" ? (
            <g>
              <path d="M 108 176 C 98 64, 302 64, 292 176 C 286 130, 262 112, 232 110 C 214 110, 196 122, 176 140 C 160 118, 136 122, 118 140 C 112 150, 108 162, 108 176 Z" fill={HAIR} />
              <path d="M 150 86 C 176 42, 250 38, 276 86 C 256 70, 224 72, 210 94 C 196 78, 170 80, 150 86 Z" fill={HAIR} />
              <path d="M 166 104 C 196 92, 228 92, 256 104" stroke={HAIR_SHINE} strokeWidth={4} fill="none" strokeLinecap="round" opacity={0.7} />
            </g>
          ) : null}
          {look === "fade" ? (
            <g>
              <path d="M 114 150 C 118 92, 282 92, 286 150 C 272 128, 240 118, 200 118 C 160 118, 128 128, 114 150 Z" fill={HAIR} />
              <Curls seed={41} count={10} cx={200} cy={128} rx={74} ry={36} rMin={22} rMax={32} fill={HAIR} />
              <Curls seed={43} count={6} cx={200} cy={112} rx={44} ry={22} rMin={16} rMax={22} fill={HAIR_SHINE} />
              <path d="M 114 150 C 112 170, 112 190, 116 206 L 124 160 Z" fill={HAIR} opacity={0.6} />
              <path d="M 286 150 C 288 170, 288 190, 284 206 L 276 160 Z" fill={HAIR} opacity={0.6} />
            </g>
          ) : null}
          {!headphonesOnNeck ? (
            <g>
              <rect x={86} y={166} width={28} height={58} rx={12} fill={p.surface} stroke={p.accent} strokeWidth={4} />
              <rect x={286} y={166} width={28} height={58} rx={12} fill={p.surface} stroke={p.accent} strokeWidth={4} />
            </g>
          ) : null}
          {/* eyebrows: thick, slightly angled in (confident) */}
          <g transform={`translate(0 ${-browRaise})`}>
            <path d="M 134 158 Q 160 144 188 152" stroke={HAIR} strokeWidth={10} strokeLinecap="round" fill="none" />
            <path d="M 212 152 Q 240 144 266 158" stroke={HAIR} strokeWidth={10} strokeLinecap="round" fill="none" />
          </g>
          {/* eyes: half-lidded, dark iris, blink by squashing */}
          <g transform={`translate(0 ${176 * blink * 0.9}) scale(1 ${1 - blink * 0.9})`}>
            <ellipse cx={163} cy={176} rx={18} ry={11} fill="#FFFFFF" />
            <ellipse cx={237} cy={176} rx={18} ry={11} fill="#FFFFFF" />
            <circle cx={166} cy={177} r={8} fill="#3B2415" />
            <circle cx={240} cy={177} r={8} fill="#3B2415" />
            <circle cx={166} cy={177} r={4} fill="#120A06" />
            <circle cx={240} cy={177} r={4} fill="#120A06" />
            <circle cx={169} cy={174} r={2.4} fill="#FFFFFF" />
            <circle cx={243} cy={174} r={2.4} fill="#FFFFFF" />
            {/* upper lids: calm, half-closed */}
            <g transform={`translate(0 ${-3 * smile})`}>
              <path d="M 145 176 Q 163 158 181 176 L 181 168 Q 163 160 145 168 Z" fill={SKIN} />
              <path d="M 219 176 Q 237 158 255 176 L 255 168 Q 237 160 219 168 Z" fill={SKIN} />
              <path d="M 146 172 Q 163 164 180 172" stroke={HAIR} strokeWidth={3.5} fill="none" strokeLinecap="round" />
              <path d="M 220 172 Q 237 164 254 172" stroke={HAIR} strokeWidth={3.5} fill="none" strokeLinecap="round" />
            </g>
          </g>
          {glasses === "shades" ? (
            <g>
              <rect x={136} y={160} width={54} height={34} rx={12} fill="#0B0B0F" opacity={0.86} stroke="#2B2B33" strokeWidth={3} />
              <rect x={210} y={160} width={54} height={34} rx={12} fill="#0B0B0F" opacity={0.86} stroke="#2B2B33" strokeWidth={3} />
              <path d="M 190 174 L 210 174" stroke="#2B2B33" strokeWidth={4} />
              <path d="M 142 166 L 160 164" stroke="#FFFFFF" strokeWidth={3} opacity={0.25} strokeLinecap="round" />
              <path d="M 216 166 L 234 164" stroke="#FFFFFF" strokeWidth={3} opacity={0.25} strokeLinecap="round" />
            </g>
          ) : null}
          {/* nose */}
          <path d="M 200 184 L 192 214 C 196 218, 204 218, 208 214" stroke={SKIN_SHADE} strokeWidth={4.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          {/* mouth */}
          <rect x={172} y={240 - mouthH / 2} width={56} height={mouthH} rx={mouthH / 2} fill={MOUTH} />
          {teethH > 0 ? <rect x={177} y={240 - mouthH / 2 + 4} width={46} height={teethH} rx={4} fill="#FFFFFF" opacity={0.92} /> : null}
          <path d={smile ? "M 170 236 Q 200 258 230 236" : "M 172 240 Q 200 252 228 240"} stroke={LIPS} strokeWidth={5} fill="none" strokeLinecap="round" opacity={closed} />
          {smile ? <path d="M 166 232 Q 170 238 174 240 M 234 232 Q 230 238 226 240" stroke={SKIN_SHADE} strokeWidth={3} fill="none" strokeLinecap="round" opacity={closed * 0.7} /> : null}
          {hero ? (
            <>
              <path d="M 270 150 C 282 132, 292 152, 282 162 C 276 168, 266 160, 270 150 Z" fill={p.accent} opacity={dropOp} transform={`translate(0 ${drop * 58})`} />
              <g transform={`translate(352 60) rotate(12) scale(${bang})`} opacity={bang * bangFade}>
                <text x={0} y={0} fontFamily={fonts.display} fontWeight={800} fontSize={74} fill={p.hero}>
                  !!
                </text>
              </g>
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
        {data.look === "vrm" ? (
          <VrmHost modelUrl={data.model ?? "models/host.vrm"} globalFrame={frame} envelope={data.envelope} width={size} height={size} framing="face" mood={data.mood} seed={11} motion={0.7} />
        ) : data.look === "image" && data.rig ? (
          (() => {
            const rig = data.rig as Rig;
            const h = (size * 1.08) / (rig.head[9][1] - rig.cropTop); // head fills the circle
            const w = (HOST_W / HOST_H) * h;
            return (
              <div style={{ position: "absolute", left: size / 2 - rig.faceCenter[0] * w, top: size / 2 - rig.faceCenter[1] * h - size * 0.06 }}>
                <ImageHost rig={rig} globalFrame={frame} envelope={data.envelope} height={h} mood={data.mood} seed={11} motion={0.6} />
              </div>
            );
          })()
        ) : (
          <div style={{ position: "absolute", left: "50%", top: data.look === "curly" ? 30 : 18, translate: "-50% 0" }}>
            <Avatar globalFrame={frame} envelope={data.envelope} styleId={data.styleId} mood={data.mood} look={data.look as Exclude<PresenterLook, "image" | "vrm">} size={size * 1.32} seed={11} />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

/** The big host for the hook scene, in the stage region under the title. */
const HERO_HEADROOM = 120;

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
        top: top - HERO_HEADROOM,
        width: w,
        height: size + HERO_HEADROOM,
        paddingTop: HERO_HEADROOM,
        boxSizing: "border-box",
        scale: `${interpolate(enter, [0, 1], [0.7, 1])}`,
        opacity: enter,
        transformOrigin: "50% 100%",
      }}
    >
      <div style={{ position: "absolute", left: "50%", top: HERO_HEADROOM + size * 0.42, width: size * 0.9, height: size * 0.9, translate: "-50% -50%", borderRadius: "50%", background: `radial-gradient(circle, ${p.glow}, transparent 62%)`, filter: "blur(18px)" }} />
      {data.look === "vrm" ? (
        <div style={{ position: "absolute", left: w / 2 - 360, top: HERO_HEADROOM - 20, width: 720, height: size + 40 }}>
          <VrmHost modelUrl={data.model ?? "models/host.vrm"} globalFrame={frame + sceneStartFrame} envelope={data.envelope} width={720} height={size + 40} framing="bust" mood={data.mood} seed={5} motion={1} />
          <HookExtras sinceAppear={frame} x={720 * 0.6} y={(size + 40) * 0.3} bangX={720 * 0.74} bangY={(size + 40) * 0.12} styleId={data.styleId} scale={size / 760} />
        </div>
      ) : data.look === "image" && data.rig ? (
        (() => {
          const rig = data.rig as Rig;
          // Fill the stage: 6% taller than the box, anchored by the crop top, so the
          // arms end just above the caption band (y 1230) instead of leaving dead space.
          const h = (size * 1.06) / (rig.cropBottom - rig.cropTop);
          const iw = (HOST_W / HOST_H) * h;
          return (
            <div style={{ position: "absolute", left: w / 2 - 0.47 * iw, top: HERO_HEADROOM - rig.cropTop * h }}>
              <ImageHost rig={rig} globalFrame={frame + sceneStartFrame} envelope={data.envelope} height={h} mood={data.mood} seed={5} motion={1} />
              <HookExtras sinceAppear={frame} x={rig.temple[0] * iw} y={rig.temple[1] * h} bangX={0.8 * iw} bangY={0.1 * h} styleId={data.styleId} scale={h / 760} />
            </div>
          );
        })()
      ) : (
        <Avatar globalFrame={frame + sceneStartFrame} envelope={data.envelope} styleId={data.styleId} mood={data.mood} look={data.look as Exclude<PresenterLook, "image" | "vrm">} size={size} sinceAppear={frame} hero seed={5} />
      )}
    </div>
  );
};

/** Sweat drop sliding down the temple and a "!!" pop for the hook, over any host. */
const HookExtras: React.FC<{ sinceAppear: number; x: number; y: number; bangX: number; bangY: number; styleId: StyleId; scale: number }> = ({ sinceAppear, x, y, bangX, bangY, styleId, scale }) => {
  const { fps } = useVideoConfig();
  const p = palettes[styleId];
  const bang = spring({ frame: sinceAppear - 8, fps, config: springs.bouncy });
  const bangFade = 1 - interpolate(sinceAppear, [70, 90], [0, 1], clamp);
  const drop = interpolate(sinceAppear, [14, 70], [0, 1], clamp);
  const dropOp = interpolate(sinceAppear, [14, 20, 62, 72], [0, 1, 1, 0], clamp);
  return (
    <svg style={{ position: "absolute", left: 0, top: 0, overflow: "visible", pointerEvents: "none" }} width={1} height={1}>
      <g transform={`translate(${x} ${y + drop * 70 * scale}) scale(${scale})`} opacity={dropOp}>
        <path d="M 0 0 C 12 -18, 22 2, 12 12 C 6 18, -4 10, 0 0 Z" fill={p.accent} />
      </g>
      <text x={bangX} y={bangY} fontFamily={fonts.display} fontWeight={800} fontSize={74 * scale} fill={p.hero} opacity={bang * bangFade} transform={`rotate(12 ${bangX} ${bangY}) scale(${bang})`} style={{ transformOrigin: `${bangX}px ${bangY}px` }}>
        !!
      </text>
    </svg>
  );
};

/** Still: the four looks side by side for choosing one. */
export const AvatarSheet: React.FC<{ styleId: StyleId }> = ({ styleId }) => {
  const p = palettes[styleId];
  const env = [0.0, 0.3, 0.7, 0.2];
  return (
    <AbsoluteFill style={{ background: p.bg, fontFamily: fonts.display }}>
      {LOOKS.map((look, i) => (
        <div key={look} style={{ position: "absolute", left: 40 + i * 500, top: 120, width: 460, height: 760, display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
          <Avatar globalFrame={0} envelope={[env[i]]} styleId={styleId} mood="calm" look={look} size={560} seed={99} />
          <div style={{ color: p.text, fontSize: 44, fontWeight: 700 }}>{i + 1}. {look}</div>
        </div>
      ))}
      <div style={{ position: "absolute", left: 40, top: 40, color: p.textMuted, fontSize: 30, fontFamily: fonts.mono, letterSpacing: "0.1em" }}>REELFORGE HOST LOOKS</div>
    </AbsoluteFill>
  );
};
