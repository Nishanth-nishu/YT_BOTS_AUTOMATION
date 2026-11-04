---
name: generate-script
description: Write a 20 to 60 second faceless Reel script for a researched AI or tech topic in REELFORGE: three hooks, the chosen hook, narration with hook / context / development / payoff / CTA, scene breakdown, on-screen text, caption and hashtags, all traced to sources. Use when a topic is selected, or the user says "write the script", "script this topic".
---

# generate-script

## Purpose
Produce the structured script JSON that `create-storyboard` consumes, accurate to the research brief and natural when spoken.

## Trigger
A topic in `data/topics/` has status `selected`, or the user names a topic with sources.

## Inputs
- Topic brief: name, category, verified claims, source URLs, publication dates.
- Hook formulas from the user-level `ig-reel` skill; de-slop rules from `ig-human`.

## Outputs
- `data/scripts/<id>.json`:
  `title, topic_id, category, hooks[3], hook_selected, narration, scenes[] (beat, narration, on_screen_text, visual), voice_instructions, caption, hashtags[], cta, sources[]`.

## Workflow
1. Write three hooks (curiosity, contrast, stake). Score each on curiosity, clarity, novelty, relevance, accuracy (1 to 5). Pick the top; never a hook the body cannot pay off.
2. Narration structure: hook (1 to 2 sentences), context (1), development (3 to 4 beats, one idea each), payoff (the result, number or reframe), optional CTA (one action).
3. Spoken-language rules: sentences under 16 words, no "delve", "game-changer", "revolutionary"; contractions welcome; numbers only when verified.
4. Every factual sentence maps to a source URL in `sources`. Unverified claims are cut, not softened.
5. Caption: first line survives the "... more" cut; one ask; three to six hashtags (`ig-caption` skill).
6. Read it aloud mentally for TTS: expand abbreviations the engine mangles or add a `PRONUNCIATION` entry.

## Validation
Word count 90 to 150 for 35 to 55 s at Kokoro's pace; no claim without a source; hook under 14 words.

## Error handling
- Thin research: go back to `research-topic`, do not invent.

## Dependencies
Claude Code (this skill is executed by the agent), `ig-reel`, `ig-human`, `ig-caption` skills.
