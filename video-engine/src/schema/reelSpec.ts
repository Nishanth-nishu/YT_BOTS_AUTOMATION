/**
 * ReelSpec: the single JSON document that drives a Reel render.
 * Produced by services/tts/synthesize.py (mirrors services/common/schema.py).
 */
import { z } from "zod";

export const captionSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  timestampMs: z.number().nullable().optional(),
  confidence: z.number().nullable().optional(),
});

export const sceneKindSchema = z.enum([
  "hook",
  "loop",
  "reasoning",
  "toolCall",
  "memory",
  "workflow",
  "payoff",
  "concept",
  "code",
  "terminal",
  "chart",
  "neuralNet",
  "rag",
]);

export const seamSchema = z.enum(["current", "up", "zoomIn", "zoomOut", "burst"]);

export const timedSceneSchema = z.object({
  id: z.string(),
  kind: sceneKindSchema,
  narration: z.string(),
  /** Romanised Hinglish for captions when narration carries Devanagari. */
  captionText: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  lines: z.array(z.string()).default([]),
  highlight: z.array(z.string()).default([]),
  data: z.record(z.string(), z.any()).default({}),
  transition: seamSchema.default("current"),
  cta: z.string().nullable().optional(),
  leadInMs: z.number().default(150),
  padAfterMs: z.number().default(350),
  minDurationMs: z.number().default(2500),
  startMs: z.number(),
  endMs: z.number(),
  audioStartMs: z.number(),
  audioEndMs: z.number(),
});

/** The animated host. `envelope` is mouth openness 0..1 per video frame. */
export const presenterSchema = z.object({
  enabled: z.boolean().default(true),
  name: z.string().default("host"),
  mood: z.enum(["hype", "calm"]).default("hype"),
  look: z.enum(["curly", "waves", "fade", "shades", "image", "vrm"]).default("vrm"),
  /** For look "vrm": the avatar file under public/ (default models/host.vrm). */
  model: z.string().nullable().optional(),
  /** For look "image": path under public/ and the rig (fractions of the image size). */
  image: z.string().nullable().optional(),
  rig: z.record(z.string(), z.any()).nullable().optional(),
  fps: z.number().default(30),
  envelope: z.array(z.number()).default([]),
  /** Per-frame [happy, angry, sad, relaxed, surprised] weights from the tone of the words. */
  expressions: z.array(z.array(z.number())).default([]),
});

export const reelSpecSchema = z.object({
  id: z.string(),
  title: z.string(),
  style: z.enum(["cinematic", "explainer", "experimental"]),
  fps: z.number().default(30),
  width: z.number().default(1080),
  height: z.number().default(1920),
  durationMs: z.number(),
  voice: z.object({ file: z.string() }).passthrough(),
  presenter: presenterSchema.nullable().optional(),
  music: z
    .object({ file: z.string(), volume: z.number().default(0.2), bpm: z.number().nullable().optional() })
    .nullable()
    .optional(),
  captions: z.array(captionSchema),
  captionMode: z.enum(["word", "sentence"]).default("word"),
  scenes: z.array(timedSceneSchema),
  caption: z.string().default(""),
  hashtags: z.array(z.string()).default([]),
  sources: z.array(z.string()).default([]),
  dmKeyword: z.string().default("LETS GO"),
  dmLink: z.string().nullable().optional(),
});

export type ReelSpec = z.infer<typeof reelSpecSchema>;
export type TimedScene = z.infer<typeof timedSceneSchema>;
export type CaptionItem = z.infer<typeof captionSchema>;
export type SceneKind = z.infer<typeof sceneKindSchema>;
export type PresenterSpec = z.infer<typeof presenterSchema>;

export const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);
