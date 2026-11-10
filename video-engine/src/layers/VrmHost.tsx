/**
 * VrmHost: a prebuilt anime character (VRM avatar) as the host. The model's
 * own rig does the work: VRM expressions for lip-sync (aa / ih / ou) and
 * blinks, humanoid bones for head sway, breathing and a relaxed arm pose.
 * Everything is a pure function of the frame; spring-bone physics is left
 * off so parallel frame rendering stays deterministic.
 *
 * Loading goes through React Suspense (useLoader) because Remotion's
 * ThreeCanvas only advances the scene when the frame changes or when the
 * canvas is created; a model that arrives later would never be drawn.
 *
 * Model: video-engine/public/models/host.vrm (VRoid Project sample, CC0;
 * see assets/models/LICENSE.txt). Any VRM 0.x or 1.0 file works.
 */
import React, { useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader, type GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { staticFile, useVideoConfig } from "remotion";
import { blinkAt, mouthAt } from "./Presenter";

export type VrmFraming = "bust" | "face";

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
};

/** Prepare a freshly loaded VRM once (useLoader caches the gltf per url). */
const prepare = (gltf: GLTF): VRM => {
  const vrm = gltf.userData.vrm as VRM;
  if (!vrm.scene.userData.__prepared) {
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.rotateVRM0(vrm); // 0.x models face -Z; turn them to +Z like 1.0
    vrm.scene.traverse((o) => {
      o.frustumCulled = false;
    });
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

/** Headphones resting round the neck: a tilted band behind the neck and two
 *  cups on the upper chest, attached to the chest bone once per model. */
const addHeadphones = (vrm: VRM) => {
  const h = vrm.humanoid;
  const anchor = h.getRawBoneNode("upperChest") ?? h.getRawBoneNode("chest") ?? h.getRawBoneNode("spine");
  const neck = h.getRawBoneNode("neck");
  if (!anchor || !neck || anchor.userData.__headphones) {
    return;
  }
  const g = new THREE.Group();
  const bandMat = new THREE.MeshToonMaterial({ color: 0x16161b });
  const cupMat = new THREE.MeshToonMaterial({ color: 0x2b2b33 });
  const rimMat = new THREE.MeshToonMaterial({ color: 0x4a4a55 });
  const padMat = new THREE.MeshToonMaterial({ color: 0x0a0a0d });
  const band = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.013, 12, 48), bandMat);
  band.rotation.x = Math.PI / 2 - 0.55; // around the neck, front dipping onto the chest
  band.position.set(0, -0.02, 0.03);
  g.add(band);
  for (const sx of [-1, 1]) {
    // yoke from the band down to the cup, then the cup with a lighter rim and a dark pad
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.05, 10), bandMat);
    stem.position.set(sx * 0.082, -0.055, 0.085);
    stem.rotation.set(0.5, 0, sx * 0.4);
    g.add(stem);
    const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.044, 0.044, 0.028, 32), cupMat);
    cup.rotation.set(Math.PI / 2 - 0.35, 0, sx * 0.35);
    cup.position.set(sx * 0.068, -0.095, 0.12);
    g.add(cup);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.04, 0.006, 8, 32), rimMat);
    rim.rotation.set(-0.35, 0, sx * 0.35);
    rim.position.set(sx * 0.068, -0.095, 0.134);
    g.add(rim);
    const pad = new THREE.Mesh(new THREE.TorusGeometry(0.027, 0.012, 10, 32), padMat);
    pad.rotation.set(-0.35, 0, sx * 0.35);
    pad.position.set(sx * 0.068, -0.095, 0.138);
    g.add(pad);
  }
  vrm.scene.updateMatrixWorld(true);
  const p = new THREE.Vector3();
  neck.getWorldPosition(p);
  p.y -= 0.015;
  anchor.worldToLocal(p);
  g.position.copy(p);
  const q = new THREE.Quaternion();
  anchor.getWorldQuaternion(q);
  g.quaternion.copy(q.invert());
  anchor.add(g);
  anchor.userData.__headphones = true;
};

type PoseProps = { globalFrame: number; envelope: number[]; expressions: number[][]; mood: "hype" | "calm"; seed: number; motion: number; framing: VrmFraming; url: string };
const PRESETS = ["happy", "angry", "sad", "relaxed", "surprised"] as const;

const Model: React.FC<PoseProps> = ({ url, globalFrame, envelope, expressions, mood, seed, motion, framing }) => {
  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  }) as unknown as GLTF;
  const vrm = useMemo(() => prepare(gltf), [gltf]);
  const hy = useMemo(() => headY(vrm), [vrm]);
  const { fps } = useVideoConfig();
  const { camera } = useThree();
  useMemo(() => addHeadphones(vrm), [vrm]);

  useFrame(() => {
    const open = mouthAt(envelope, globalFrame);
    const blink = blinkAt(globalFrame, seed);
    const t = globalFrame / fps;
    const h = vrm.humanoid;
    const em = vrm.expressionManager;

    // mouth: a vowel mix from the envelope so it is not one flapping shape
    if (em) {
      em.setValue("aa", Math.min(1, open * 0.7));
      em.setValue("ih", Math.max(0, Math.sin(t * 9.3) * 0.25) * open);
      em.setValue("ou", Math.max(0, Math.sin(t * 6.1 + 1) * 0.3) * open);
      em.setValue("blink", blink);
      // tone of the words: per-frame preset weights computed at synthesis time
      const row = expressions[Math.max(0, Math.min(expressions.length - 1, Math.round(globalFrame)))] ?? [];
      const base = mood === "hype" ? 0.1 : 0.2;
      PRESETS.forEach((name, i) => {
        const v = row[i] ?? 0;
        em.setValue(name, name === "happy" ? Math.min(1, base + v) : v);
      });
      em.update();
    }

    // head: slow sway plus a nod that follows speech energy
    const head = h.getNormalizedBoneNode("head");
    const neck = h.getNormalizedBoneNode("neck");
    const spine = h.getNormalizedBoneNode("spine");
    const chest = h.getNormalizedBoneNode("chest") ?? h.getNormalizedBoneNode("upperChest");
    const yaw = (Math.sin(t / 3.1) * 0.11 + Math.sin(t / 7.3) * 0.05) * motion;
    const pitch = (Math.sin(t / 3.9) * 0.04 + open * 0.09 + (mood === "hype" ? -0.03 : 0)) * motion;
    const roll = (Math.sin(t / 5.7) * 0.06 + (open > 0.1 ? Math.sin(globalFrame / 4) * open * 0.03 : 0)) * motion;
    if (head) {
      head.rotation.set(pitch, yaw, roll);
    }
    if (neck) {
      neck.rotation.set(pitch * 0.4, yaw * 0.4, roll * 0.3);
    }
    const breathe = Math.sin((t / 4.2) * Math.PI * 2);
    if (spine) {
      spine.rotation.set(0.015 * breathe, 0, 0);
    }
    if (chest) {
      chest.rotation.set(0.012 * breathe, 0, 0);
    }
    // relaxed arms instead of the T-pose, with a tiny breathing lift
    const lu = h.getNormalizedBoneNode("leftUpperArm");
    const ru = h.getNormalizedBoneNode("rightUpperArm");
    const ll = h.getNormalizedBoneNode("leftLowerArm");
    const rl = h.getNormalizedBoneNode("rightLowerArm");
    if (lu) {
      lu.rotation.set(0, 0, 1.2 - 0.02 * breathe);
    }
    if (ru) {
      ru.rotation.set(0, 0, -1.2 + 0.02 * breathe);
    }
    if (ll) {
      ll.rotation.set(0, 0, 0.25);
    }
    if (rl) {
      rl.rotation.set(0, 0, -0.25);
    }
    h.update();

    if (vrm.lookAt) {
      vrm.lookAt.target = camera;
      vrm.lookAt.update(0);
    }

    const faceY = hy + 0.06;
    if (framing === "face") {
      camera.position.set(0, faceY, 0.58);
      camera.lookAt(0, faceY - 0.01, 0);
    } else {
      camera.position.set(0, faceY - 0.1, 1.3);
      camera.lookAt(0, faceY - 0.13, 0);
    }
    camera.updateProjectionMatrix();
  });

  return <primitive object={vrm.scene} />;
};

export const VrmHost: React.FC<Props> = ({ modelUrl, globalFrame, envelope, expressions = [], width, height, framing = "bust", mood = "hype", seed = 7, motion = 1 }) => {
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
      <Model url={url} globalFrame={globalFrame} envelope={envelope} expressions={expressions} mood={mood} seed={seed} motion={motion} framing={framing} />
    </ThreeCanvas>
  );
};
