/**
 * Looks for the epic-story cast, keyed by model file name (public/models/<name>.vrm).
 * The textures (skin, hair, clothes) are baked into each model by
 * services/host/epic_cast.py; this file adds what textures cannot: crowns,
 * feathers, jewellery, halos, and each character's size. Keep the names in
 * step with CAST in that Python file.
 *
 * These are our own stylised designs for public-domain characters. Do not
 * model them on any film, TV, game or comic version.
 */
export type PropSpec =
  | { kind: "crown"; color?: string; gem?: string; tall?: boolean }
  | { kind: "feather" }
  | { kind: "topknot"; color?: string; band?: string }
  | { kind: "earrings"; color?: string; size?: number }
  | { kind: "headband"; color?: string; gem?: string }
  | { kind: "tilak"; color?: string; shape?: "line" | "dot" }
  | { kind: "halo"; color?: string };

export type CharacterLook = { props: PropSpec[]; scale?: number };

const GOLD = "#FFC83D";

export const EPIC_CAST: Record<string, CharacterLook> = {
  narada: { props: [{ kind: "topknot", color: "#1A1820", band: GOLD }, { kind: "tilak", color: "#FFFFFF" }, { kind: "earrings" }] },
  drona: { props: [{ kind: "topknot", color: "#D6D6DC", band: "#B5651D" }, { kind: "tilak", color: "#E63946" }] },
  arjuna: { props: [{ kind: "crown", gem: "#4CC9F0" }, { kind: "earrings" }] },
  krishna: { props: [{ kind: "crown", gem: "#E63946" }, { kind: "feather" }, { kind: "tilak", color: "#FFD166" }, { kind: "earrings" }, { kind: "halo" }] },
  karna: { props: [{ kind: "earrings", size: 1.7 }, { kind: "headband", color: "#E07A1F" }, { kind: "tilak", color: "#E63946" }] },
  bhima: { props: [{ kind: "headband", color: "#B5651D" }], scale: 1.12 },
  yudhishthira: { props: [{ kind: "crown", gem: "#F5F5F5" }, { kind: "tilak", color: "#E63946" }] },
  abhimanyu: { props: [{ kind: "headband", color: GOLD, gem: "#E63946" }] },
  ashwatthama: { props: [{ kind: "headband", color: "#3A3A52", gem: "#7DF9FF" }] },
  rama: { props: [{ kind: "crown", gem: "#3DDC97" }, { kind: "tilak", color: "#E63946" }, { kind: "earrings" }, { kind: "halo" }] },
  lakshmana: { props: [{ kind: "headband", color: GOLD }, { kind: "tilak", color: "#E63946" }] },
  ravana: { props: [{ kind: "crown", color: "#C9972B", gem: "#E63946", tall: true }, { kind: "earrings", size: 1.4 }], scale: 1.1 },
  parashurama: { props: [{ kind: "topknot", color: "#46281A", band: "#B5651D" }, { kind: "tilak", color: "#FFFFFF" }] },
  draupadi: { props: [{ kind: "tilak", color: "#E63946", shape: "dot" }, { kind: "earrings", size: 1.3 }, { kind: "headband", color: GOLD, gem: "#E63946" }] },
  durga: { props: [{ kind: "crown", gem: "#E63946", tall: true }, { kind: "tilak", color: "#E63946", shape: "dot" }, { kind: "earrings", size: 1.3 }, { kind: "halo" }] },
  kali: { props: [{ kind: "crown", color: "#B8860B", gem: "#E63946" }, { kind: "tilak", color: "#E63946", shape: "dot" }, { kind: "halo", color: "#E63946" }] },
};

export const lookFor = (modelUrl: string): CharacterLook | null => {
  const name = modelUrl.split("/").pop()?.replace(/\.vrm$/i, "") ?? "";
  return EPIC_CAST[name] ?? null;
};

/** Named faces. Values are weights for the avatar's own face shapes (brow / eye / mouth), 0..1. */
export const EMOTES: Record<string, Record<string, number>> = {
  shock: { ALL_Surprised: 1 },
  awe: { BRW_Surprised: 1, EYE_Surprised: 0.7, MTH_Surprised: 0.5 },
  rage: { BRW_Angry: 1, EYE_Angry: 1, MTH_Angry: 1 },
  stern: { BRW_Angry: 0.9, EYE_Angry: 0.55, MTH_Down: 0.7 },
  focus: { BRW_Angry: 0.7, EYE_Angry: 0.35, MTH_Down: 0.25 },
  grin: { BRW_Joy: 1, EYE_Joy: 1, MTH_Joy: 1 },
  smirk: { BRW_Fun: 0.8, MTH_Fun: 1, EYE_Joy_R: 0.9 },
  calm: { BRW_Fun: 0.3, EYE_Joy: 0.25, MTH_Up: 0.6 },
  sad: { BRW_Sorrow: 1, EYE_Sorrow: 1, MTH_Sorrow: 1 },
  worried: { BRW_Sorrow: 0.9, EYE_Surprised: 0.4, MTH_Down: 0.5 },
};

export type Gesture = "idle" | "raise" | "point" | "bow" | "open";
