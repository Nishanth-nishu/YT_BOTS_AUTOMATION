---
name: create-storyboard
description: Convert an approved REELFORGE script into a storyboard JSON with one scene per beat, a scene kind, visual data, highlights, seams and SFX intent, then validate it against the schema. Use when a script is approved, or the user says "storyboard this", "break this into scenes".
---

# create-storyboard

## Purpose
Turn narration into render-ready scene definitions that the engine's scene kinds understand.

## Trigger
A script JSON exists in `data/scripts/<id>.json` with status approved, or the user hands over a script.

## Inputs
- Script (hook, narration per beat, on-screen text, visual instructions, sources).
- Available scene kinds in `video-engine/src/schema/reelSpec.ts` (`hook`, `loop`, `reasoning`, `toolCall`, `memory`, `workflow`, `payoff`, `concept`, `code`, `chart`).

## Outputs
- `data/storyboards/<id>.json` matching `services/common/schema.py::Storyboard`.

## House format fields (every reel since 2026-11-10)
- `voice`: `{"provider": "kokoro", "voice": "hm_omega", "speed": 1.15}` (male Hinglish host).
- `presenter`: `{"enabled": true, "mood": "hype"}`; the host is big in the hook scene and a badge at the left of the caption band elsewhere.
- Every scene: `narration` (Devanagari + Latin) and `captionText` (romanised, same sentence and word count).
- `dmKeyword` (`LETS GO`) and `dmLink` (the one link the DM bot sends; defaults to `sources[0]`). No link in `caption`, titles, lines, `cta`, or `data` (terminal `command` must not be a URL: write `git clone dsh-superagent-prototype`, not the GitHub URL).
- Last scene is `payoff` with `cta` "Comment LETS GO, link DM mein aayega".

## Workflow
1. One scene per narration beat (6 to 9 scenes for 30 to 60 s). Scene 1 is always `hook`, the last is `payoff` with a `cta`.
2. For each scene set: `kind`, `title` (6 to 10 words, the on-screen headline), `highlight` (1 to 2 words in the hero colour), `data` for the kind, `transition` (seam vector: `current` by default, `zoomIn` when going deeper into the same idea, `up` for a reveal, `zoomOut` for arrival at the big picture, `burst` only when leaving a world).
3. Narration per scene: 10 to 30 words, spoken-language, no jargon without a gloss.
4. Validate schema and house rules (links, Devanagari on screen, hook length, keyword ask, captionText counts):
   ```bash
   .venv\Scripts\python -m services.common.rules data/storyboards/<id>.json
   ```
5. Hand to `generate-voiceover`.

## Validation
Schema passes; every scene has a different `kind` from its neighbour unless intentional; no scene relies on a static background only; total narration 90 to 150 words.

## Error handling
- Unknown `kind`: either map to an existing kind or create it with `create-cinematic-reel` / `create-animated-explainer`.

## Dependencies
Python venv, pydantic.
