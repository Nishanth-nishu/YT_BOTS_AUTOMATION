/**
 * Reel: the storyboard-driven composition. Input props are a ReelSpec plus a
 * quality profile. Scenes are placed with absolute frame ranges from the TTS
 * timing, wrapped in SceneShell seams, with voice, music, SFX cues and
 * captions layered on top.
 */
import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, type CalculateMetadataFunction } from "remotion";
import "../design/fonts";
import { ReelFrame } from "../layers/Stack";
import { PresenterContext, PresenterPip } from "../layers/Presenter";
import { Captions } from "../captions/Captions";
import { quality, type QualityProfile } from "../design/tokens";
import { clamp } from "../design/motion";
import { msToFrames, reelSpecSchema, type ReelSpec, type TimedScene } from "../schema/reelSpec";
import { SceneShell } from "../scenes/SceneShell";
import { HookScene } from "../scenes/HookScene";
import { LoopScene } from "../scenes/LoopScene";
import { ReasoningScene } from "../scenes/ReasoningScene";
import { ToolCallScene } from "../scenes/ToolCallScene";
import { MemoryScene } from "../scenes/MemoryScene";
import { WorkflowScene } from "../scenes/WorkflowScene";
import { PayoffScene } from "../scenes/PayoffScene";
import { ConceptScene } from "../scenes/ConceptScene";
import { DialogueScene } from "../scenes/DialogueScene";
import { TerminalScene } from "../scenes/TerminalScene";
import { ChartScene } from "../scenes/ChartScene";
import { NeuralNetScene } from "../scenes/NeuralNetScene";
import { RagScene } from "../scenes/RagScene";

export type ReelProps = {
  /** Path under public/ to a ReelSpec JSON, used when `spec` is null (Studio). */
  specFile: string | null;
  spec: ReelSpec | null;
  quality: QualityProfile;
};

export const calculateReelMetadata: CalculateMetadataFunction<ReelProps> = async ({ props, abortSignal }) => {
  let raw: unknown = props.spec;
  if (!raw && props.specFile) {
    const res = await fetch(staticFile(props.specFile), { signal: abortSignal });
    raw = await res.json();
  }
  const spec = reelSpecSchema.parse(raw);
  const fps = spec.fps;
  const q = quality[props.quality] ?? quality.standard;
  return {
    durationInFrames: Math.ceil((spec.durationMs / 1000) * fps),
    fps,
    width: q.width,
    height: q.height,
    props: { ...props, spec },
    defaultOutName: `${spec.id}.${props.quality}`,
  };
};

const SceneByKind: React.FC<{ scene: TimedScene; styleId: ReelSpec["style"]; particleScale: number }> = ({ scene, styleId, particleScale }) => {
  switch (scene.kind) {
    case "hook":
      return <HookScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "loop":
      return <LoopScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "reasoning":
      return <ReasoningScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "toolCall":
      return <ToolCallScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "memory":
      return <MemoryScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "workflow":
      return <WorkflowScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "payoff":
      return <PayoffScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "concept":
      return <ConceptScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "code":
    case "terminal":
      return <TerminalScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "chart":
      return <ChartScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "neuralNet":
      return <NeuralNetScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "rag":
      return <RagScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    case "dialogue":
      return <DialogueScene scene={scene} styleId={styleId} particleScale={particleScale} />;
    default:
      return <HookScene scene={scene} styleId={styleId} particleScale={particleScale} />;
  }
};

/** SFX cue list derived from the scene structure: a whoosh into every seam,
 *  a riser into the payoff and an impact when it lands. SFX start 3 frames
 *  before the visual they accent. */
const SfxCues: React.FC<{ spec: ReelSpec }> = ({ spec }) => {
  const { fps } = useVideoConfig();
  const cues: { at: number; file: string; volume: number }[] = [];
  spec.scenes.forEach((s, i) => {
    if (i === 0) {
      return;
    }
    const start = msToFrames(s.startMs, fps);
    if (s.kind === "payoff") {
      cues.push({ at: Math.max(0, start - 2 * fps), file: "sfx/riser.ogg", volume: 0.55 });
      cues.push({ at: Math.max(0, start - 2), file: "sfx/impact.ogg", volume: 0.8 });
    } else {
      cues.push({ at: Math.max(0, start - 3), file: i % 2 === 0 ? "sfx/whoosh.ogg" : "sfx/whoosh2.ogg", volume: 0.5 });
    }
  });
  return (
    <>
      {cues.map((c, i) => (
        <Sequence key={i} from={c.at} layout="none">
          <Audio src={staticFile(c.file)} volume={c.volume} />
        </Sequence>
      ))}
    </>
  );
};

const MusicBed: React.FC<{ spec: ReelSpec }> = ({ spec }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  if (!spec.music) {
    return null;
  }
  const base = spec.music.volume;
  const vol = interpolate(frame, [0, fps, durationInFrames - 2 * fps, durationInFrames - 1], [0, base, base, 0], clamp);
  return <Audio src={staticFile(spec.music.file)} volume={vol} loop />;
};

/** True while a dialogue scene is on screen: both characters are already big
 *  on stage, so the small host badge hides and captions go back to full width. */
const useInDialogue = (spec: ReelSpec): boolean => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spec.scenes.some((s) => s.kind === "dialogue" && frame >= msToFrames(s.startMs, fps) && frame < msToFrames(s.endMs, fps));
};

const Pip: React.FC<{ spec: ReelSpec; hookEnd: number }> = ({ spec, hookEnd }) => (useInDialogue(spec) ? null : <PresenterPip hiddenUntilFrame={hookEnd} />);

/** Captions sit full width during the hook (the host is big there) and move
 *  right of the presenter badge once it appears. */
const CaptionBand: React.FC<{ spec: ReelSpec; narrowFromFrame: number | null }> = ({ spec, narrowFromFrame }) => {
  const frame = useCurrentFrame();
  const inDialogue = useInDialogue(spec);
  const narrow = narrowFromFrame !== null && frame >= narrowFromFrame - 2 && !inDialogue;
  return <Captions captions={spec.captions} scenes={spec.scenes} mode={spec.captionMode} styleId={spec.style} left={narrow ? 304 : undefined} fontSize={narrow ? 56 : 60} />;
};

export const Reel: React.FC<ReelProps> = ({ spec, quality: profile }) => {
  const { fps, width } = useVideoConfig();
  const q = quality[profile] ?? quality.standard;
  if (!spec) {
    return null;
  }
  // Scenes are authored at 1080x1920; the canvas may be smaller (draft).
  const layoutScale = width / 1080;
  const presenter = spec.presenter && spec.presenter.enabled ? { ...spec.presenter, styleId: spec.style } : null;
  // The badge stays hidden while the hook shows the big host, then pops in.
  const hookEnd = spec.scenes.length && spec.scenes[0].kind === "hook" ? msToFrames(spec.scenes[0].endMs, fps) : 0;
  return (
    <PresenterContext.Provider value={presenter}>
    <AbsoluteFill style={{ width: 1080, height: 1920, scale: `${layoutScale}`, transformOrigin: "0 0" }}>
    <ReelFrame style={spec.style} grid={spec.style === "explainer"}>
      <Audio src={staticFile(spec.voice.file)} volume={1} />
      <MusicBed spec={spec} />
      <SfxCues spec={spec} />
      <AbsoluteFill>
        {spec.scenes.map((scene, i) => {
          const from = msToFrames(scene.startMs, fps);
          const to = msToFrames(scene.endMs, fps);
          const prev = i > 0 ? spec.scenes[i - 1].transition : null;
          const next = i < spec.scenes.length - 1 ? scene.transition : null;
          return (
            <Sequence key={scene.id} name={scene.id} from={from} durationInFrames={Math.max(1, to - from)}>
              <SceneShell enterFrom={prev} exitWith={next}>
                <SceneByKind scene={scene} styleId={spec.style} particleScale={q.particleScale} />
              </SceneShell>
            </Sequence>
          );
        })}
      </AbsoluteFill>
      {presenter ? <Pip spec={spec} hookEnd={hookEnd} /> : null}
      <CaptionBand spec={spec} narrowFromFrame={presenter ? hookEnd : null} />
    </ReelFrame>
    </AbsoluteFill>
    </PresenterContext.Provider>
  );
};
