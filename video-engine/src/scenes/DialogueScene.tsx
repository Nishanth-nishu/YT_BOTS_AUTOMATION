/**
 * DialogueScene: two characters on stage, turned towards each other. Each
 * scene has one speaker (`data.speaker`); that character lip-syncs to the
 * voice track, leans in and lights up, while the other listens with the mouth
 * shut. The cast comes from `data.cast` (left character first):
 *   [{ name: "host", label: "Nish", model: "models/host.vrm" },
 *    { name: "guest", label: "Sam", model: "models/guest.vrm" }]
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import { springs } from "../design/motion";
import { fonts, palettes, type StyleId } from "../design/tokens";
import { usePresenter } from "../layers/Presenter";
import { VrmHost } from "../layers/VrmHost";
import { msToFrames, type TimedScene } from "../schema/reelSpec";
import { SceneTitle, Stage } from "./SceneShell";

type CastMember = { name: string; label?: string; model: string };

const DEFAULT_CAST: CastMember[] = [
  { name: "host", label: "Host", model: "models/host.vrm" },
  { name: "guest", label: "Guest", model: "models/guest.vrm" },
];

const W = 600;
const H = 560;

export const DialogueScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const presenter = usePresenter();
  const p = palettes[styleId];
  const cast: CastMember[] = (Array.isArray(scene.data.cast) && scene.data.cast.length >= 2 ? scene.data.cast : DEFAULT_CAST).slice(0, 2);
  const speaker: string = scene.data.speaker ?? cast[0].name;
  const start = msToFrames(scene.startMs, fps);
  const enter = spring({ frame: frame - 2, fps, config: springs.smooth });

  return (
    <AbsoluteFill>
      <ParticleField count={26} scale={particleScale} styleId={styleId} seed={73} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "MEANWHILE"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        {cast.map((member, i) => {
          const left = i === 0;
          const talking = member.name === speaker;
          const x = left ? -20 : 1080 - W + 20;
          return (
            <div
              key={member.name}
              style={{
                position: "absolute",
                left: x,
                top: 30,
                width: W,
                height: H,
                opacity: enter,
                translate: `${interpolate(enter, [0, 1], [left ? -80 : 80, 0])}px 0px`,
                scale: `${talking ? 1.04 : 0.9}`,
                transformOrigin: left ? "30% 100%" : "70% 100%",
                filter: talking ? "none" : "brightness(0.55) saturate(0.7)",
                zIndex: talking ? 2 : 1,
              }}
            >
              <div style={{ position: "absolute", left: "50%", top: "44%", width: W * 0.8, height: W * 0.8, translate: "-50% -50%", borderRadius: "50%", background: `radial-gradient(circle, ${talking ? p.glow : "rgba(120,130,170,0.16)"}, transparent 62%)`, filter: "blur(20px)" }} />
              {presenter ? (
                <VrmHost
                  modelUrl={member.model}
                  globalFrame={frame + start}
                  envelope={presenter.envelope}
                  expressions={talking ? presenter.expressions : []}
                  width={W}
                  height={H}
                  framing="bust"
                  mood={talking ? presenter.mood : "calm"}
                  seed={left ? 5 : 23}
                  motion={talking ? 1.3 : 0.5}
                  yaw={left ? 0.42 : -0.42}
                  speaking={talking}
                />
              ) : null}
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  bottom: 6,
                  translate: "-50% 0",
                  padding: "8px 22px",
                  borderRadius: 999,
                  background: talking ? p.hero : `${p.surface}E6`,
                  border: `2px solid ${talking ? p.hero : p.line}`,
                  color: talking ? p.bg : p.textDim,
                  fontFamily: fonts.mono,
                  fontWeight: 600,
                  fontSize: 26,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {member.label ?? member.name}
              </div>
            </div>
          );
        })}
      </Stage>
    </AbsoluteFill>
  );
};
