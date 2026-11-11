/**
 * VrmHost: a prebuilt anime character (VRM avatar) as the host. The model's
 * own rig does the work: VRM expressions for lip-sync (aa / ih / ou) and
 * blinks, humanoid bones for head sway, breathing and arm poses.
 * Everything is a pure function of the frame; spring-bone physics is left
 * off so parallel frame rendering stays deterministic.
 *
 * On top of the model:
 *   - props (crown, feather, jewellery, halo) from design/epicCast.ts, built
 *     from simple shapes and attached to the head bone;
 *   - emotes: named faces that drive the avatar's separate brow, eye and
 *     mouth shapes directly, far stronger than the four VRM presets;
 *   - gestures: arm and spine poses blended in from the idle pose.
 *
 * Loading goes through React Suspense (useLoader) because Remotion's
 * ThreeCanvas only advances the scene when the frame changes or when the
 * canvas is created; a model that arrives later would never be drawn.
 *
 * Models: video-engine/public/models/*.vrm (VRoid Project samples, CC0;
 * see assets/models/LICENSE.txt). Any VRM 0.x or 1.0 file works.
 */
import React, { useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader, type GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { staticFile, useVideoConfig } from "remotion";
import { EMOTES, lookFor, type Costume, type Gesture, type PropSpec } from "../design/epicCast";
import { blinkAt, mouthAt } from "./Presenter";

export type VrmFraming = "bust" | "face" | "stage";

type Props = {
  modelUrl: string; // path under public/
  globalFrame: number;
  envelope: number[];
  expressions?: number[][];
  width: number;
  height: number;
  framing?: VrmFraming;
  mood?: "hype" | "calm";
  seed?: number;
  motion?: number;
  /** Turn the whole body (radians, + is towards the viewer's right). Used by the dialogue scene. */
  yaw?: number;
  /** false for a character who is listening: mouth stays shut whatever the envelope says. */
  speaking?: boolean;
  /** A named face from EMOTES and how strongly to show it (0..1). */
  emote?: string;
  emoteWeight?: number;
  /** An arm / body pose and how far into it (0..1). */
  gesture?: Gesture;
  gestureWeight?: number;
  /** Multiplies the tone-of-voice expression track. 1 = as authored. */
  expressiveness?: number;
};

const mat = (color: string) => new THREE.MeshBasicMaterial({ color, toneMapped: false, side: THREE.DoubleSide });

/** Build one prop. `f` is +1 or -1: which way the face points along the head bone's Z axis. */
const buildProp = (spec: PropSpec, f: number): THREE.Object3D => {
  const g = new THREE.Group();
  const gold = "#FFC83D";
  switch (spec.kind) {
    case "crown": {
      const color = spec.color ?? gold;
      const h = spec.tall ? 0.085 : 0.055;
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.098, 0.084, h, 28, 1, true), mat(color));
      band.position.y = 0.212 + h / 2;
      g.add(band);
      const spikes = spec.tall ? 9 : 7;
      for (let i = 0; i < spikes; i++) {
        const a = (i / spikes) * Math.PI * 2;
        const front = Math.cos(a) * f > 0.2;
        const spike = new THREE.Mesh(new THREE.ConeGeometry(0.014, front ? 0.085 : 0.05, 8), mat(color));
        spike.position.set(Math.sin(a) * 0.094, 0.212 + h + (front ? 0.04 : 0.022), Math.cos(a) * 0.094);
        g.add(spike);
      }
      const gem = new THREE.Mesh(new THREE.SphereGeometry(0.02, 12, 12), mat(spec.gem ?? "#E63946"));
      gem.position.set(0, 0.212 + h / 2, f * 0.094);
      g.add(gem);
      break;
    }
    case "feather": {
      const fg = new THREE.Group();
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.003, 0.004, 0.13, 6), mat("#E8E0B0"));
      stem.position.y = 0.065;
      fg.add(stem);
      const layers: [string, number, number][] = [["#1E8E5A", 0.05, 0.085], ["#12B5A6", 0.036, 0.062], ["#2742C7", 0.024, 0.04], ["#FFC83D", 0.012, 0.02]];
      layers.forEach(([c, rx, ry], i) => {
        const eye = new THREE.Mesh(new THREE.CircleGeometry(1, 24), mat(c));
        eye.scale.set(rx, ry, 1);
        eye.position.set(0, 0.15, f * (0.001 + i * 0.0012));
        fg.add(eye);
      });
      fg.position.set(0.05, 0.25, f * 0.02);
      fg.rotation.z = -0.32;
      g.add(fg);
      break;
    }
    case "topknot": {
      const bun = new THREE.Mesh(new THREE.SphereGeometry(0.052, 18, 14), mat(spec.color ?? "#1A1820"));
      bun.position.set(0, 0.245, -f * 0.01);
      g.add(bun);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.04, 0.008, 8, 24), mat(spec.band ?? gold));
      ring.position.set(0, 0.208, -f * 0.01);
      ring.rotation.x = Math.PI / 2;
      g.add(ring);
      break;
    }
    case "earrings": {
      const s = spec.size ?? 1;
      [-1, 1].forEach((side) => {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.016 * s, 0.005 * s, 8, 20), mat(spec.color ?? gold));
        ring.position.set(side * 0.098, 0.03 - 0.012 * s, f * 0.012);
        ring.rotation.y = Math.PI / 2;
        g.add(ring);
      });
      break;
    }
    case "headband": {
      const band = new THREE.Mesh(new THREE.TorusGeometry(0.132, 0.01, 8, 48), mat(spec.color ?? gold));
      band.position.y = 0.15;
      band.rotation.x = Math.PI / 2 + f * 0.16;
      g.add(band);
      if (spec.gem) {
        const gem = new THREE.Mesh(new THREE.SphereGeometry(0.016, 12, 12), mat(spec.gem));
        gem.position.set(0, 0.13, f * 0.132);
        g.add(gem);
      }
      break;
    }
    case "tilak": {
      const dot = spec.shape === "dot";
      const mark = new THREE.Mesh(new THREE.CircleGeometry(1, 16), mat(spec.color ?? "#E63946"));
      mark.scale.set(dot ? 0.011 : 0.006, dot ? 0.011 : 0.024, 1);
      mark.position.set(0, dot ? 0.118 : 0.128, f * 0.104);
      g.add(mark);
      break;
    }
    case "halo": {
      const color = spec.color ?? gold;
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.235, 0.25, 64), mat(color));
      ring.position.set(0, 0.1, -f * 0.16);
      g.add(ring);
      const glow = new THREE.Mesh(new THREE.CircleGeometry(0.235, 64), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.16, toneMapped: false, side: THREE.DoubleSide, depthWrite: false }));
      glow.position.copy(ring.position);
      g.add(glow);
      break;
    }
  }
  return g;
};

/** A ring around the body, wider than it is deep (shoulders are wider than the chest is thick). */
const bodyRing = (radius: number, tube: number, color: string, depth = 0.7) => {
  const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 10, 48), mat(color));
  ring.scale.set(1, depth, 1);
  ring.rotation.x = Math.PI / 2;
  return ring;
};

/** Hang a costume on the body bones. `f` is the facing sign (see buildProp); the left arm points along f * X. */
const dress = (vrm: VRM, costume: Costume, f: number, bulky: boolean) => {
  const bone = (name: string) => vrm.humanoid.getRawBoneNode(name as never);
  const chest = bone("upperChest") ?? bone("chest") ?? bone("spine");
  const neck = bone("neck");
  const hips = bone("hips");
  const main = costume.main ?? "#FFC83D";
  const trim = costume.trim ?? "#E63946";
  const pad = bulky ? 1.18 : 1; // a hoodie is thicker than a shirt
  const add = (to: THREE.Object3D | null, ...items: THREE.Object3D[]) => items.forEach((o) => to?.add(o));

  // necklace: a ring round the neck whose front hangs down on the chest
  const necklace = (radius: number, tilt: number, color: string, tube = 0.009, pendant?: string) => {
    const g = new THREE.Group();
    const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 10, 44), mat(color));
    ring.rotation.x = Math.PI / 2 + f * tilt;
    g.add(ring);
    if (pendant) {
      const gem = new THREE.Mesh(new THREE.SphereGeometry(tube * 2.4, 12, 12), mat(pendant));
      gem.position.set(0, -Math.sin(tilt) * radius, f * Math.cos(tilt) * radius);
      g.add(gem);
    }
    g.position.set(0, 0.0, f * 0.012);
    return g;
  };
  // sash: a loop from one shoulder to the opposite hip
  const sash = (color: string, tube: number) => {
    const g = new THREE.Group();
    g.add(bodyRing(0.2 * pad, tube, color, 0.66));
    g.rotation.z = 0.82;
    g.position.set(0, -0.03, f * 0.005);
    return g;
  };
  const armband = (side: number, color: string, at = 0.1) => {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.058 * pad, 0.011, 8, 28), mat(color));
    ring.rotation.y = Math.PI / 2;
    ring.position.x = side * f * at;
    return ring;
  };
  const belt = (color: string, gem: string) => {
    const g = new THREE.Group();
    g.add(bodyRing(0.155 * pad, 0.02, color, 0.72));
    const buckle = new THREE.Mesh(new THREE.SphereGeometry(0.03, 14, 14), mat(gem));
    buckle.position.set(0, 0, f * 0.155 * pad * 0.72);
    buckle.scale.set(1, 1, 0.5);
    g.add(buckle);
    g.position.y = 0.09;
    return g;
  };

  if (costume.kind === "sage") {
    // prayer beads: a ring of small spheres, and a cloth sash
    const beads = new THREE.Group();
    const n = 26;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.0125, 8, 8), mat(trim));
      b.position.set(Math.sin(a) * 0.105, 0, Math.cos(a) * 0.105);
      beads.add(b);
    }
    beads.rotation.x = f * 0.62;
    beads.position.set(0, -0.005, f * 0.012);
    add(neck, beads);
    add(chest, sash(main, 0.03));
    return;
  }
  [1, -1].forEach((side) => add(bone(side === 1 ? "leftUpperArm" : "rightUpperArm"), armband(side, main), ...(costume.kind === "armor" ? [armband(side, trim, 0.135)] : [])));
  add(hips, belt(main, trim));
  if (costume.kind === "royal") {
    add(neck, necklace(0.088, 0.5, main), necklace(0.118, 0.72, main, 0.008, trim));
    add(chest, sash(trim, 0.024));
    return;
  }
  // armor: banded cuirass (three metal bands round the chest), small shoulder guards, a boss and a collar.
  // Metal is lit (Lambert) so the bands and guards read as rounded forms, with some glow so it stays bright.
  const metal = (color: string) => new THREE.MeshLambertMaterial({ color, emissive: color, emissiveIntensity: 0.38, side: THREE.DoubleSide });
  [1, -1].forEach((side) => {
    const guard = new THREE.Mesh(new THREE.SphereGeometry(0.07 * pad, 20, 12, 0, Math.PI * 2, 0, Math.PI * 0.5), metal(main));
    guard.position.set(side * f * 0.035, 0.018, 0);
    guard.scale.set(1.25, 0.62, 1.1);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.07 * pad, 0.005, 8, 30), mat(trim));
    rim.rotation.x = Math.PI / 2;
    rim.position.set(side * f * 0.035, 0.018, 0);
    rim.scale.set(1.25, 1.1, 1);
    add(bone(side === 1 ? "leftUpperArm" : "rightUpperArm"), guard, rim);
  });
  [0.05, -0.005, -0.06].forEach((y, i) => {
    const band = new THREE.Mesh(new THREE.TorusGeometry((0.168 - i * 0.008) * pad, 0.03, 10, 48), metal(main));
    band.scale.set(1, 0.68, 0.5); // flattened: a plate, not a tube
    band.rotation.x = Math.PI / 2;
    band.position.set(0, y, f * 0.004);
    const line = bodyRing((0.17 - i * 0.008) * pad, 0.004, trim, 0.7);
    line.position.set(0, y - 0.027, f * 0.004);
    add(chest, band, line);
  });
  const boss = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 16), mat(trim));
  boss.scale.set(1, 1, 0.5);
  boss.position.set(0, 0.03, f * 0.168 * pad * 0.68);
  add(chest, boss);
  add(neck, necklace(0.08, 0.3, main, 0.012));
};

/** Prepare a freshly loaded VRM once (useLoader caches the gltf per url). */
const prepare = (gltf: GLTF, modelUrl: string): VRM => {
  const vrm = gltf.userData.vrm as VRM;
  if (!vrm.scene.userData.__prepared) {
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.rotateVRM0(vrm); // 0.x models face -Z; turn them to +Z like 1.0
    vrm.scene.traverse((o) => {
      o.frustumCulled = false;
    });
    vrm.scene.userData.__baseYaw = vrm.scene.rotation.y; // rotateVRM0 may have turned the model round
    // face shapes by short name ("BRW_Angry") so emotes can drive them directly
    const morphs: { mesh: THREE.Mesh; index: number; key: string }[] = [];
    vrm.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      const dict = mesh.morphTargetDictionary;
      if (mesh.isMesh && dict) {
        Object.keys(dict).forEach((name) => {
          const m = name.match(/Fcl_(.+)$/);
          if (m) {
            morphs.push({ mesh, index: dict[name], key: m[1] });
          }
        });
      }
    });
    vrm.scene.userData.__morphs = morphs;
    const look = lookFor(modelUrl);
    const head = vrm.humanoid.getRawBoneNode("head");
    if (look && head) {
      const faces = vrm.scene.userData.__baseYaw !== 0 ? -1 : 1; // a turned-round (0.x) model's face is on its bone's -Z side
      const props = new THREE.Group();
      look.props.forEach((p) => props.add(buildProp(p, faces)));
      head.add(props);
      if (look.costume) {
        dress(vrm, look.costume, faces, Boolean(look.costume.bulky));
      }
    }
    vrm.scene.userData.__scale = look?.scale ?? 1;
    vrm.scene.scale.setScalar(look?.scale ?? 1);
    vrm.scene.userData.__prepared = true;
  }
  return vrm;
};

/** Head position of the loaded model, for framing. */
const headY = (vrm: VRM): number => {
  const head = vrm.humanoid.getNormalizedBoneNode("head");
  const v = new THREE.Vector3();
  if (head) {
    vrm.scene.updateMatrixWorld(true);
    head.getWorldPosition(v);
    return v.y;
  }
  return 1.4;
};

type Pose = Partial<Record<"lu" | "ru" | "ll" | "rl" | "spine" | "head", [number, number, number]>>;
/** Poses in normalized-bone space: the left arm hangs down at z = +1.2, the right at z = -1.2. */
const GESTURES: Record<Gesture, Pose> = {
  idle: {},
  raise: { ru: [0, 0, 1.05], rl: [0, 0, 0.55] },
  point: { ru: [0, 1.25, -0.1], rl: [0, 0.15, 0] },
  bow: { spine: [0.42, 0, 0], head: [0.25, 0, 0] },
  open: { lu: [0, -0.35, 0.75], ru: [0, 0.35, -0.75], ll: [0, -0.5, 0.2], rl: [0, 0.5, -0.2] },
};

type PoseProps = {
  globalFrame: number; envelope: number[]; expressions: number[][]; mood: "hype" | "calm"; seed: number; motion: number; framing: VrmFraming; url: string; modelUrl: string;
  bodyYaw: number; speaking: boolean; emote?: string; emoteWeight: number; gesture: Gesture; gestureWeight: number; expressiveness: number;
};
const PRESETS = ["happy", "angry", "sad", "relaxed", "surprised"] as const;
const mix = (a: number, b: number, t: number) => a + (b - a) * t;

const Model: React.FC<PoseProps> = ({ url, modelUrl, globalFrame, envelope, expressions, mood, seed, motion, framing, bodyYaw, speaking, emote, emoteWeight, gesture, gestureWeight, expressiveness }) => {
  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  }) as unknown as GLTF;
  const vrm = useMemo(() => prepare(gltf, modelUrl), [gltf, modelUrl]);
  const hy = useMemo(() => headY(vrm), [vrm]);
  const { fps } = useVideoConfig();
  const { camera } = useThree();

  useFrame(() => {
    const open = speaking ? mouthAt(envelope, globalFrame) : 0;
    const blink = blinkAt(globalFrame, seed);
    const t = globalFrame / fps;
    const h = vrm.humanoid;
    const em = vrm.expressionManager;
    const face = emote ? EMOTES[emote] : undefined;
    const row = expressions[Math.max(0, Math.min(expressions.length - 1, Math.round(globalFrame)))] ?? [];

    // mouth: a vowel mix from the envelope so it is not one flapping shape
    if (em) {
      em.setValue("aa", Math.min(1, open * 0.7));
      em.setValue("ih", Math.max(0, Math.sin(t * 9.3) * 0.25) * open);
      em.setValue("ou", Math.max(0, Math.sin(t * 6.1 + 1) * 0.3) * open);
      // wide or narrowed emote eyes and a blink fight each other: let the emote win
      em.setValue("blink", face && (face.ALL_Surprised || face.EYE_Surprised || face.EYE_Joy) ? blink * (1 - emoteWeight) : blink);
      // tone of the words: per-frame preset weights computed at synthesis time
      const base = mood === "hype" ? 0.1 : 0.2;
      PRESETS.forEach((name, i) => {
        const v = Math.min(1, (row[i] ?? 0) * expressiveness) * (face ? 1 - emoteWeight * 0.8 : 1);
        em.setValue(name, name === "happy" ? Math.min(1, base * (face ? 1 - emoteWeight : 1) + v) : v);
      });
      em.update();
    }
    // face shapes the VRM presets do not reach: surprise from the track, plus the named emote
    const morphs: { mesh: THREE.Mesh; index: number; key: string }[] = vrm.scene.userData.__morphs ?? [];
    const surprised = Math.min(1, (row[4] ?? 0) * expressiveness);
    morphs.forEach(({ mesh, index, key }) => {
      if (!mesh.morphTargetInfluences || /^(MTH_[AIUEO]|EYE_Close|ALL_(Fun|Sorrow|Angry|Joy|Neutral)|HA_)/.test(key)) {
        return; // visemes, blinks and the preset faces belong to the expression manager
      }
      let w = key === "ALL_Surprised" ? surprised * (face ? 1 - emoteWeight : 1) : 0;
      const target = face?.[key];
      if (target) {
        // an emote's mouth shape gives way while the character is talking
        w = Math.max(w, target * emoteWeight * (key.startsWith("MTH_") ? 1 - open * 0.7 : 1));
      }
      mesh.morphTargetInfluences[index] = w;
    });

    // head: slow sway plus a nod that follows speech energy
    const head = h.getNormalizedBoneNode("head");
    const neck = h.getNormalizedBoneNode("neck");
    const spine = h.getNormalizedBoneNode("spine");
    const chest = h.getNormalizedBoneNode("chest") ?? h.getNormalizedBoneNode("upperChest");
    const yaw = (Math.sin(t / 3.1) * 0.11 + Math.sin(t / 7.3) * 0.05) * motion;
    const pitch = (Math.sin(t / 3.9) * 0.04 + open * 0.09 + (mood === "hype" ? -0.03 : 0)) * motion;
    const roll = (Math.sin(t / 5.7) * 0.06 + (open > 0.1 ? Math.sin(globalFrame / 4) * open * 0.03 : 0)) * motion;
    const pose = GESTURES[gesture] ?? {};
    const g = gestureWeight;
    const breathe = Math.sin((t / 4.2) * Math.PI * 2);
    if (head) {
      head.rotation.set(pitch + (pose.head?.[0] ?? 0) * g, yaw, roll);
    }
    if (neck) {
      neck.rotation.set(pitch * 0.4, yaw * 0.4, roll * 0.3);
    }
    if (spine) {
      spine.rotation.set(0.015 * breathe + (pose.spine?.[0] ?? 0) * g, 0, 0);
    }
    if (chest) {
      chest.rotation.set(0.012 * breathe, 0, 0);
    }
    // relaxed arms instead of the T-pose, with a tiny breathing lift, blended towards the gesture
    const arm = (bone: THREE.Object3D | null, idle: [number, number, number], to?: [number, number, number]) => {
      if (bone) {
        const wave = to ? Math.sin(t * 2.2) * 0.04 * g : 0; // a held pose still breathes a little
        bone.rotation.set(mix(idle[0], to?.[0] ?? idle[0], g), mix(idle[1], to?.[1] ?? idle[1], g), mix(idle[2], to?.[2] ?? idle[2], g) + wave);
      }
    };
    arm(h.getNormalizedBoneNode("leftUpperArm"), [0, 0, 1.2 - 0.02 * breathe], pose.lu);
    arm(h.getNormalizedBoneNode("rightUpperArm"), [0, 0, -1.2 + 0.02 * breathe], pose.ru);
    arm(h.getNormalizedBoneNode("leftLowerArm"), [0, 0, 0.25], pose.ll);
    arm(h.getNormalizedBoneNode("rightLowerArm"), [0, 0, -0.25], pose.rl);
    h.update();

    // turned characters look where their head points (at each other), not at the camera
    vrm.scene.rotation.y = (vrm.scene.userData.__baseYaw ?? 0) + bodyYaw;
    if (vrm.lookAt) {
      vrm.lookAt.target = bodyYaw === 0 ? camera : null;
      vrm.lookAt.update(0);
    }

    const faceY = (hy + 0.06) * (vrm.scene.userData.__scale ?? 1);
    if (framing === "face") {
      camera.position.set(0, faceY, 0.58);
      camera.lookAt(0, faceY - 0.01, 0);
    } else if (framing === "stage") {
      // further back and a little higher: room for a crown above and a raised arm beside
      camera.position.set(0, faceY + 0.02, 1.95);
      camera.lookAt(0, faceY - 0.03, 0);
    } else {
      camera.position.set(0, faceY - 0.1, 1.3);
      camera.lookAt(0, faceY - 0.13, 0);
    }
    camera.updateProjectionMatrix();
  });

  return <primitive object={vrm.scene} />;
};

export const VrmHost: React.FC<Props> = ({ modelUrl, globalFrame, envelope, expressions = [], width, height, framing = "bust", mood = "hype", seed = 7, motion = 1, yaw = 0, speaking = true, emote, emoteWeight = 1, gesture = "idle", gestureWeight = 1, expressiveness = 1 }) => {
  const url = staticFile(modelUrl);
  const fov = framing === "face" ? 26 : 24;
  return (
    <ThreeCanvas
      width={width}
      height={height}
      camera={{ fov, near: 0.05, far: 20, position: [0, 1.4, 1] }}
      gl={{ alpha: true, antialias: true, premultipliedAlpha: true }}
      onCreated={({ gl, scene }) => {
        gl.setClearColor(0x000000, 0); // transparent canvas: the reel background shows through
        scene.background = null;
      }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={1.1} />
      <directionalLight position={[1.2, 2.4, 2.0]} intensity={1.6} />
      <directionalLight position={[-1.5, 1.0, 1.0]} intensity={0.5} color="#9fb4ff" />
      {/* no Suspense here: ThreeCanvas's own boundary delays the render until the model is loaded */}
      <Model url={url} modelUrl={modelUrl} globalFrame={globalFrame} envelope={envelope} expressions={expressions} mood={mood} seed={seed} motion={motion} framing={framing} bodyYaw={yaw} speaking={speaking} emote={emote} emoteWeight={emoteWeight} gesture={gesture} gestureWeight={gestureWeight} expressiveness={expressiveness} />
    </ThreeCanvas>
  );
};
