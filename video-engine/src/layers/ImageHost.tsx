/**
 * ImageHost: the host as an illustration animated in layers. The pixels of
 * the face and outfit are never redrawn; motion comes from clipped copies of
 * the same image:
 *   body      breathing (slow vertical scale from the bottom)
 *   head      gentle sway: rotation about the neck plus a few px of drift
 *   hair      the outer hair follows the head with a small lag
 *   brows     the brow band lifts on loud syllables
 *   eyelids   the skin above each eye slides down over it (blink)
 *   jaw       lower lip and chin drop with the voice; the gap shows a dark
 *             mouth interior with a hint of teeth (lip-sync)
 * The rig (fractions of the image size) comes from spec.presenter.rig, mapped
 * once from assets/images/host.json. Every motion is a pure function of the
 * frame, so renders are identical.
 */
import React from "react";
import { Img, staticFile, useVideoConfig } from "remotion";
import { blinkAt, mouthAt } from "./Presenter";

export type Rig = {
  image: string;
  cropTop: number;
  cropBottom: number;
  neck: [number, number];
  faceCenter: [number, number];
  temple: [number, number];
  head: [number, number][];
  hair: [number, number][];
  eyes: { x: number; y: number; w: number; h: number }[];
  brows: { x: number; y: number; w: number; h: number };
  mouth: { x: number; y: number; w: number };
  jaw: [number, number][];
  jawDropMax: number;
  mouthInterior: string;
  teeth: string;
};

/** Natural size of the host image; the rig is resolution independent. */
export const HOST_W = 1500;
export const HOST_H = 2000;

const poly = (pts: [number, number][]) => `polygon(${pts.map(([x, y]) => `${(x * 100).toFixed(2)}% ${(y * 100).toFixed(2)}%`).join(", ")})`;
const box = (b: { x: number; y: number; w: number; h: number }) => `polygon(${(b.x * 100).toFixed(2)}% ${(b.y * 100).toFixed(2)}%, ${((b.x + b.w) * 100).toFixed(2)}% ${(b.y * 100).toFixed(2)}%, ${((b.x + b.w) * 100).toFixed(2)}% ${((b.y + b.h) * 100).toFixed(2)}%, ${(b.x * 100).toFixed(2)}% ${((b.y + b.h) * 100).toFixed(2)}%)`;

type Props = {
  rig: Rig;
  globalFrame: number;
  envelope: number[];
  /** Height in px of the full image box; the component scales the 1500x2000 image to it. */
  height: number;
  mood?: "hype" | "calm";
  seed?: number;
  /** Extra sway for the hero (1) versus the badge (0.6). */
  motion?: number;
};

export const ImageHost: React.FC<Props> = ({ rig, globalFrame, envelope, height, mood = "hype", seed = 7, motion = 1 }) => {
  const { fps } = useVideoConfig();
  const s = height / HOST_H;
  const W = HOST_W * s;
  const H = height;
  const open = mouthAt(envelope, globalFrame);
  const blink = blinkAt(globalFrame, seed);
  const t = globalFrame / fps;
  const breathe = 1 + 0.012 * Math.sin((t / 4.2) * Math.PI * 2);
  const sway = (Math.sin(t / 3.1) * 1.2 + Math.sin(t / 7.3) * 0.6) * motion + (open > 0.1 ? Math.sin(globalFrame / 4) * open * 0.6 : 0);
  const driftX = Math.sin(t / 5.7) * 3 * motion;
  const driftY = (Math.sin(t / 3.9) * 2 + open * 3) * motion;
  const hairLag = Math.sin(t / 3.1 - 0.5) * 0.35 * motion;
  const browRaise = ((mood === "hype" ? 2 : 0) + open * 6) * s;
  const jawDrop = open * rig.jawDropMax * H;
  const neckX = rig.neck[0] * W;
  const neckY = rig.neck[1] * H;
  const src = staticFile(rig.image);
  const imgStyle: React.CSSProperties = { position: "absolute", left: 0, top: 0, width: W, height: H, display: "block" };
  const cropClip = `polygon(0% ${rig.cropTop * 100}%, 100% ${rig.cropTop * 100}%, 100% ${rig.cropBottom * 100}%, 0% ${rig.cropBottom * 100}%)`;
  const mouthX = rig.mouth.x * W;
  const mouthY = rig.mouth.y * H;
  const mouthW = rig.mouth.w * W;

  return (
    <div style={{ position: "relative", width: W, height: H, overflow: "visible" }}>
      {/* body: breathing */}
      <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transformOrigin: `50% ${rig.cropBottom * 100}%`, transform: `scaleY(${breathe})` }}>
        <Img src={src} style={{ ...imgStyle, clipPath: cropClip }} />
      </div>
      {/* head group: sway about the neck */}
      <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transformOrigin: `${neckX}px ${neckY}px`, transform: `translate(${driftX}px, ${driftY}px) rotate(${sway}deg)` }}>
        <Img src={src} style={{ ...imgStyle, clipPath: poly(rig.head) }} />
        {/* hair with a small lag */}
        <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transformOrigin: `${neckX}px ${neckY}px`, transform: `rotate(${hairLag}deg)` }}>
          <Img src={src} style={{ ...imgStyle, clipPath: poly(rig.hair) }} />
        </div>
        {/* mouth interior, revealed as the jaw drops */}
        {jawDrop > 0.4 ? (
          <div
            style={{
              position: "absolute",
              left: mouthX,
              top: mouthY - 2,
              width: mouthW,
              height: jawDrop + 6,
              borderRadius: `0 0 ${mouthW / 2}px ${mouthW / 2}px / 0 0 ${jawDrop + 6}px ${jawDrop + 6}px`,
              background: rig.mouthInterior,
            }}
          >
            {jawDrop > 6 * s ? <div style={{ position: "absolute", left: "10%", top: 1, width: "80%", height: Math.min(7 * s, jawDrop * 0.3), background: rig.teeth, opacity: 0.85, borderRadius: 3 }} /> : null}
          </div>
        ) : null}
        {/* jaw: lower lip and chin drop */}
        <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `translateY(${jawDrop}px)` }}>
          <Img src={src} style={{ ...imgStyle, clipPath: poly(rig.jaw) }} />
        </div>
        {/* brow band lift */}
        <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `translateY(${-browRaise}px)` }}>
          <Img src={src} style={{ ...imgStyle, clipPath: box(rig.brows) }} />
        </div>
        {/* eyelids: the skin above each eye slides down over it */}
        {blink > 0.02
          ? rig.eyes.map((e, i) => (
              <div key={i} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, clipPath: box(e) }}>
                <Img src={src} style={{ ...imgStyle, transform: `translateY(${blink * e.h * H * 1.15}px)` }} />
              </div>
            ))
          : null}
      </div>
    </div>
  );
};
