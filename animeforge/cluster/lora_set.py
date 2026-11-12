"""Candidate training pictures for a character LoRA.

Draws the character in many framings, angles, moods and places, held to the
reference by IP-Adapter Plus, then scores each picture against the reference.
A person then picks the ones that show the same face and costume
(`selected.txt`); only those are trained on. Every picture comes from our own
prompts and a cleared model, which is the condition on LoRA training.

    python -m animeforge.cluster.lora_set --spec episode.json --reference ref.png --out DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from animeforge.cluster.gen_still import NEG

QUALITY = "anime coloring, masterpiece, high score, great score, absurdres"
# (name, tags, width, height): what changes from picture to picture. The caption
# keeps only these tags, so the LoRA ties everything else to the trigger word.
VARIATIONS = [
    ("portrait-front", "portrait, looking at viewer, white background, simple background", 1024, 1024),
    ("portrait-side", "portrait, from side, profile, white background, simple background", 1024, 1024),
    ("portrait-34", "portrait, three-quarter view, looking away, grey background, simple background", 1024, 1024),
    ("closeup-smile", "close-up, face focus, gentle smile, looking at viewer, forest background", 1024, 1024),
    ("closeup-serious", "close-up, face focus, serious, narrowed eyes, night, oil lamp light", 1024, 1024),
    ("upper-forest", "upper body, looking at viewer, forest, morning light", 768, 1344),
    ("upper-palace", "upper body, arms crossed, palace hall, pillars, daylight", 768, 1344),
    ("upper-bow", "upper body, holding a longbow, looking to the side, hermitage courtyard", 768, 1344),
    ("upper-shout", "upper body, open mouth, shouting, battlefield, dust, sunset", 768, 1344),
    ("cowboy-walk", "cowboy shot, walking, forest path, dappled light", 768, 1344),
    ("cowboy-aim", "cowboy shot, drawing a longbow, aiming, from side, forest", 768, 1344),
    ("full-stand", "full body, standing, white background, simple background", 768, 1344),
    ("full-river", "full body, standing on a riverbank, sunrise, wind", 768, 1344),
    ("sitting", "sitting cross-legged, calm, eyes closed, under a tree, upper body", 768, 1344),
    ("from-below", "from below, upper body, looking down at viewer, blue sky, clouds", 768, 1344),
    ("back-glance", "from behind, looking back over shoulder, upper body, evening sky", 768, 1344),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="episode file whose character is trained")
    ap.add_argument("--reference", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per", type=int, default=4, help="pictures per variation")
    ap.add_argument("--scale", type=float, default=0.45)
    ap.add_argument("--seed", type=int, default=9000)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "candidates").mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    tags = spec["character"]["tags"]

    import torch
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline
    from PIL import Image
    from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

    ref = Image.open(a.reference).convert("RGB")
    encoder = CLIPVisionModelWithProjection.from_pretrained(
        "h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        spec.get("still_model", "cagliostrolab/animagine-xl-4.0"), image_encoder=encoder,
        torch_dtype=torch.float16, use_safetensors=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    pipe.to("cuda")
    pipe.set_ip_adapter_scale(a.scale)

    rows = []
    for vi, (name, vtags, w, h) in enumerate(VARIATIONS):
        for k in range(a.per):
            seed = a.seed + vi * 10 + k
            img = pipe(prompt=f"{tags}, {vtags}, {QUALITY}", negative_prompt=NEG, ip_adapter_image=ref,
                       width=w, height=h, num_inference_steps=28, guidance_scale=5.0,
                       generator=torch.Generator("cuda").manual_seed(seed)).images[0]
            f = f"{len(rows):03d}-{name}.png"
            img.save(out / "candidates" / f)
            rows.append({"n": len(rows), "file": f, "variation": name, "tags": vtags, "seed": seed})
    del pipe
    torch.cuda.empty_cache()

    encoder.to("cuda")
    proc = CLIPImageProcessor()

    def embed(img):
        x = proc(images=img, return_tensors="pt")["pixel_values"].to("cuda", torch.float16)
        return torch.nn.functional.normalize(encoder(pixel_values=x).image_embeds, dim=-1)

    with torch.no_grad():
        e_ref = embed(ref)
        for r in rows:
            r["similarity"] = round(float((embed(Image.open(out / "candidates" / r["file"]).convert("RGB")) * e_ref).sum()), 4)

    # Contact sheets of 16 (one variation per row), numbered, for the person choosing.
    from PIL import ImageDraw
    cell = 256
    for page in range(0, len(rows), 16):
        chunk = rows[page:page + 16]
        sheet = Image.new("RGB", (cell * 4, cell * 4), "black")
        for i, r in enumerate(chunk):
            im = Image.open(out / "candidates" / r["file"]).convert("RGB")
            im.thumbnail((cell, cell))
            x, y = (i % 4) * cell, (i // 4) * cell
            sheet.paste(im, (x + (cell - im.width) // 2, y))
            ImageDraw.Draw(sheet).text((x + 4, y + 4), f"{r['n']} {r['similarity']:.2f}", fill="yellow")
        sheet.save(out / f"sheet-{page // 16}.jpg", quality=85)

    (out / "candidates.json").write_text(json.dumps(
        {"character": spec["character"]["id"], "tags": tags, "reference": a.reference,
         "adapter_scale": a.scale, "pictures": rows}, indent=1))
    print(len(rows), "candidates; mean similarity", round(sum(r["similarity"] for r in rows) / len(rows), 4))


if __name__ == "__main__":
    main()
