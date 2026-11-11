# Installing the shot pipeline on the GPU machine

Written 2026-11-11 from the projects' own documentation. **None of these steps
has been run**: there was no NVIDIA GPU to run them on. Treat the sizes as the
published repository sizes and the VRAM notes as claims to verify. Correct this
file as each step is actually done.

Target: Windows 11 or WSL2/Linux, NVIDIA RTX 3090 (24 GB), 32 GB RAM or more,
150 GB free on the models drive.

## 0. Check the machine

    python -m animeforge.audit            # must exit 0
    python -m animeforge.storage          # free space on the drives AnimeForge uses

Set `ANIMEFORGE_MODELS_DIR` to the drive with the most space.

## 1. PyTorch with CUDA

Install the CUDA build of PyTorch that matches the driver, in its own virtual
environment. Confirm `torch.cuda.is_available()` is true and re-run the audit.

## 2. ComfyUI (GPL-3.0, run as its own process)

Clone https://github.com/Comfy-Org/ComfyUI into its own folder with its own
environment. AnimeForge talks to it over HTTP only. Acknowledge the condition
by adding `comfyui` to `ANIMEFORGE_ACK`.

## 3. Smallest video model first: Wan 2.2 Fun Control 5B

Registry id `wan2.2-fun-control`, checkpoint `alibaba-pai/Wan2.2-Fun-5B-Control`
(Apache-2.0). Before downloading, read its size from the model host and call
`ensure_space`. Generate one five-second control-driven shot and run
`python -m animeforge.shotqa` on it. Record VRAM peak and time in the
registry's `benchmark` field.

## 4. Wan 2.2 Animate

Registry id `wan2.2-animate`, checkpoint `Wan-AI/Wan2.2-Animate-14B`
(Apache-2.0, 67.4 GB as published). The official commands are documented for
80 GB VRAM. On 24 GB a quantized or FP8 variant is needed: that is a different
file from a different publisher, so add it to the registry with its source and
licence first. Its pose and face preprocessing models are separate downloads
with their own licences: check each. InsightFace models are non-commercial and
are blocked in the registry.

## 5. Blender

Install Blender from blender.org (GPL; called as an external program). Needed
for multi-arm characters, cloth and hair simulation, camera rigs and
compositing. Scene templates do not exist yet.

## 6. Voices for a shot with speech

The existing pipeline's Kokoro Hindi voices work on CPU today. The AI4Bharat
models (`indic-parler-tts`, `indicf5`) are gated on Hugging Face: log in,
read and accept their terms, record them in the registry, then benchmark.
