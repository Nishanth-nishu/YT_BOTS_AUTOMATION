"""One character still with an SDXL checkpoint (default Animagine XL 4.0).

Writes the PNG and a JSON sidecar with seed, time and peak VRAM.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

NEG = ("border, frame, picture frame, letterboxed, lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, "
       "fewer digits, cropped, worst quality, low quality, low score, bad score, "
       "average score, signature, watermark, username, blurry, extra arms, extra legs")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="cagliostrolab/animagine-xl-4.0")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--count", type=int, default=1)
    a = ap.parse_args()

    import torch
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

    pipe = StableDiffusionXLPipeline.from_pretrained(
        a.repo, torch_dtype=torch.float16, use_safetensors=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for i in range(a.count):
        seed = a.seed + i
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        img = pipe(prompt=a.prompt, negative_prompt=NEG, width=a.width, height=a.height,
                   num_inference_steps=a.steps, guidance_scale=a.cfg,
                   generator=torch.Generator("cuda").manual_seed(seed)).images[0]
        p = out if a.count == 1 else out.with_name(f"{out.stem}-{seed}{out.suffix}")
        img.save(p)
        meta = {"model": a.repo, "prompt": a.prompt, "negative": NEG, "seed": seed,
                "width": a.width, "height": a.height, "steps": a.steps, "cfg": a.cfg,
                "seconds": round(time.time() - t, 1),
                "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                "gpu": torch.cuda.get_device_name(0)}
        p.with_suffix(".json").write_text(json.dumps(meta, indent=1))
        print(json.dumps(meta))


if __name__ == "__main__":
    main()
