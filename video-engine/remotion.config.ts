/**
 * REELFORGE Remotion configuration.
 * Node API renders (services/rendering) pass options explicitly; this file
 * applies to `npx remotion` CLI usage.
 */
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
// WebGL effects and Three.js need a real GL backend in headless Chrome.
Config.setChromiumOpenGlRenderer("angle");
// RAM on the local machine is the binding constraint: keep tabs low by default.
Config.setConcurrency(2);
