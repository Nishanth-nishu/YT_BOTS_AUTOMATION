/**
 * DialogueScene: two characters on stage, turned towards each other.
 *
 * `data.cast` lists them, left first:
 *   [{ name: "drona", label: "Guru Drona", model: "models/drona.vrm" },
 *    { name: "arjuna", label: "Arjun", model: "models/arjuna.vrm" }]
 * `data.speaker` is who talks. A cast member lip-syncs, steps forward and
 * lights up while the other listens. Any other speaker ("narrator") means the
 * scene is being told, not spoken: both characters stand lit and silent while
 * the narrator's badge does the talking.
 *
 * Acting, all optional and per character name:
 *   data.emotes    { arjuna: "focus", drona: "stern" }   named faces (design/epicCast.ts)
 *   data.gestures  { drona: "point" }                    arm / body poses
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ParticleField } from "../animations/Particles";
import type { Gesture } from "../design/epicCast";
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

const W = 620;
const H = 600;

export const DialogueScene: React.FC<{ scene: TimedScene; styleId: StyleId; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const presenter = usePresenter();
  const p = palettes[styleId];
  const cast: CastMember[] = (Array.isArray(scene.data.cast) && scene.data.cast.length >= 2 ? scene.data.cast : DEFAULT_CAST).slice(0, 2);
  const speaker: string = scene.data.speaker ?? cast[0].name;
  const told = !cast.some((m) => m.name === speaker); // narrated: nobody on stage is talking
  const emotes: Record<string, string> = scene.data.emotes ?? {};
  const gestures: Record<string, Gesture> = scene.data.gestures ?? {};
  const epic = styleId === "epic";
  const start = msToFrames(scene.startMs, fps);
  const enter = spring({ frame: frame - 2, fps, config: springs.smooth });
  // faces and poses ease in just after the scene lands, so the change reads as a reaction
  const act = spring({ frame: frame - 6, fps, config: springs.smooth });

  return (
    <AbsoluteFill>
      <ParticleField count={26} scale={particleScale} styleId={styleId} seed={73} speed={0.4} />
      <SceneTitle kicker={scene.data.kicker ?? "MEANWHILE"} title={scene.title ?? ""} highlight={scene.highlight} styleId={styleId} />
      <Stage>
        {cast.map((member, i) => {
          const left = i === 0;
          const talking = member.name === speaker;
          const lit = talking || told;
          const x = left ? -30 : 1080 - W + 30;
          return (
            <div
              key={member.name}
              style={{
                position: "absolute",
                left: x,
                top: 0,
                width: W,
                height: H,
                opacity: enter,
                translate: `${interpolate(enter, [0, 1], [left ? -80 : 80, 0])}px 0px`,
                scale: `${talking ? 1.05 : told ? 0.97 : 0.9}`,
                transformOrigin: left ? "30% 100%" : "70% 100%",
                filter: lit ? "none" : "brightness(0.55) saturate(0.7)",
                zIndex: talking ? 2 : 1,
              }}
            >
              <div style={{ position: "absolute", left: "50%", top: "46%", width: W * 0.8, height: W * 0.8, translate: "-50% -50%", borderRadius: "50%", background: `radial-gradient(circle, ${talking ? p.glow : "rgba(120,130,170,0.16)"}, transparent 62%)`, filter: "blur(20px)" }} />
              {presenter ? (
                <VrmHost
                  modelUrl={member.model}
                  globalFrame={frame + start}
                  envelope={presenter.envelope}
                  expressions={talking ? presenter.expressions : []}
                  width={W}
                  height={H}
                  framing={epic ? "stage" : "bust"}
                  mood={talking ? presenter.mood : "calm"}
                  seed={left ? 5 : 23}
                  motion={talking ? 1.3 : 0.6}
                  yaw={left ? 0.42 : -0.42}
                  speaking={talking}
                  emote={emotes[member.name]}
                  emoteWeight={act}
                  gesture={gestures[member.name] ?? "idle"}
                  gestureWeight={act}
                  expressiveness={epic ? 1.8 : 1}
                />
              ) : null}
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  bottom: told ? 70 : 6, // clear of the narrator's badge
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
