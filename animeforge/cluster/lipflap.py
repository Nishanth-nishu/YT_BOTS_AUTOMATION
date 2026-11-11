"""Phase 5 prototype: audio-timed anime lip flaps with no face model.

LatentSync needs InsightFace (non-commercial) and MuseTalk needs face-parsing
weights with no stated licence, so neither may be used here. Limited anime has
always done speech with a few mouth drawings switched in time with the voice,
and that can be built from cleared parts only:

1. Draw a close-up of the character (SDXL).
2. Redraw it twice at low strength with the same seed, once "closed mouth" and
   once "open mouth". The two differ almost only at the mouth.
3. Find the mouth as the place where the two differ most, and feather a mask
   around it. Everything outside the mask comes from the closed drawing, so
   nothing else shimmers.
4. Open the mouth by the loudness of the voice, held on twos (12 changes a
   second), with a slow push-in so the frame is not frozen.

    python -m animeforge.cluster.lipflap --prompt TAGS --voice line.wav --out DIR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

from animeforge.cluster.gen_still import NEG

FPS = 24
W, H = 704, 1280


def envelope(path: Path, fps: int = FPS) -> list[float]:
    """Loudness per video frame, 0..1."""
    import numpy as np

    with wave.open(str(path), "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype={1: np.uint8, 2: np.int16, 4: np.int32}[sw]).astype(np.float32)
    a = a.reshape(-1, ch).mean(axis=1)
    a /= float(np.abs(a).max() or 1.0)
    hop = sr / fps
    out = []
    for i in range(int(len(a) / hop) + 1):
        seg = a[int(i * hop): int((i + 1) * hop)]
        out.append(float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0)
    top = sorted(out)[int(len(out) * 0.95)] or 1.0
    return [min(1.0, v / top) for v in out]


def openness(env: list[float], quiet: float = 0.12, wide: float = 0.5) -> list[float]:
    """Three mouth positions, held on twos: 0 closed, 0.5 half, 1 open."""
    out = []
    for i in range(0, len(env), 2):
        v = max(env[i:i + 2])
        level = 0.0 if v < quiet else (0.5 if v < wide else 1.0)
        out += [level] * len(env[i:i + 2])
    return out


def mouth_mask(closed, opened):
    """Feathered mask around where the two drawings differ most; also how much of the change it holds."""
    import numpy as np
    from PIL import Image, ImageFilter

    a = np.asarray(closed, dtype=np.float32)
    b = np.asarray(opened, dtype=np.float32)
    diff = np.abs(a - b).mean(axis=2)
    blur = np.asarray(Image.fromarray(np.clip(diff, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)),
                      dtype=np.float32)
    y, x = np.unravel_index(int(blur.argmax()), blur.shape)
    h, w = blur.shape
    rx, ry = int(w * 0.11), int(h * 0.05)
    box = (max(0, x - rx), max(0, y - ry), min(w, x + rx), min(h, y + ry))
    m = np.zeros_like(blur)
    m[box[1]:box[3], box[0]:box[2]] = 1.0
    mask = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)),
                      dtype=np.float32) / 255.0
    inside = float((diff * (m > 0)).sum() / max(1.0, diff.sum()))
    return mask, {"centre": [int(x), int(y)], "box": list(map(int, box)), "share_of_change_inside": round(inside, 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="character tags for the close-up")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="cagliostrolab/animagine-xl-4.0")
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--strength", type=float, default=0.32)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    import imageio_ffmpeg
    import numpy as np
    import torch
    from diffusers import (EulerAncestralDiscreteScheduler, StableDiffusionXLImg2ImgPipeline,
                           StableDiffusionXLPipeline)
    from PIL import Image

    from animeforge.cluster.gen_shot import fit

    quality = "anime coloring, masterpiece, high score, great score, absurdres"
    pipe = StableDiffusionXLPipeline.from_pretrained(a.repo, torch_dtype=torch.float16, use_safetensors=True)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda")
    g = lambda: torch.Generator("cuda").manual_seed(a.seed)  # noqa: E731
    base = pipe(prompt=f"{a.prompt}, portrait, face focus, looking at viewer, closed mouth, {quality}",
                negative_prompt=NEG, width=768, height=1344, num_inference_steps=28, guidance_scale=5.0,
                generator=g()).images[0]
    base.save(out / "base.png")
    i2i = StableDiffusionXLImg2ImgPipeline(**pipe.components)
    variants = {}
    for name, mouth in (("closed", "closed mouth"), ("open", "open mouth, talking, :o")):
        variants[name] = i2i(prompt=f"{a.prompt}, portrait, face focus, looking at viewer, {mouth}, {quality}",
                             negative_prompt=NEG, image=base, strength=a.strength, num_inference_steps=40,
                             guidance_scale=5.0, generator=g()).images[0]
        variants[name].save(out / f"{name}.png")
    del pipe, i2i
    torch.cuda.empty_cache()

    closed, opened = fit(variants["closed"], W, H), fit(variants["open"], W, H)
    mask, info = mouth_mask(closed, opened)
    Image.fromarray((mask * 255).astype(np.uint8)).save(out / "mask.png")
    c, o, m3 = np.asarray(closed, np.float32), np.asarray(opened, np.float32), mask[..., None]

    env = envelope(Path(a.voice))
    lead = int(0.3 * FPS)
    levels = [0.0] * lead + openness(env) + [0.0] * int(0.4 * FPS)
    silent = out / "silent.mp4"
    writer = imageio_ffmpeg.write_frames(str(silent), (W, H), fps=FPS, codec="libx264", quality=8,
                                         pix_fmt_out="yuv420p", macro_block_size=None)
    writer.send(None)
    n = len(levels)
    for k, lv in enumerate(levels):
        frame = Image.fromarray(np.clip(c * (1 - m3 * lv) + o * (m3 * lv), 0, 255).astype(np.uint8))
        z = 1.0 + 0.05 * k / max(1, n - 1)                       # slow push-in
        cw, chh = W / z, H / z
        left, top = (W - cw) / 2, (H - chh) * 0.4
        frame = frame.resize((W, H), Image.LANCZOS, box=(left, top, left + cw, top + chh))
        writer.send(np.asarray(frame).tobytes())
    writer.close()

    final = out / "talking.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", str(silent), "-itsoffset", "0.3",
                    "-i", a.voice, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", str(final)], check=True)

    e = np.array([0.0] * lead + env + [0.0] * int(0.4 * FPS))[:n]
    lv = np.array(levels[:len(e)])
    corr = float(np.corrcoef(e, lv)[0, 1]) if e.std() > 0 and lv.std() > 0 else 0.0
    report = {"method": "lip flaps from two redraws, mouth found by difference; no face model",
              "model": a.repo, "frames": n, "seconds": round(n / FPS, 2), "mask": info,
              "mouth_changes": int((np.diff(lv) != 0).sum()),
              "share_of_frames_open": round(float((lv > 0).mean()), 3),
              "loudness_to_mouth_correlation": round(corr, 3),
              "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
