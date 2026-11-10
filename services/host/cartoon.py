"""Cel-shade a cutout photo into a flat-colour, ink-edged illustration.

    python -m services.host.cartoon assets/images/host_photo.png assets/images/host.png [--levels 10] [--edge 9] [--sat 1.25]

Steps: edge-preserving smoothing (repeated bilateral filter), colour
quantisation with k-means (flat cel bands), ink edges from an adaptive
threshold on the smoothed luminance, a touch of saturation, and the source
alpha kept so the figure still sits on the reel background.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def cel_shade(rgba: np.ndarray, levels: int = 18, edge_block: int = 11, edge_strength: float = 0.8, saturation: float = 1.22, smooth_passes: int = 5, mix: float = 0.6, gamma: float = 0.92) -> np.ndarray:
    """rgba: HxWx4 uint8 -> HxWx4 uint8 cel-shaded with the same alpha."""
    rgb = rgba[:, :, :3].copy()
    alpha = rgba[:, :, 3]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # 1. smooth while keeping edges (downscale for speed, upscale back)
    h, w = bgr.shape[:2]
    small = cv2.resize(bgr, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    for _ in range(smooth_passes):
        small = cv2.bilateralFilter(small, d=9, sigmaColor=28, sigmaSpace=7)
    smooth = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    # 2. flat colour bands: k-means over the visible pixels only
    mask = alpha > 8
    samples = smooth[mask].reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(7)
    subset = samples[rng.choice(len(samples), size=min(60000, len(samples)), replace=False)]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, _, centers = cv2.kmeans(subset, levels, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    flat_pixels = smooth.reshape(-1, 3).astype(np.float32)
    dists = ((flat_pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    quant = centers[dists.argmin(axis=1)].reshape(h, w, 3).astype(np.uint8)
    # soften band edges and keep some of the smooth gradient underneath so the
    # shading reads as cel lighting, not a posterised JPEG
    quant = cv2.bilateralFilter(quant, d=5, sigmaColor=12, sigmaSpace=3)
    quant = (quant.astype(np.float32) * mix + smooth.astype(np.float32) * (1 - mix)).astype(np.uint8)

    # 3. ink edges from the smoothed luminance
    gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, edge_block, 6)
    edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ink = 1.0 - (1.0 - edges.astype(np.float32) / 255.0) * edge_strength
    out = (quant.astype(np.float32) * ink[:, :, None]).clip(0, 255).astype(np.uint8)

    # 4. saturation and a mid-tone lift
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = (hsv[:, :, 1] * saturation).clip(0, 255)
    hsv[:, :, 2] = (255.0 * (hsv[:, :, 2] / 255.0) ** gamma).clip(0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 5. outline the silhouette with a thin dark line (cel-style contour)
    contour = cv2.morphologyEx((alpha > 128).astype(np.uint8) * 255, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8))
    out[contour > 0] = (out[contour > 0] * 0.35).astype(np.uint8)

    result = np.dstack([cv2.cvtColor(out, cv2.COLOR_BGR2RGB), alpha])
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--levels", type=int, default=18)
    ap.add_argument("--edge", type=int, default=11, help="adaptive threshold block size (odd)")
    ap.add_argument("--edge-strength", type=float, default=0.8)
    ap.add_argument("--sat", type=float, default=1.22)
    ap.add_argument("--passes", type=int, default=5)
    ap.add_argument("--mix", type=float, default=0.6, help="flat bands vs smooth gradient, 1 = fully flat")
    ap.add_argument("--gamma", type=float, default=0.92)
    args = ap.parse_args(argv)
    rgba = cv2.cvtColor(cv2.imread(args.src, cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    if rgba.shape[2] != 4:
        raise SystemExit("source must be an RGBA cutout (run rembg first)")
    out = cel_shade(rgba, args.levels, args.edge | 1, args.edge_strength, args.sat, args.passes, args.mix, args.gamma)
    cv2.imwrite(args.dst, cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA))
    print("wrote", args.dst, out.shape)
    return 0


if __name__ == "__main__":
    sys.exit(main())
