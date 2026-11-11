"""Phase 3: does a reference image keep a character the same across new scenes?

For each scene prompt it renders the character twice with the same seed: once
from the text alone, once with IP-Adapter Plus fed the reference still. It then
scores every image against the reference with CLIP image similarity and writes
a contact sheet (top row text only, bottom row with the reference) and a report.

    python -m animeforge.cluster.consistency --reference ref.png --character "..." --out DIR
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from animeforge.cluster.gen_still import NEG

SCENES = [
    ("battlefield", "standing on a battlefield at sunset, wind, dust, full body, bow held at side"),
    ("kneeling", "kneeling with joined palms before a teacher, hermitage courtyard, side view"),
    ("closeup", "close-up portrait, calm focused expression, looking at viewer, night, oil lamp light"),
    ("aiming", "drawing a longbow and aiming upward, dynamic angle from below, forest canopy"),
    ("chariot", "riding a war chariot, white horses, banners, motion, upper body"),
    ("smiling", "laughing warmly, palace garden, daylight, cowboy shot"),
]
QUALITY = "anime coloring, masterpiece, high score, great score, absurdres"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--character", required=True, help="the character's fixed description tags")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="cagliostrolab/animagine-xl-4.0")
    ap.add_argument("--scale", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=101)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    import torch
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline
    from PIL import Image
    from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

    ref = Image.open(a.reference).convert("RGB")
    encoder = CLIPVisionModelWithProjection.from_pretrained(
        "h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        a.repo, image_encoder=encoder, torch_dtype=torch.float16, use_safetensors=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.to("cuda")

    rows, t0 = [], time.time()
    torch.cuda.reset_peak_memory_stats()
    for i, (name, scene) in enumerate(SCENES):
        prompt = f"1boy, solo, original, {a.character}, {scene}, {QUALITY}"
        for mode, scale in (("text", 0.0), ("ref", a.scale)):
            pipe.set_ip_adapter_scale(scale)
            img = pipe(prompt=prompt, negative_prompt=NEG, ip_adapter_image=ref,
                       width=768, height=1344, num_inference_steps=28, guidance_scale=5.0,
                       generator=torch.Generator("cuda").manual_seed(a.seed + i)).images[0]
            f = out / f"{name}-{mode}.png"
            img.save(f)
            rows.append({"scene": name, "mode": mode, "file": f.name, "prompt": prompt})
    gen_s, peak = time.time() - t0, torch.cuda.max_memory_allocated() / 2**30
    del pipe
    torch.cuda.empty_cache()

    # Scored with the adapter's own image encoder (OpenCLIP ViT-H, in the
    # Apache-2.0 h94/IP-Adapter repository), so no extra model is needed.
    clip_id = "h94/IP-Adapter models/image_encoder (ViT-H)"
    encoder.to("cuda")
    proc = CLIPImageProcessor()

    def embed(img):
        x = proc(images=img, return_tensors="pt")["pixel_values"].to("cuda", torch.float16)
        return torch.nn.functional.normalize(encoder(pixel_values=x).image_embeds, dim=-1)

    with torch.no_grad():
        e_ref = embed(ref)
        for r in rows:
            r["similarity"] = round(float((embed(Image.open(out / r["file"]).convert("RGB")) * e_ref).sum()), 4)

    def mean(mode):
        v = [r["similarity"] for r in rows if r["mode"] == mode]
        return round(sum(v) / len(v), 4)

    w, h = 256, 448
    sheet = Image.new("RGB", (w * (len(SCENES) + 1), h * 2), "black")
    small = ref.resize((w, h))
    sheet.paste(small, (0, 0))
    sheet.paste(small, (0, h))
    for i, (name, _) in enumerate(SCENES):
        sheet.paste(Image.open(out / f"{name}-text.png").resize((w, h)), (w * (i + 1), 0))
        sheet.paste(Image.open(out / f"{name}-ref.png").resize((w, h)), (w * (i + 1), h))
    sheet.save(out / "contact_sheet.jpg", quality=88)

    report = {"reference": a.reference, "character": a.character, "model": a.repo,
              "adapter": "h94/IP-Adapter ip-adapter-plus_sdxl_vit-h", "adapter_scale": a.scale,
              "metric": f"cosine similarity of {clip_id} image embeddings to the reference",
              "mean_similarity_text_only": mean("text"), "mean_similarity_with_reference": mean("ref"),
              "seconds_for_12_images": round(gen_s, 1), "peak_vram_gb": round(peak, 2),
              "gpu": torch.cuda.get_device_name(0), "images": rows}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "images"}, indent=1))


if __name__ == "__main__":
    main()
