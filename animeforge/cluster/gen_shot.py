"""One image-to-video shot with Wan 2.2 TI2V-5B through diffusers.

Writes the MP4 and a JSON sidecar with the settings, wall time and peak VRAM,
which is the benchmark recorded in the registry.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

NEG = ("bright tones, overexposed, static, blurred details, subtitles, text, watermark, "
       "worst quality, low quality, jpeg artifacts, ugly, deformed, disfigured, extra fingers, "
       "poorly drawn hands, poorly drawn face, fused fingers, extra limbs, extra arms, "
       "still picture, messy background, walking backwards, flicker, morphing face")


def fit(img, width: int, height: int):
    """Centre-crop to the target aspect, then resize."""
    from PIL import Image

    w, h = img.size
    want = width / height
    if w / h > want:
        nw = int(h * want)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / want)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize((width, height), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="Wan-AI/Wan2.2-TI2V-5B-Diffusers")
    ap.add_argument("--width", type=int, default=704)
    ap.add_argument("--height", type=int, default=1280)
    ap.add_argument("--frames", type=int, default=121)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--offload", choices=["none", "model", "sequential"], default="model")
    ap.add_argument("--no-tiling", action="store_true", help="decode the whole clip at once (needs more memory)")
    a = ap.parse_args()

    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    t0 = time.time()
    vae = AutoencoderKLWan.from_pretrained(a.repo, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(a.repo, vae=vae, torch_dtype=torch.bfloat16)
    if not a.no_tiling:
        # Measured 2026-11-12 on an RTX 3090: without tiling the VAE runs out of
        # memory decoding 121 frames at 704x1280 after denoising has finished.
        pipe.vae.enable_tiling()
    if a.offload == "model":
        pipe.enable_model_cpu_offload()
    elif a.offload == "sequential":
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.to("cuda")
    load_s = time.time() - t0

    image = fit(load_image(a.image), a.width, a.height)
    torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    frames = pipe(image=image, prompt=a.prompt, negative_prompt=NEG,
                  height=a.height, width=a.width, num_frames=a.frames,
                  num_inference_steps=a.steps, guidance_scale=a.cfg,
                  generator=torch.Generator("cpu").manual_seed(a.seed)).frames[0]
    gen_s = time.time() - t1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    export_to_video(frames, str(out), fps=a.fps)
    meta = {"model": a.repo, "image": a.image, "prompt": a.prompt, "negative": NEG,
            "seed": a.seed, "width": a.width, "height": a.height, "frames": a.frames,
            "fps": a.fps, "steps": a.steps, "cfg": a.cfg, "offload": a.offload, "vae_tiling": not a.no_tiling,
            "load_seconds": round(load_s, 1), "generate_seconds": round(gen_s, 1),
            "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
