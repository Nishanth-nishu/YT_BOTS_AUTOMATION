"""GPU side of an episode: a still and a five-second clip for every shot.

Reads animeforge/cluster/episodes/<id>.json. Stills come from the SDXL
checkpoint, with IP-Adapter Plus holding the main character to one reference
image; clips come from Wan 2.2 TI2V-5B. Each model is loaded once. Finished
files are kept, so a retried job only does what is missing.

    python -m animeforge.cluster.episode_job <episode.json> <out dir>
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

from animeforge.cluster import gen_shot
from animeforge.cluster.gen_still import NEG

QUALITY = "anime coloring, masterpiece, high score, great score, absurdres"
W, H, FRAMES, FPS = 704, 1280, 121, 24


def stills(spec: dict, out: Path) -> dict:
    import torch
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline
    from PIL import Image
    from transformers import CLIPVisionModelWithProjection

    todo = [s for s in spec["shots"] if not (out / s["id"] / "still.png").exists()]
    ref_path = out / "reference.png"
    if not todo and ref_path.exists():
        return {"stills_made": 0}
    encoder = CLIPVisionModelWithProjection.from_pretrained(
        "h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        spec.get("still_model", "cagliostrolab/animagine-xl-4.0"), image_encoder=encoder,
        torch_dtype=torch.float16, use_safetensors=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.to("cuda")
    ch = spec["character"]

    def render(prompt: str, seed: int, scale: float, ref):
        pipe.set_ip_adapter_scale(scale)
        return pipe(prompt=prompt, negative_prompt=NEG, ip_adapter_image=ref, width=768, height=1344,
                    num_inference_steps=28, guidance_scale=5.0,
                    generator=torch.Generator("cuda").manual_seed(seed)).images[0]

    t = time.time()
    if not ref_path.exists():
        blank = Image.new("RGB", (224, 224), "gray")
        render(f"{ch['tags']}, {ch.get('reference_scene', 'upper body, simple background, looking at viewer')}, {QUALITY}",
               ch.get("reference_seed", 11), 0.0, blank).save(ref_path)
    ref = Image.open(ref_path).convert("RGB")
    for i, s in enumerate(todo):
        d = out / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        scale = spec.get("reference_scale", 0.6) if s.get("use_reference", True) else 0.0
        prompt = f"{s['subject']}, {QUALITY}"
        seed = s.get("seed", 500 + i)
        render(prompt, seed, scale, ref).save(d / "still.png")
        (d / "still.json").write_text(json.dumps({"prompt": prompt, "seed": seed, "reference_scale": scale}, indent=1))
    made = {"stills_made": len(todo), "stills_seconds": round(time.time() - t, 1),
            "stills_peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
    del pipe, encoder
    gc.collect()
    torch.cuda.empty_cache()
    return made


def clips(spec: dict, out: Path) -> dict:
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    todo = [s for s in spec["shots"] if not (out / s["id"] / "shot.mp4").exists()]
    if not todo:
        return {"clips_made": 0}
    repo = spec.get("video_model", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
    vae = AutoencoderKLWan.from_pretrained(repo, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(repo, vae=vae, torch_dtype=torch.bfloat16)
    pipe.vae.enable_tiling()          # the untiled decode of 121 frames at 704x1280 ran out of 24 GB
    pipe.enable_model_cpu_offload()
    times = []
    torch.cuda.reset_peak_memory_stats()
    for i, s in enumerate(todo):
        d = out / s["id"]
        image = gen_shot.fit(load_image(str(d / "still.png")), W, H)
        t = time.time()
        frames = pipe(image=image, prompt=s["motion"], negative_prompt=gen_shot.NEG, height=H, width=W,
                      num_frames=FRAMES, num_inference_steps=spec.get("steps", 50), guidance_scale=5.0,
                      generator=torch.Generator("cpu").manual_seed(s.get("seed", 500 + i))).frames[0]
        tmp = d / "shot.partial.mp4"
        export_to_video(frames, str(tmp), fps=FPS)
        tmp.rename(d / "shot.mp4")
        times.append(round(time.time() - t, 1))
        (d / "shot.json").write_text(json.dumps({"model": repo, "prompt": s["motion"], "frames": FRAMES, "fps": FPS,
                                                 "width": W, "height": H, "steps": spec.get("steps", 50),
                                                 "generate_seconds": times[-1]}, indent=1))
        print("clip", s["id"], times[-1], "s", flush=True)
    return {"clips_made": len(todo), "clip_seconds": times,
            "clips_peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)}


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    report = {"episode": spec["id"], **stills(spec, out), **clips(spec, out)}
    (out / "gpu_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
