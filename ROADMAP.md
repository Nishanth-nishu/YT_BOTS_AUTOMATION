# REELFORGE Roadmap

Status key: done, in progress, planned.

| Phase | Scope | Acceptance | Status |
|---|---|---|---|
| 1. Environment and skills | Hardware and software inspection, skill discovery and audit, Remotion install, project skeleton, docs | A basic local Remotion video renders and its frames are inspected | done (2026-11-05) |
| 2. Benchmark video | "How AI Agents Actually Work": hook, cinematic scene, reasoning, tool calling, memory, workflow diagram, typography, sound, voiceover, captions. Draft and final renders, benchmark report | Five or more distinct scenes, voiceover and captions present, QA probe passes, benchmark report written | in progress |
| 3. Motion graphics library | Typography, particles, transitions, cinematic backgrounds, 3D scenes, neural network diagrams, charts, code animation. Cinematic and explainer templates | Each component has a Studio composition and a rendered still | planned |
| 4. Audio and captions | Kokoro install (CPU local, CUDA on Ada), Piper evaluation, caption timing from TTS timestamps, pronunciation controls, caching | Word-level captions synchronised within 80 ms on a test reel | planned |
| 5. Research and scripting | Topic discovery from arXiv, Hugging Face, GitHub trending, official blogs. Scoring, dedupe, hook generation, storyboard generation | A topic to storyboard run with no manual edits | planned |
| 6. End-to-end pipeline | Research -> Script -> Storyboard -> Visuals -> VO -> Captions -> Render -> QA -> Export | One reel generated end-to-end without code changes | planned |
| 7. Dashboard | Overview, research, script editor, storyboard editor, preview, production, QA, publishing, analytics | Local dashboard manages a full production run | planned |
| 8. Daily automation | Three-topic selection, scheduling, duplicate detection, retries, reporting, manual approval | Three reels in one batch within hardware limits | planned |
| 9. Optimisation | Visual quality, render speed, audio quality, variety, accuracy, memory | Benchmarks improve against Phase 2 baseline | planned |

## Phase 1 record

Implemented:
- Environment inspection (docs/ENVIRONMENT_REPORT.md). Found no local NVIDIA GPU; RTX 3090s are on Ada plafnet2.
- FFmpeg 9.0.2 installed locally with winget (free).
- Skill audit of 7 repositories, 18 skills installed project-locally (SKILLS_REGISTRY.md).
- Remotion 4.0.540 project in video-engine with transitions, media, shapes, three, captions, effects, motion-blur, fonts, paths, noise, zod, three, react-three-fiber.
- Design system: tokens, motion presets, local OFL fonts, five-layer stack, entrance/stagger/exit primitives, kinetic typography, counter.
- CC0 SFX kit (22 files) with credits.
- SmokeTest composition rendered at 1080x1920, 30 fps, 6 s in 32 s on the local CPU; ffprobe and frame inspection passed.

Outstanding from Phase 1:
- `claude plugin install remotion@remotion` not run (CLI not on PATH in this shell; identical content installed as skills).
- Local renders output `yuvj420p` by default; the production encoder re-wraps to `yuv420p` limited range.

## Hardware-driven decisions

- Local machine renders drafts only when RAM allows; the scheduler checks free RAM before launching Chrome.
- Final renders and TTS prefer Ada. gnode118 is excluded from every job.
- No Ollama or local LLM; Claude Code is the intelligence layer.
