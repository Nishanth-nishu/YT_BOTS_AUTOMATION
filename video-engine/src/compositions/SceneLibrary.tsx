/**
 * SceneLibrary: renders any scene kind in isolation with sample data so each
 * component has a Studio composition and a rendered still for review.
 */
import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import "../design/fonts";
import { ReelFrame } from "../layers/Stack";
import { Captions } from "../captions/Captions";
import type { StyleId } from "../design/tokens";
import type { SceneKind, TimedScene } from "../schema/reelSpec";
import { HookScene } from "../scenes/HookScene";
import { LoopScene } from "../scenes/LoopScene";
import { ReasoningScene } from "../scenes/ReasoningScene";
import { ToolCallScene } from "../scenes/ToolCallScene";
import { MemoryScene } from "../scenes/MemoryScene";
import { WorkflowScene } from "../scenes/WorkflowScene";
import { PayoffScene } from "../scenes/PayoffScene";
import { ConceptScene } from "../scenes/ConceptScene";
import { TerminalScene } from "../scenes/TerminalScene";
import { ChartScene } from "../scenes/ChartScene";
import { NeuralNetScene } from "../scenes/NeuralNetScene";
import { RagScene } from "../scenes/RagScene";

export type SceneLibraryProps = {
  kind: SceneKind;
  styleId: StyleId;
  title: string;
  highlight: string[];
  lines: string[];
  data: Record<string, unknown>;
  cta: string | null;
  durationSeconds: number;
};

export const SAMPLES: Record<string, Partial<SceneLibraryProps>> = {
  concept: { kind: "concept", title: "Three things every model needs", highlight: ["three"], lines: ["Data it has actually seen", "A loss it can lower", "Compute to run the loop"], data: { kicker: "CONCEPT" } },
  terminal: { kind: "terminal", title: "Install it in one line", highlight: ["one"], data: { command: "pip install reelforge", lines: [{ text: "Collecting reelforge", kind: "dim" }, { text: "Downloading reelforge-0.3.0.whl (1.2 MB)", kind: "dim" }, { text: "Successfully installed reelforge-0.3.0", kind: "ok" }, { text: "$ reelforge render agents.json", kind: "out" }, { text: "rendered 1708 frames in 80 s", kind: "ok" }], windowTitle: "bash" } },
  chart: { kind: "chart", title: "Smaller models, same score", highlight: ["same"], data: { type: "bar", series: [{ label: "7B", value: 61.2 }, { label: "13B", value: 66.4 }, { label: "70B", value: 72.9 }, { label: "ours 8B", value: 72.1, hero: true }], unit: "%", decimals: 1, note: "Illustrative data" } },
  chartLine: { kind: "chart", title: "Cost per million tokens", highlight: ["cost"], data: { type: "line", series: [{ label: "2023", value: 30 }, { label: "2024", value: 10 }, { label: "2025", value: 2.5 }, { label: "2026", value: 0.6 }], unit: "$", decimals: 1, note: "Illustrative data" } },
  neuralNet: { kind: "neuralNet", title: "Signals flow forward", highlight: ["forward"], data: { layers: [4, 7, 7, 3], labels: ["input", "hidden", "hidden", "output"] } },
  rag: { kind: "rag", title: "How RAG answers", highlight: ["RAG"], data: { stages: ["Query", "Embed", "Vector DB", "Top-k docs", "LLM", "Answer"] } },
};

const Pick: React.FC<{ scene: TimedScene; styleId: StyleId }> = ({ scene, styleId }) => {
  const props = { scene, styleId, particleScale: 1 };
  switch (scene.kind) {
    case "hook":
      return <HookScene {...props} />;
    case "loop":
      return <LoopScene {...props} />;
    case "reasoning":
      return <ReasoningScene {...props} />;
    case "toolCall":
      return <ToolCallScene {...props} />;
    case "memory":
      return <MemoryScene {...props} />;
    case "workflow":
      return <WorkflowScene {...props} />;
    case "payoff":
      return <PayoffScene {...props} />;
    case "concept":
      return <ConceptScene {...props} />;
    case "code":
    case "terminal":
      return <TerminalScene {...props} />;
    case "chart":
      return <ChartScene {...props} />;
    case "neuralNet":
      return <NeuralNetScene {...props} />;
    case "rag":
      return <RagScene {...props} />;
    default:
      return null;
  }
};

export const SceneLibrary: React.FC<SceneLibraryProps> = ({ kind, styleId, title, highlight, lines, data, cta, durationSeconds }) => {
  const { width } = useVideoConfig();
  const ms = durationSeconds * 1000;
  const scene: TimedScene = {
    id: "sample",
    kind,
    narration: title,
    title,
    lines,
    highlight,
    data,
    transition: "current",
    cta,
    leadInMs: 150,
    padAfterMs: 350,
    minDurationMs: 2500,
    startMs: 0,
    endMs: ms,
    audioStartMs: 150,
    audioEndMs: ms - 350,
  };
  const captions = [{ text: "sample", startMs: 400, endMs: 900 }, { text: " caption", startMs: 900, endMs: 1500 }, { text: " here.", startMs: 1500, endMs: ms - 400 }];
  return (
    <AbsoluteFill style={{ width: 1080, height: 1920, scale: `${width / 1080}`, transformOrigin: "0 0" }}>
      <ReelFrame style={styleId} grid={styleId === "explainer"}>
        <Pick scene={scene} styleId={styleId} />
        <Captions captions={captions} scenes={[scene]} mode="word" styleId={styleId} />
      </ReelFrame>
    </AbsoluteFill>
  );
};
