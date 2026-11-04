/**
 * Local OFL fonts, loaded from public/fonts so renders work offline (Ada
 * compute nodes may not have internet). Variable TTFs carry weights 100-900.
 */
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";
import { fonts } from "./tokens";

let loaded: Promise<void> | null = null;

export const loadAllFonts = (): Promise<void> => {
  if (loaded) {
    return loaded;
  }
  loaded = Promise.all([
    loadFont({
      family: fonts.display,
      url: staticFile("fonts/SpaceGrotesk-Variable.ttf"),
      weight: "300 700",
    }),
    loadFont({
      family: fonts.body,
      url: staticFile("fonts/Inter-Variable.ttf"),
      weight: "100 900",
    }),
    loadFont({
      family: fonts.mono,
      url: staticFile("fonts/JetBrainsMono-Variable.ttf"),
      weight: "100 800",
    }),
  ]).then(() => undefined);
  return loaded;
};

// Kick off loading as soon as the bundle is evaluated.
loadAllFonts();
