/**
 * REELFORGE design tokens.
 * Single source of truth for colour, type, spacing and safe zones.
 * Never inline a hex colour or font name inside a scene component.
 */

export type StyleId = "cinematic" | "explainer" | "experimental";

export type Palette = {
  bg: string;
  bgAlt: string;
  surface: string;
  hero: string; // the ONE hero colour, at most one glowing element per frame
  accent: string;
  accent2: string;
  text: string;
  textDim: string;
  textMuted: string;
  glow: string;
  line: string;
  success: string;
  warn: string;
};

export const palettes: Record<StyleId, Palette> = {
  // STYLE A: deep blue and violet cinematic
  cinematic: {
    bg: "#05060D",
    bgAlt: "#0B0E1C",
    surface: "#121632",
    hero: "#7C5CFF",
    accent: "#4CC9F0",
    accent2: "#F72585",
    text: "#F5F6FF",
    textDim: "#B4B8D6",
    textMuted: "#6F749A",
    glow: "rgba(124, 92, 255, 0.45)",
    line: "rgba(180, 184, 214, 0.16)",
    success: "#3DDC97",
    warn: "#FFB84C",
  },
  // STYLE B: explainer, slightly brighter surfaces for diagrams
  explainer: {
    bg: "#070A12",
    bgAlt: "#0D1220",
    surface: "#151C2E",
    hero: "#4CC9F0",
    accent: "#7C5CFF",
    accent2: "#3DDC97",
    text: "#F3F6FA",
    textDim: "#AEB8CC",
    textMuted: "#66708A",
    glow: "rgba(76, 201, 240, 0.40)",
    line: "rgba(174, 184, 204, 0.18)",
    success: "#3DDC97",
    warn: "#FFB84C",
  },
  // STYLE C placeholder: generative, higher contrast
  experimental: {
    bg: "#030304",
    bgAlt: "#0A0A0D",
    surface: "#131318",
    hero: "#E4FF3B",
    accent: "#FF4D6D",
    accent2: "#4CC9F0",
    text: "#FAFAFA",
    textDim: "#B8B8C0",
    textMuted: "#6E6E78",
    glow: "rgba(228, 255, 59, 0.35)",
    line: "rgba(184, 184, 192, 0.16)",
    success: "#3DDC97",
    warn: "#FFB84C",
  },
};

export const fonts = {
  display: "Space Grotesk",
  body: "Inter",
  mono: "JetBrains Mono",
} as const;

/** Type scale for a 1080 wide frame. Scale with width / 1080 for other sizes. */
export const type = {
  hero: 128,
  h1: 96,
  h2: 72,
  h3: 56,
  body: 44,
  caption: 54,
  small: 34,
  micro: 26,
  mono: 36,
  trackingTight: "-0.03em",
  trackingNormal: "-0.01em",
  trackingWide: "0.08em",
  lineTight: 1.02,
  lineNormal: 1.2,
} as const;

export const spacing = {
  xs: 8,
  sm: 16,
  md: 24,
  lg: 40,
  xl: 64,
  xxl: 96,
} as const;

export const radius = {
  sm: 12,
  md: 20,
  lg: 32,
  pill: 999,
} as const;

/**
 * 9:16 safe zone for Instagram Reels at 1080 x 1920.
 * Platform UI covers the bottom ~500px and the right ~120px.
 * Critical text stays inside this box.
 */
export const safeZone = {
  top: 360,
  bottom: 1420,
  left: 80,
  right: 960,
  captionY: 1240, // caption block baseline area (inside the zone, above UI)
} as const;

export const video = {
  width: 1080,
  height: 1920,
  fps: 30,
} as const;

export const quality = {
  draft: { width: 720, height: 1280, particleScale: 0.35, threeDetail: 0.5 },
  standard: { width: 1080, height: 1920, particleScale: 1, threeDetail: 1 },
  cinematic: { width: 1080, height: 1920, particleScale: 1.6, threeDetail: 1.5 },
} as const;

export type QualityProfile = keyof typeof quality;
