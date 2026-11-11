# AnimeForge roadmap and status

Last updated 2026-11-11. A module is listed as working only when a real test of
it has passed. "Not started" means no code exists.

## Where things stand

| Phase | What | Status |
|---|---|---|
| 1 | Hardware and dependency audit | **Done.** See [AUDIT.md](AUDIT.md). |
| 2 | Hindi voice prototype | Not started for the new engines. The existing Kokoro Hindi voices work on CPU. IndicF5 and Indic Parler-TTS are gated and unverified; Chatterbox is usable but untested. |
| 3 | Character consistency (ComfyUI, IPAdapter, ControlNet, LoRA) | Not started. Needs the GPU. Reference-sheet template and check exist. |
| 4 | Image-to-video (Wan, LTX-Video, AnimateDiff) benchmarks | Not started. Needs the GPU. No model has been benchmarked. |
| 5 | Lip-sync (LatentSync, MuseTalk) | Not started. Needs the GPU. Anime compatibility unknown. |
| 6 | End-to-end 30-second video | Not started on the new stack. The older VRM/Remotion pipeline makes 50-second episodes today. |
| 7 | Multi-episode automation | Not started. |
| 8 | Quality, licensing and monetization audit | Licence registry and rights database exist; the audit itself is not done. |

## What exists and is tested (CPU only)

| Module | Purpose | Run it |
|---|---|---|
| `animeforge.audit` | Reports GPU, VRAM, RAM, disks, tools; says which phases a machine can run | `python -m animeforge.audit [--ssh-host ada]` |
| `animeforge.storage` | Refuses a download that would leave under 20 GB free | `python -m animeforge.storage` |
| `animeforge.registry` | 27 models and tools with code licence, weight licence, commercial limits; `require()` gate with no fallback | `python -m animeforge.registry` |
| `animeforge.rights` | Character database and asset rights registry (SQLite); `require_character()` gate | `python -m animeforge.rights seed`, `list`, `check <id>` |
| `animeforge.references` | Character reference-sheet template and completeness check | `python -m animeforge.references check <id>` |
| `animeforge.shotqa` | Measures freeze, flicker, popped frames, motion; makes a contact sheet | `python -m animeforge.shotqa shot.mp4` |
| Skill `divine-character-animation` | The gated one-shot-at-a-time workflow | `.claude/skills/divine-character-animation/SKILL.md` |

## Phase 1 findings

1. **The development laptop cannot run the GPU phases.** It has an Intel UHD
   770, no NVIDIA GPU, 15.7 GB RAM (target 32 GB), no WSL, no Blender, and a
   CPU-only PyTorch. It has 165 GB free on C: and two empty 195 GB drives.
2. **A GPU cluster is reachable** (`ssh ada`, the IIIT Ada cluster). It was only
   probed with status commands. Its home directory had 6.1 GB free. It is an
   institutional research cluster: whether it may be used for a monetized
   channel is a question for its usage policy and its owners, not something
   this project can assume.
3. **Licence findings that change the plan**
   - Blocked for monetized output: Wav2Lip, InsightFace pretrained models, and
     therefore IP-Adapter FaceID. PuLID is unverified for the same reason.
   - Clear to use: Wan 2.1 and Wan 2.2 (Apache-2.0 code and weights),
     AnimateDiff, ControlNet union SDXL, SDXL base, Animagine XL 4.0, standard
     IP-Adapter, Kohya sd-scripts, MuseTalk (subject to its dependencies),
     Chatterbox Multilingual (Hindi supported, output is watermarked).
   - Not yet readable: IndicF5 and Indic Parler-TTS are gated on Hugging Face;
     their terms need a logged-in read. LTX-Video's weights use a custom
     licence that was not read in full. Indic-Speak is licensed "other" and
     built on Llama 3.2.
   - Wan 2.2 Animate 14B is 67.4 GB and its documented commands need 80 GB
     VRAM. Running it on 24 GB needs a quantized variant, which must be
     registered and licence-checked as its own checkpoint.
4. **Existing assets:** the three base 3D models are CC0 with evidence
   recorded. The sound-effects folder inherited from the earlier repository
   has no recorded origin and is marked pending.

## Not built yet (from the specification)

REST API, job queue with retries, model caching, VRAM monitoring, structured
logging; the story engine beyond the existing epic-episode format; subtitles
in Devanagari (the fonts lack it); horizontal 1920x1080 layouts; thumbnails;
every GPU engine and its adapter; ComfyUI and Blender templates; the sample
five-second shot.

## Decisions needed before Phase 2 to 5 can start

1. Which machine has the RTX 3090, and may it be used for this project?
2. A Hugging Face login to read and accept the AI4Bharat model terms.
3. Whether reference voices will be recorded by you (for the cloning engines)
   or voices will be created from text descriptions only.
