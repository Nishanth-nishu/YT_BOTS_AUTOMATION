---
name: divine-character-animation
description: Produce short, cinematic, respectful animation shots of Indian mythological and mythology-inspired characters with local models (Wan 2.2 Animate, Wan 2.2 Fun Control, ComfyUI) and Blender on a 24 GB NVIDIA GPU. Use when the user asks to animate a deity or epic character, make a mythology shot, build or check a character reference sheet, or QA a generated shot. Works one short shot at a time and refuses to start a shot until the hardware, licence, rights and reference-sheet gates pass.
---

# Divine character animation

One character, one short shot, checked, before anything bigger. Never build
ahead of a shot that has not been tested.

## Status: read this first

Written 2026-11-11. **No shot has been generated yet.** The development laptop
has no NVIDIA GPU, no ComfyUI and no Blender, so nothing that needs them has
been built or tested. What exists and is tested:

| Piece | Where | State |
|---|---|---|
| Hardware gate | `python -m animeforge.audit` | works |
| Disk-space gate | `animeforge.storage.ensure_space` | works |
| Model licence gate | `animeforge.registry.require` | works; Wan 2.2 models registered |
| Character rights gate | `animeforge.rights.require_character` | works; 16 epic characters seeded |
| Reference sheet template and check | `python -m animeforge.references` | works; no character has a complete sheet |
| Shot QA and contact sheet | `python -m animeforge.shotqa` | works on any video; thresholds not yet calibrated on generated shots |
| ComfyUI workflow templates | `workflows/` | **not written** |
| Blender scene templates | `blender/` | **not written** |
| Motion reference pipeline | | **not written** |
| Shot generation scripts | | **not written** |
| Sample animation | | **not made** |

Do not add a workflow, template or script to the "works" rows until it has
produced a shot that passed step 7 on the target GPU. Do not describe an
untested file as working.

## The gates, in order

Stop at the first one that fails and tell the user what it needs. Do not work
round a gate.

1. **Hardware.** `python -m animeforge.audit` must report an NVIDIA GPU with
   24 GB VRAM. Exit code 2 means this machine cannot generate shots: say so
   and stop. Do not start jobs on a shared or institutional cluster unless the
   user has confirmed they are allowed to use it for this project.
2. **Disk.** Before any download call `ensure_space(models_dir, need_gb, what)`
   with the real size from the model host. Wan 2.2 Animate 14B is 67.4 GB as
   published. Never download first and check after.
3. **Model licence.** `require("<model-id>", acknowledged=settings().acknowledged)`
   for every model, node pack and preprocessing model the shot will load. If
   it raises, stop. A quantized, FP8 or GGUF variant is a different checkpoint:
   add it to `animeforge/registry/models.json` with its own source and licence
   before using it. Never swap in another model because the first was refused.
4. **Character rights.** `require_character(id, territory)`. Epic characters
   are "conditional": the user must accept the conditions (own design only;
   respectful treatment; review before publishing).
5. **Reference sheet.** `python -m animeforge.references check <id>` must pass:
   front, side, three-quarter, full body, expression sheet, costume, ornaments,
   poses, palette, and the `defining` block.

## Making one shot

6. **Plan the shot** as a small JSON beside the character: what happens in
   five seconds or less, camera move, which control inputs (first frame, last
   frame, pose sequence, depth, edges), visual direction. If the shot restates
   a defining attribute differently, it must name it in `story_reason`;
   `references.diff_defining` rejects anything else.
7. **Generate, then QA.** `python -m animeforge.shotqa shot.mp4 --seconds 5 --width W --height H`.
   Measured checks (freeze, flicker, popped frames, motion, duration, size)
   must pass. Then open the contact sheet beside the reference sheet and check
   by eye: face, anatomy, **number of limbs**, hands, costume, ornaments,
   object interaction, lighting. Record who reviewed it in the report's
   `reviewed_by`. A shot is approved only when both are done.
8. Only after an approved shot: write down the exact workflow, checkpoint
   files, seed, settings, VRAM peak and time in the registry's `benchmark`
   field, and save the workflow as a template.

## Rules that do not bend

- **Anatomy.** For a character with more than two arms, do not rely on
  generative video to keep the count. Use a rigged 3D character in Blender, or
  animate limbs as separately controlled layers, and count limbs on every
  frame of the contact sheet.
- **Consistency.** Defining attributes (skin colour, arms, crown, weapon,
  ornaments, costume) never change between scenes without a story reason.
- **Respect.** These figures are sacred to living traditions. No mockery, no
  sexualised or degrading depiction, no putting words of a real religious
  leader or institution in their mouths. Every shot is reviewed by a person
  before publishing.
- **Originality.** Never copy a specific film, TV, game or comic design, and
  never name one, or an artist, in a prompt. Traditional iconography (blue
  skin, peacock feather, flute, trident) is common heritage; one studio's
  rendering of it is not.
- **Reference video.** Motion taken from a video of a person needs that
  person's agreement and a right to use the footage. Film our own, or use
  motion we created in Blender.
- **Reference voice and likeness.** No real actor's face, body or voice.

## Fitting 24 GB (to be verified, not assumed)

The official Wan 2.2 Animate commands are documented for 80 GB VRAM. Expected
route on a 3090, each step to be measured before it is relied on: an FP8 or
quantized checkpoint (registered and licence-checked as its own entry), text
encoder on CPU, model offloading between stages, short segments (about 5 s at
480p or 720p), one model in VRAM at a time, VRAM logged throughout. Start with
Wan 2.2 Fun Control 5B, which is the smaller model. If a workflow does not fit,
report the measured peak; do not claim it works.

## Visual directions

Traditional devotional painting, 3D cinematic, stylised anime, epic fantasy.
Pick one per character in `character.json` (`visual_direction`) and keep it.
Jewellery and textiles are defining detail: put them on the ornament and
costume references, not only in prompts.

## Files

- `templates/character.template.json` and `templates/shot.template.json`: start a character or a shot from these.
- `INSTALL.md`: what to install on the GPU machine, in order, with the space each step needs.
