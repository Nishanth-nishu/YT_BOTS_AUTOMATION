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

type PoseProps = { globalFrame: number; envelope: number[]; mood: "hype" | "calm"; seed: number; motion: number; framing: VrmFraming; url: string };

const Model: React.FC<PoseProps> = ({ url, globalFrame, envelope, mood, seed, motion, framing }) => {
  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  }) as unknown as GLTF;
  const vrm = useMemo(() => prepare(gltf), [gltf]);
  const hy = useMemo(() => headY(vrm), [vrm]);
  const { fps } = useVideoConfig();
  const { camera } = useThree();

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
      em.setValue("happy", mood === "hype" ? 0.12 : 0.25);
      em.update();
    }

    // head: slow sway plus a nod that follows speech energy
    const head = h.getNormalizedBoneNode("head");
    const neck = h.getNormalizedBoneNode("neck");
    const spine = h.getNormalizedBoneNode("spine");
    const chest = h.getNormalizedBoneNode("chest") ?? h.getNormalizedBoneNode("upperChest");
    const yaw = (Math.sin(t / 3.1) * 0.08 + Math.sin(t / 7.3) * 0.04) * motion;
    const pitch = (Math.sin(t / 3.9) * 0.03 + open * 0.05 + (mood === "hype" ? -0.03 : 0)) * motion;
    const roll = (Math.sin(t / 5.7) * 0.04 + (open > 0.1 ? Math.sin(globalFrame / 4) * open * 0.02 : 0)) * motion;
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

export const VrmHost: React.FC<Props> = ({ modelUrl, globalFrame, envelope, width, height, framing = "bust", mood = "hype", seed = 7, motion = 1 }) => {
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
      <Model url={url} globalFrame={globalFrame} envelope={envelope} mood={mood} seed={seed} motion={motion} framing={framing} />
    </ThreeCanvas>
  );
};
