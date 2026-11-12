"""Does the character LoRA hold the character better than what we had?

Six scenes, same seeds, four ways: text only, IP-Adapter alone (the old
method), LoRA alone, LoRA with a light IP-Adapter. Each picture is scored
against the reference and against the other five of its way, and a contact
sheet is written (one row per way).

    python -m animeforge.cluster.lora_eval --spec ep.json --reference ref.png --lora DIR/name.safetensors --trigger word --out DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from animeforge.cluster.consistency import QUALITY, SCENES
from animeforge.cluster.gen_still import NEG


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--lora", required=True)
    ap.add_argument("--trigger", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lora-scale", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=101)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
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
    lora = Path(a.lora)
    pipe.load_lora_weights(str(lora.parent), weight_name=lora.name, adapter_name="character")
    pipe.to("cuda")

    # (name, LoRA weight, IP-Adapter scale, prompt uses the trigger word)
    ways = [("text", 0.0, 0.0, False), ("adapter", 0.0, 0.45, False),
            ("lora", a.lora_scale, 0.0, True), ("lora+adapter", a.lora_scale, 0.3, True)]
    rows = []
    for way, lw, ip, trig in ways:
        pipe.set_adapters(["character"], adapter_weights=[lw])
        pipe.set_ip_adapter_scale(ip)
        for i, (name, scene) in enumerate(SCENES):
            prompt = f"{a.trigger + ', ' if trig else ''}{tags}, {scene}, {QUALITY}"
            img = pipe(prompt=prompt, negative_prompt=NEG, ip_adapter_image=ref, width=768, height=1344,
                       num_inference_steps=28, guidance_scale=5.0,
                       generator=torch.Generator("cuda").manual_seed(a.seed + i)).images[0]
            f = f"{name}-{way}.png"
            img.save(out / f)
            rows.append({"scene": name, "way": way, "file": f})
    del pipe
    torch.cuda.empty_cache()

    encoder.to("cuda")
    proc = CLIPImageProcessor()

    def embed(img):
        x = proc(images=img, return_tensors="pt")["pixel_values"].to("cuda", torch.float16)
        return torch.nn.functional.normalize(encoder(pixel_values=x).image_embeds, dim=-1)

    with torch.no_grad():
        e_ref = embed(ref)
        embs = {}
        for r in rows:
            e = embed(Image.open(out / r["file"]).convert("RGB"))
            embs[r["file"]] = e
            r["similarity"] = round(float((e * e_ref).sum()), 4)
        # How alike the six pictures of one way are to each other: what matters from shot to shot.
        among = {}
        for way, *_ in ways:
            es = [embs[r["file"]] for r in rows if r["way"] == way]
            pairs = [float((es[i] * es[j]).sum()) for i in range(len(es)) for j in range(i + 1, len(es))]
            among[way] = round(sum(pairs) / len(pairs), 4)

    w, h = 256, 448
    sheet = Image.new("RGB", (w * (len(SCENES) + 1), h * len(ways)), "black")
    for y, (way, *_) in enumerate(ways):
        sheet.paste(ref.resize((w, h)), (0, y * h))
        for i, (name, _) in enumerate(SCENES):
            sheet.paste(Image.open(out / f"{name}-{way}.png").resize((w, h)), (w * (i + 1), y * h))
    sheet.save(out / "contact_sheet.jpg", quality=88)

    def mean(way):
        v = [r["similarity"] for r in rows if r["way"] == way]
        return round(sum(v) / len(v), 4)

    report = {"lora": lora.name, "lora_scale": a.lora_scale, "trigger": a.trigger,
              "metric": "cosine similarity of ViT-H image embeddings (h94/IP-Adapter image encoder)",
              "to_reference": {way: mean(way) for way, *_ in ways}, "among_themselves": among,
              "rows_of_sheet": [x[0] for x in ways], "gpu": torch.cuda.get_device_name(0), "images": rows}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "images"}, indent=1))


if __name__ == "__main__":
    main()
