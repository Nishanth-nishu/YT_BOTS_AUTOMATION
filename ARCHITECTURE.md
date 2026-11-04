# REELFORGE Architecture

Local-first, modular monolith. One repository, one SQLite database, one Remotion project, Python services glued by a job scheduler. GPU-heavy stages can run on the Ada cluster's RTX 3090 nodes (gnode113 to gnode116, never gnode118); everything else runs on the Windows machine.

## 1. System overview

```
+-----------------------------------------------------------------------------------+
|  LOCAL WINDOWS 11 (i5-13500, 16 GB RAM, Intel UHD 770)                             |
|                                                                                    |
|  Claude Code (this session, project skills)                                        |
|      |                                                                             |
|      v                                                                             |
|  services/   research -> scripts -> storyboard -> tts -> captions -> rendering ->  |
|              quality -> publishing            (Python 3.11, pydantic, SQLite)      |
|      |                                                                             |
|      +-- video-engine/   Remotion 4.0.540 (React 19, TS, Three.js) <- storyboard   |
|      |      Studio preview on localhost:3000, CPU draft renders                    |
|      +-- apps/dashboard  React + Vite + Tailwind, local only                       |
|      +-- apps/backend    FastAPI, thin API over SQLite for the dashboard           |
|      +-- data/database/reelforge.sqlite                                            |
|      +-- output/{drafts,approved,rejected,covers,reports}                          |
|                                                                                    |
|  infra/ada  ---- ssh ada / rsync ---->  ADA CLUSTER  (plafnet2, RTX 3090 24 GB)    |
|                                          sbatch: kokoro CUDA, remotion render,     |
|                                          ffmpeg h264_nvenc, QA ffprobe             |
|                                          results rsync'd back to output/           |
+-----------------------------------------------------------------------------------+
```

Why hybrid: the brief assumed a local RTX 3090. Inspection found no NVIDIA GPU locally and only about 1.5 GB of free RAM at the time of inspection. The user then authorised the Ada cluster, whose plafnet2 nodes carry the RTX 3090s. Every stage still has a local fallback so the system degrades gracefully: CPU TTS, CPU render, libx264 encode.

## 2. Pipeline stages and ownership

| Stage | Package | Input | Output | Runs on |
|---|---|---|---|---|
| Research | services/research | RSS, arXiv API, Hugging Face, GitHub trending pages | Topic rows (score, sources, claims) in SQLite, JSON in data/topics | Local |
| Script | services/scripts | Topic + research brief | Script JSON (hook variants, narration, scenes, caption, hashtags) in data/scripts | Local, Claude Code via generate-script skill |
| Storyboard | services/storyboard | Script JSON | Storyboard JSON (scenes with timing, visual recipe, components, SFX) in data/storyboards | Local |
| Voiceover | services/tts | Storyboard narration | WAV per scene plus word timings JSON in assets/audio/<reel_id>/ | Ada CUDA primary, local CPU fallback |
| Captions | services/captions | Word timings | Caption JSON (Remotion `Caption[]`, pages) | Local |
| Render | services/rendering | Storyboard + audio + captions as Remotion input props | MP4 draft/final, cover PNG | Ada primary, local draft |
| QA | services/quality | MP4 | QA report JSON plus contact sheet PNG | Local or Ada |
| Publish | services/publishing | Approved MP4 | Export package: MP4, cover, caption.txt, hashtags.txt, checklist.md | Local |
| Scheduler | services/scheduler | Daily plan | Jobs table, retries, resource gating | Local |

The video engine never reads the database. It receives one JSON `ReelSpec` as input props (validated with zod in TypeScript and pydantic in Python, same schema), which keeps renders reproducible from a single file.

## 3. Data model (SQLite)

```
topics        id, slug, name, category, description, sources(json), published_at,
              notes, verified_claims(json), unverified_claims(json),
              score_novelty .. score_shareability, score_total, status, used_at
scripts       id, topic_id, version, title, hook_selected, hooks(json), narration,
              scenes(json), on_screen_text(json), caption, hashtags(json), cta,
              sources(json), created_at
storyboards   id, script_id, version, style, scenes(json), total_frames, status
voiceovers    id, storyboard_id, provider, voice, speed, audio_path, timings_path,
              duration_s, text_hash, created_at
renders       id, storyboard_id, profile, machine, output_path, cover_path,
              render_seconds, peak_ram_mb, peak_vram_mb, status, error
qa_reports    id, render_id, technical(json), visual(json), editorial(json),
              score, passed, report_path
jobs          id, kind, payload(json), state, priority, attempts, worker,
              created_at, started_at, finished_at, error
publications  id, render_id, export_dir, caption_path, status, published_at
```

Job states: `queued -> running -> succeeded | failed -> retrying -> dead`. A job records which machine ran it (`local` or `ada:<node>`).

## 4. Video engine layout

```
video-engine/
  public/fonts/     Inter, Space Grotesk, JetBrains Mono (OFL, variable TTF)
  public/sfx/       CC0 kit (see assets/sfx/CREDITS.txt)
  public/voice/     per-reel voiceover WAVs, generated, git-ignored
  src/design/       tokens.ts (palettes, type scale, safe zone, quality profiles)
                    motion.ts (easings, springs, durations, seam vectors)
                    fonts.ts  (local font loading)
  src/layers/       Stack.tsx: BgMesh, GridLines, Grade, Grain, Vignette, ReelFrame
  src/animations/   Entrance, Stagger, SceneExit, Breathe, parallax, particles
  src/typography/   WordReveal, CharReveal, Headline, Counter, HighlightPill, Kicker
  src/scenes/       reusable scene archetypes (hook, concept, diagram, code, payoff, cta)
  src/visuals/      AI visualisations: neural net, transformer, attention, RAG, agent loop,
                    tool call, memory, vector search, GPU grid; dev: terminal, code, API
  src/three/        Three.js scenes with 2D fallback
  src/transitions/  presets built on @remotion/transitions plus hand-rolled seams
  src/captions/     word-highlight captions from Caption[] JSON
  src/audio/        music bed, SFX cue placement, ducking under VO
  src/compositions/ Reel (storyboard-driven), SmokeTest, Cover (Still)
  src/schema/       ReelSpec zod schema shared with Python
```

Rules enforced in code review: `useCurrentFrame` and `interpolate` only, every interpolate clamped, no CSS transitions, no `useFrame` in Three.js, fonts from `public/`, SFX start 2 to 3 frames before the visual they accent.

## 5. Quality profiles

| Profile | Size | Particles | 3D | Concurrency (local / Ada) | Encode |
|---|---|---|---|---|---|
| draft | 720x1280 | 35% | simplified | 1 / 8 | libx264 crf 24 |
| standard | 1080x1920 | 100% | normal | 2 / 12 | libx264 crf 18 or h264_nvenc p5 cq 20 |
| cinematic | 1080x1920 | 160% | detailed | 2 / 16 | h264_nvenc p5 cq 18 |

Post-processing always normalises to yuv420p, bt709 limited range, AAC 192 kbps, faststart, then validates with ffprobe (reel-export skill recipe).

## 6. Ada integration

`infra/ada/` holds the SLURM templates and the sync script. Flow for a remote render:

1. `rsync` the reel's input bundle (storyboard JSON, audio, captions) and the video-engine source (without node_modules) to the Ada working directory.
2. `sbatch` a job: partition `plafnet2`, account `plafnet2`, `--exclude=gnode118`, 1 GPU, 8 CPUs, 32 GB. The job loads `u22/ffmpeg/7.1.1`, uses a user-local Node.js in the working directory, runs `remotion render` with concurrency 12, encodes with `h264_nvenc`, writes a QA probe.
3. Poll `squeue` / `sacct`, then `rsync` the MP4, cover and report back into `output/`.

The scheduler treats an Ada failure (queue full, node down) as a retryable error and can fall back to a local draft render.

## 7. Security and budget

- No paid APIs. Research uses public RSS, the arXiv API, Hugging Face public pages and GitHub trending HTML, all fetched with a generic user agent and rate limiting.
- Research pages are untrusted data: parsed into structured fields, never executed as instructions.
- Secrets never enter the repo. `.env.example` documents configurable paths; Ada access uses the user's existing SSH key.
- Generated media and model weights are git-ignored.
- Kokoro weights (Apache 2.0) download to a cache outside the repo on first use.
- The dashboard binds to 127.0.0.1 only.
