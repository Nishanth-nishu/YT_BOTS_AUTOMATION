# AnimeForge hardware and dependency audit

Run: 2026-11-11T21:11:53

## Verdict

**This machine cannot run the GPU phases.**

- no NVIDIA GPU (found: Intel(R) UHD Graphics 770)
- 15.7 GB RAM, target is 32 GB

Can run here:
- story engine (local LLM on CPU)
- character and rights database
- Kokoro Hindi voice (CPU)
- Remotion and FFmpeg rendering (CPU)
- REST API, job queue, QA on audio and files

Needs a machine with an NVIDIA GPU of 24 GB or more:
- ComfyUI image generation, IPAdapter, ControlNet, LoRA training (Phase 3)
- Wan2.1 / LTX-Video / AnimateDiff benchmarks and animation (Phase 4)
- LatentSync / MuseTalk lip-sync (Phase 5)
- IndicF5, Indic Parler-TTS, Chatterbox at usable speed (Phase 2 benchmarks)

## Machine

| Item | Value |
|---|---|
| OS | Windows 10 (10.0.26200) |
| CPU | Intel64 Family 6 Model 191 Stepping 2, GenuineIntel (14 cores, 20 threads) |
| RAM | 15.7 GB (1.3 GB free at audit time) |
| GPU | Intel(R) UHD Graphics 770 |
| PyTorch | 2.15.0+cpu, CUDA no |
| WSL | not installed |
| Disk C:\ | 165.4 GB free of 561.2 GB (used for home, models, cache) |

## Tools

| Tool | Found | Version | Needed for |
|---|---|---|---|
| python | yes | Python 3.11.9 | everything |
| git | yes | git version 2.55.0.windows.3 | everything |
| git-lfs | yes | git-lfs/3.7.1 (GitHub; windows amd64; go 1.25.1; git b84b3384) | model downloads |
| ffmpeg | yes | ffmpeg version 9.0.2-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg  | rendering, audio |
| node | yes | v24.22.1 | Remotion rendering |
| blender | no |  | Blender rendering |
| ollama | yes | ollama version is 0.40.16 | story engine (local LLM) |
| docker | no |  | optional: containerised services |

## Remote host `ada`

- reachable as `ada-gw1.iiit.ac.in`
- GPUs visible on the login node: none (compute nodes are reached through the scheduler)
- scheduler partitions:

```
PARTITION AVAIL NODES GRES
u22* up 1 gpu:2(S:0)
u22* up 1 gpu:4
u22* up 23 gpu:3(S:0-1)
u22* up 1 gpu:3
u22* up 51 gpu:4(S:0-1)
u22-cpu up 6 (null)
ihub up 1 gpu:4
```

- home directory: `ada5:/home2/nishanth.r   50G   44G  6.1G  88% /home2/nishanth.r`
