# AnimeForge roadmap and status

Last updated 2026-11-12. A module is listed as working only when a real run of
it has passed. Every number below was measured on an RTX 3090 (24 GB) on the
Ada cluster; details and dates are in `animeforge/registry/models.json`.

## Where things stand

| Phase | What | Status |
|---|---|---|
| 1 | Hardware and dependency audit | **Done.** See [AUDIT.md](AUDIT.md). |
| 2 | Hindi voice | **Working, not yet listened to.** Chatterbox Multilingual, built-in voice. |
| 3 | Character consistency | **Improved, not solved.** A character LoRA holds face and costume in the stills; the video model can still drift within a shot. |
| 4 | Image-to-video | **Working.** Wan 2.2 TI2V-5B benchmarked at four settings. |
| 5 | Lip-sync | **Prototype working** for a still close-up. No licensed face-model lip-sync exists yet. |
| 6 | End-to-end 30-second video | **Done once.** `arjuna-chidiya-ki-aankh`, 31.7 s, voice and subtitles. |
| 7 | Multi-episode automation | **Working mechanically.** A second episode ran through the queue with one automatic retry; its content failed review. |
| 8 | Quality, licensing, monetization audit | **Done as a written audit below.** Open items listed. |

## Measured results

### Phase 2: Hindi voice (Chatterbox Multilingual 0.1.7)

- 3.16 GB peak VRAM, 11.7 s to load, 0.56 to 0.64 x real time once warm.
- Six test lines read back by Whisper large-v3: mean character error 0.086.
  Two lines had no errors. Typical slips are one sound (बाण heard as बार).
- The six lines of the Arjuna episode: errors 0.0 to 0.172, all under the 0.25 limit.
- Voice is the engine's built-in one. No reference clip was used, so no real
  person's voice is cloned. Every file carries the PerTh watermark.
- **Not done:** nobody has listened for accent and naturalness. A transcription
  score cannot judge that. The AI4Bharat engines are still gated.

### Phase 3: consistency

**IP-Adapter Plus (first method).** Similarity to the reference across six
scenes: 0.710 without it, 0.804 at 0.6 (copies the reference background too),
0.823 with a plain-background reference at 0.45. In the first episode cut
Arjuna kept crown, armour and sash but his face differed in each of his shots.

**Character LoRA (current method).** Kohya sd-scripts v0.12.3 on Animagine XL 4.0.

- Training set: 64 candidate pictures drawn by us in 16 framings, 33 chosen by
  eye. 1200 steps, rank 16, 25 minutes, about 8 GB VRAM, 81 MB file.
- Test (six scenes, same seeds, by eye): at weight 0.9 the character is the
  same in every picture but skin lightens and backgrounds bleach. At weight
  0.6 with the step-800 file, skin and scene colour hold and the character
  still matches. That setting is used, with the adapter off.
- The similarity score does not show the gain (pictures to each other: text
  0.789, adapter 0.854, LoRA 0.6 0.813). The adapter is rewarded for copying
  the reference's pose and pale background. The choice was made by eye.
- In the re-cut episode, the walking shot and the aiming shot now show the
  same Arjuna in a green forest. Two flaws remain: the walking still has a
  decorative arch border at the top, and in the last shot the video model
  changes his face as he turns toward the camera.
- **Not done:** a second training round on cleaner pictures (the first set was
  drawn with the adapter and is pale), LoRAs for other characters, ControlNet
  poses, ComfyUI workflows, any identity control inside the video model.

**Transitions.** Scene changes dissolve over 0.4 s (`crossfade`). A shot marked
`continues` starts from the previous clip's last frame and is joined with a
plain cut, so motion carries across. Tried once (aim, then release): the join
is seamless, but a large turn inside the chained shot made the face drift.
Chained shots should keep the same framing and small motion.

### Phase 4: image-to-video (Wan 2.2 TI2V-5B, diffusers)

| Size | Steps | Time for 5 s | Peak VRAM | Shot check |
|---|---|---|---|---|
| 704x1280 | 50 | 1050 s | 17.19 GB | pass |
| 704x1280 | 30 | 680 s | 17.19 GB | pass (the default) |
| 480x864 | 30 | 267 s | 14.38 GB | flicker flagged |
| 480x864 | 20 | 203 s | 14.38 GB | flicker flagged |

Needs model CPU offload and tiled VAE decode; without either it runs out of
memory. Of eight episode clips made so far, two failed the flicker check
(fast motion: walking, arrow release) and passed when redone with a new seed
and calmer motion. Wan 2.1 14B, Wan 2.2 Animate, LTX-Video and AnimateDiff were
not benchmarked.

### Phase 5: lip-sync

- LatentSync is blocked (needs InsightFace models, non-commercial). MuseTalk is
  unverified (unlicensed face-parsing weights). Wav2Lip stays blocked.
- What works instead: "lip flaps". Two low-strength redraws of one close-up
  (mouth closed, mouth open), the mouth found by image difference, opened by
  the voice loudness, held on twos. Test: 3.5 s, 12 mouth changes, loudness to
  mouth correlation 0.84, 8.9 GB VRAM. The face stays still and the mouth moves.
- Limits: it is open/closed only (no vowel shapes), it works on a still
  close-up, and the test close-up is a separately drawn face, not the
  episode's Arjuna. It is not yet wired into the episode cut.

### Phase 6: first episode

`output/animeforge/arjuna-chidiya-ki-aankh.mp4`: 31.7 s, 720x1280, 24 fps, six
shots, Hindi narration, burned Devanagari subtitles, loudness normalised. All
six shots pass the measured checks. By eye: the hermitage shots are clean; the
bird looks alive although the line says it is wooden; Arjuna is consistent in
two of his three shots (see Phase 3). The earlier cut is kept beside it as
`arjuna-chidiya-ki-aankh.v1-adapter.mp4` for comparison.
No music or sound effects. Not uploaded anywhere.

### Phase 7: automation

- `animeforge.story` turns a seed (person-written Hindi lines) into an episode
  file; the local 7B model writes only the picture plan. Its plan for Karna
  did not match the lines and was rewritten by hand.
- `animeforge.jobs` (SQLite queue, retries with doubling delay, dead-letter)
  and `animeforge.api` (FastAPI) drive the cluster through `animeforge.slurm`.
- `karna-kavach-daan` was queued and run by the worker. The first attempt
  failed on a stalled package download and was retried automatically; the
  second made six clips and six voices and assembled a 39.4 s video.
- Review failed it, correctly: on one line the voice engine kept speaking
  nonsense after the sentence (error 1.9). The voice step now transcribes
  every take and retakes a bad one (up to four). Not yet re-run.
- By eye it has a worse fault the checks cannot see: Karna was drawn looking
  female in his first shot. He needs the same LoRA treatment as Arjuna.

## Phase 8: audit

**Licences.** Every model in the published video is gated by the registry:
Animagine XL 4.0 (conditional, acknowledged), IP-Adapter Plus (acknowledged),
Wan 2.2 TI2V-5B (Apache-2.0), Chatterbox (MIT, watermarked). Whisper is used
only for checking. Noto Sans Devanagari is OFL, licence file included. Blocked
or unverified models (Wav2Lip, InsightFace, IP-Adapter FaceID, LatentSync,
MuseTalk, lbpcascade_animeface) are not used and nothing was substituted for them.

**Rights.** Characters are original designs with entries in the rights
database; the stories are retellings of public-domain epics in our own words.
Prompts are checked for protected names and artist tags.

**Open before monetized publishing**

1. Ada is an institutional research cluster. Whether it may render videos for
   a monetized channel is its owners' decision. Ask before relying on it.
2. YouTube asks creators to disclose realistic altered or synthetic content.
   Stylised animation is generally outside that, but the synthetic voice
   should be considered when filling the upload form.
3. Mass-produced, near-identical videos risk YouTube's "inauthentic content"
   monetization rule. Six-shot narrated clips with one varying character are
   close to that line until the picture quality and variety improve.
4. Listen to the voice; finish the face consistency work; add music and sound
   with recorded origins (the inherited sound-effects folder is still pending).
5. Religious figures: the epics' characters are revered. Keep depictions
   respectful and the retelling faithful; the fact-check step from the older
   pipeline is not yet wired into `animeforge.story`.

## Operations learned

See `animeforge/cluster/README.md`. In short: node scratch is purged weekly, so
models live on share6 (50 GB used by this project; about 9 GB of quota left)
and are restored at job start; environments are rebuilt per node (about 2
minutes when the package servers are fast); one episode costs roughly 70 to 75
GPU-minutes, and a character LoRA about 45 (pictures, training, test).

## Not built

ComfyUI workflows, Blender templates, the motion-reference pipeline, Wan 2.2 Animate and Fun Control, AI4Bharat voices (need your
Hugging Face login), lip flaps inside episodes, music, horizontal 1920x1080,
thumbnails, and upload of AnimeForge videos (waiting for your go-ahead).
