# Phase 2 Benchmark: "How AI Agents Actually Work"

Reel id `agents-benchmark`. 56.9 s, 1708 frames at 30 fps, 7 scenes, 149 word-level captions, Kokoro `af_heart` voice, synthesised ambient bed, 9 SFX cues.

Scenes (all storyboard-driven, no per-reel code):

| # | Scene | Kind | Visual |
|---|---|---|---|
| 1 | hook | hook (cinematic) | Kinetic hero type with hero-colour words, animated strike through "chatbot", glowing orb, particle field |
| 2 | loop | loop | One-reply chat bubble goes still, then a Think / Act / Observe ring draws itself with a travelling pulse |
| 3 | reason | reasoning | LLM node pulses beside a thought panel; plan steps type in and tick |
| 4 | tool | toolCall | JSON request card flies Agent -> search, spinner while running, response card flies back |
| 5 | memory | memory | Scratchpad chips stack; vector grid lights up as a query finds its 4 nearest neighbours |
| 6 | workflow | workflow | Four-stage loop diagram with a packet cycling, "Done" node lands |
| 7 | payoff | payoff | Hero typography, CTA pill, particle bloom |

Seams follow the vector law: current (slide left), zoomIn into reasoning, up into memory, zoomOut into the workflow overview.

## Machines

| | Local | Ada gnode113 |
|---|---|---|
| CPU | i5-13500, 14c/20t | 16 of 48 cores allocated |
| GPU | Intel UHD 770 (no NVENC) | RTX 3090 24 GB |
| RAM | 15.7 GB total, about 1.5 GB free before render | 48 GB allocated of 251 GB |
| Encoder | libx264 crf 24 (draft) | h264_nvenc p5 cq 20 |

## Run 1 (before caption and loudness fixes)

| Metric | Local draft 720x1280, concurrency 2 | Ada standard 1080x1920, concurrency 16 |
|---|---|---|
| Render time | 105.6 s (16.2 frames/s) | 262 s (6.5 frames/s) |
| Encode time | 4.6 s | 9 s (NVENC) |
| Peak render process tree RSS | 2.04 GB | 10.26 GB (16 Chrome tabs) |
| Peak system RAM used | 16.8 GB (min available 13 MB) | n/a |
| CPU | avg 30%, peak 99.7% | n/a |
| Output | 4.98 MB | 11.94 MB |
| ffprobe | 720x1280 h264 yuv420p 30 fps aac, 56.94 s | 1080x1920 h264 yuv420p tv-range bt709 30 fps aac, 56.94 s |
| Loudness | -22.5 LUFS, TP -0.4 dBFS (FAIL) | -22.5 LUFS, TP 0.0 dBFS (FAIL) |
| Technical QA | 12/14 pass | 12/14 pass |

Observations:
- Local rendering at concurrency 2 drove available RAM to 13 MB because Opera, Claude and Edge WebView already held most memory. The scheduler must check free RAM and drop to concurrency 1 (or offload to Ada) below 2.5 GB free.
- Ada's wall time was dominated by Chrome frame capture of large blurred gradients and SVG glow filters, not by encoding. 16 tabs on 16 cores gave 6.5 frames/s at full resolution; the per-frame cost scales with pixels (2.25x the draft).
- Both outputs were too quiet and the Ada mix clipped: the VO was normalised to -3 dBFS peak and SFX stacked on top. Fix: two-pass EBU R128 loudnorm to -16 LUFS / -1.5 dBFS true peak in both encoders.

Visual QA on run 1 found: hook and payoff titles wrapping into 5 to 7 lines and colliding with captions, title/diagram overlap on loop and workflow, strike line on the wrong words, CTA overflow, and caption pages containing bare punctuation tokens that bled across scene boundaries. All fixed in the code (auto-sized `SceneTitle`, inline strike, shared vertical layout, scene-aware caption paging, Kokoro punctuation merging).

## Run 2 (final)

Filled in below after the final renders.
