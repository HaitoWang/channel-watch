import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type RobotMode = "intro" | "auth";
export type MascotVariant = "robot" | "fox";

type MascotConfig = {
  path: string;
  targetHeight: number;
  rootPosition: [number, number, number];
  rootRotation: [number, number, number];
  modelYaw: number;
  authOffsetX: number;
  authLean: number;
  floorPosition: [number, number, number];
  floorRadius: number;
  ringPosition: [number, number, number];
  ringOpacityScale: number;
  scannerHeight: number;
  scannerOpacity: number;
  preferredAnimations: string[];
  idleSway: number;
};

const mascotConfigs = {
  robot: {
    path: "/models/RobotExpressive.glb",
    targetHeight: 3.45,
    rootPosition: [1.28, -1.75, 0],
    rootRotation: [-0.02, -0.12, 0.01],
    modelYaw: -0.1,
    authOffsetX: 0.34,
    authLean: -0.22,
    floorPosition: [1.28, -1.78, 0],
    floorRadius: 2.8,
    ringPosition: [1.18, -0.48, -0.28],
    ringOpacityScale: 1,
    scannerHeight: 3.1,
    scannerOpacity: 0.18,
    preferredAnimations: ["Idle", "Walking", "Dance", "Wave"],
    idleSway: 0.015
  },
  fox: {
    path: "/models/Fox.glb",
    targetHeight: 2.35,
    rootPosition: [1.44, -1.52, 0],
    rootRotation: [-0.02, -0.18, 0.01],
    modelYaw: -0.6,
    authOffsetX: 0.28,
    authLean: -0.18,
    floorPosition: [1.44, -1.54, 0],
    floorRadius: 2.35,
    ringPosition: [1.34, -0.58, -0.28],
    ringOpacityScale: 0.22,
    scannerHeight: 2.45,
    scannerOpacity: 0,
    preferredAnimations: ["Survey", "Walk", "Run"],
    idleSway: 0.01
  }
} satisfies Record<MascotVariant, MascotConfig>;

type RobotProbe = {
  frame: number;
  headYaw: number;
  rootYaw: number;
  sample: {
    nonDark: number;
    avgRgbSum: number;
    width: number;
    height: number;
  };
};

declare global {
  interface Window {
    __codiumRobotProbe?: () => RobotProbe | null;
  }
}

const damp = THREE.MathUtils.damp;

function createGlowRing(radius: number, color: string, opacity: number) {
  return new THREE.Mesh(
    new THREE.TorusGeometry(radius, 0.006, 8, 128),
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    })
  );
}

function normalizeModel(model: THREE.Object3D, targetHeight: number) {
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const scale = targetHeight / Math.max(size.y, 0.001);
  model.scale.setScalar(scale);

  model.updateMatrixWorld(true);
  const scaledBox = new THREE.Box3().setFromObject(model);
  const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
  model.position.x -= scaledCenter.x;
  model.position.y -= scaledBox.min.y;
  model.position.z -= scaledCenter.z;
}

function RobotScene({ mode, mascot }: { mode: RobotMode; mascot: MascotVariant }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const modeRef = useRef(mode);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const config = mascotConfigs[mascot];
    host.dataset.robotStatus = "initializing";

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true
    });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.setClearColor(0x050607, 0);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x080a0d, 6.2, 11);

    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, 0.38, 6.2);

    const root = new THREE.Group();
    root.position.set(...config.rootPosition);
    root.rotation.set(...config.rootRotation);
    scene.add(root);

    const modelRoot = new THREE.Group();
    modelRoot.rotation.y = config.modelYaw;
    root.add(modelRoot);

    scene.add(new THREE.HemisphereLight(0xf6f7f8, 0x111318, 1.9));

    const key = new THREE.DirectionalLight(0xffffff, 4.8);
    key.position.set(3.2, 4.6, 4.5);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    scene.add(key);

    const rim = new THREE.DirectionalLight(0xe6e8eb, 2.8);
    rim.position.set(-4.2, 2.7, 3.6);
    scene.add(rim);

    const warm = new THREE.PointLight(0xf2e6d2, 2.8, 5.4);
    warm.position.set(1.9, 1.2, 2.8);
    scene.add(warm);

    const coreLight = new THREE.PointLight(0xf4f5f6, 2.2, 4.2);
    coreLight.position.set(0.15, 1.75, 1.35);
    root.add(coreLight);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(config.floorRadius, 96),
      new THREE.ShadowMaterial({ opacity: 0.28, color: 0x000000 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(...config.floorPosition);
    floor.receiveShadow = true;
    scene.add(floor);

    const ringGroup = new THREE.Group();
    ringGroup.position.set(...config.ringPosition);
    [1.06, 1.42, 1.82].forEach((radius, index) => {
      const ring = createGlowRing(radius, index === 1 ? "#d8dde2" : "#ffffff", (0.1 - index * 0.018) * config.ringOpacityScale);
      ring.rotation.set(Math.PI / 2.08, 0.24 + index * 0.42, 0);
      ringGroup.add(ring);
    });
    scene.add(ringGroup);

    const scannerMaterial = new THREE.MeshBasicMaterial({
      color: "#f1f3f4",
      transparent: true,
      opacity: config.scannerOpacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const scanners = Array.from({ length: 7 }, (_, index) => {
      const scanner = new THREE.Mesh(new THREE.PlaneGeometry(0.02, config.scannerHeight), scannerMaterial);
      scanner.position.set(-1.2 + index * 0.52, 0.1, -0.42);
      scanner.rotation.z = -0.28;
      root.add(scanner);
      return scanner;
    });

    const loader = new GLTFLoader();
    let mixer: THREE.AnimationMixer | null = null;
    let activeModel: THREE.Object3D | null = null;
    let frame = 0;
    let last = performance.now();
    let animationId = 0;
    let isDisposed = false;
    const pointer = new THREE.Vector2();
    const targetPointer = new THREE.Vector2();
    const compactScene = { offsetX: 0, offsetY: 0 };

    loader.load(
      config.path,
      (gltf) => {
        if (isDisposed) return;
        const model = gltf.scene;
        normalizeModel(model, config.targetHeight);
        model.traverse((object) => {
          const mesh = object as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          const material = mesh.material;
          if (!Array.isArray(material) && material) {
            material.needsUpdate = true;
          }
        });

        modelRoot.add(model);
        activeModel = model;
        mixer = new THREE.AnimationMixer(model);

        const clip = config.preferredAnimations.map((name) => THREE.AnimationClip.findByName(gltf.animations, name)).find(Boolean) ?? gltf.animations[0];
        if (clip) {
          const action = mixer.clipAction(clip);
          action.reset().fadeIn(0.2).play();
        }

        host.dataset.robotStatus = "running";
      },
      undefined,
      () => {
        if (isDisposed) return;
        host.dataset.robotStatus = "error";
      }
    );

    const updateSize = () => {
      const width = Math.max(1, host.clientWidth);
      const height = Math.max(1, host.clientHeight);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.8);
      const isCompact = width <= 720;
      compactScene.offsetX = isCompact ? -0.72 : 0;
      compactScene.offsetY = isCompact ? 0.08 : 0;
      camera.fov = isCompact ? 39 : 34;
      camera.position.y = isCompact ? 0.5 : 0.38;
      camera.position.z = isCompact ? 7.25 : 6.2;
      renderer.setPixelRatio(dpr);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(host);
    updateSize();

    const handlePointer = (event: PointerEvent) => {
      const rect = host.getBoundingClientRect();
      targetPointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      targetPointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
    };
    window.addEventListener("pointermove", handlePointer, { passive: true });

    const samplePixels = () => {
      const gl = renderer.getContext();
      const pixels = new Uint8Array(4 * 25);
      let nonDark = 0;
      let total = 0;
      const samplePoints = [
        [0.62, 0.22],
        [0.68, 0.34],
        [0.72, 0.5],
        [0.78, 0.64],
        [0.68, 0.78]
      ];

      samplePoints.forEach(([px, py]) => {
        const x = Math.max(0, Math.floor(renderer.domElement.width * px));
        const y = Math.max(0, Math.floor(renderer.domElement.height * (1 - py)));
        gl.readPixels(x, y, 5, 5, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        for (let index = 0; index < pixels.length; index += 4) {
          const value = pixels[index] + pixels[index + 1] + pixels[index + 2];
          total += value;
          if (value > 12) nonDark += 1;
        }
      });

      return {
        nonDark,
        avgRgbSum: Math.round(total / ((pixels.length / 4) * samplePoints.length)),
        width: renderer.domElement.width,
        height: renderer.domElement.height
      };
    };

    const probe = () => ({
      frame,
      headYaw: modelRoot.rotation.y,
      rootYaw: root.rotation.y,
      sample: samplePixels()
    });
    window.__codiumRobotProbe = probe;

    const animate = () => {
      const now = performance.now();
      const delta = Math.min(0.033, (now - last) / 1000);
      const t = now * 0.001;
      last = now;
      frame += 1;
      pointer.lerp(targetPointer, 0.045);

      const authLean = modeRef.current === "auth" ? config.authLean : 0;
      root.position.x = config.rootPosition[0] + compactScene.offsetX + (modeRef.current === "auth" ? config.authOffsetX : 0);
      root.position.y = config.rootPosition[1] + compactScene.offsetY + Math.sin(t * 1.25) * 0.035;
      root.rotation.y = damp(root.rotation.y, pointer.x * 0.16 + authLean, 4.4, delta);
      root.rotation.z = Math.sin(t * 0.7) * 0.015;
      modelRoot.rotation.y = damp(modelRoot.rotation.y, pointer.x * 0.24 + config.modelYaw, 4.8, delta);
      modelRoot.rotation.x = damp(modelRoot.rotation.x, -pointer.y * 0.045, 4.8, delta);

      const pulse = 0.5 + Math.sin(t * 3.1) * 0.5;
      coreLight.intensity = 1.9 + pulse * 1.4;
      ringGroup.rotation.y = t * 0.16;
      ringGroup.rotation.z = Math.sin(t * 0.6) * 0.05;
      scanners.forEach((scanner, index) => {
        scanner.position.y = -0.2 + Math.sin(t * 0.85 + index * 0.65) * 0.24;
      });

      mixer?.update(delta);
      if (activeModel) activeModel.rotation.z = Math.sin(t * 0.8) * config.idleSway;

      renderer.render(scene, camera);
      host.dataset.robotFrame = String(frame);
      host.dataset.robotHeadYaw = modelRoot.rotation.y.toFixed(4);
      host.dataset.robotRootYaw = root.rotation.y.toFixed(4);
      if (frame % 30 === 0) {
        const sample = samplePixels();
        host.dataset.robotNonDark = String(sample.nonDark);
        host.dataset.robotAvgRgb = String(sample.avgRgbSum);
        host.dataset.robotPixels = `${sample.width}x${sample.height}`;
      }

      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);

    return () => {
      isDisposed = true;
      cancelAnimationFrame(animationId);
      resizeObserver.disconnect();
      window.removeEventListener("pointermove", handlePointer);
      if (window.__codiumRobotProbe === probe) window.__codiumRobotProbe = undefined;
      delete host.dataset.robotStatus;
      delete host.dataset.robotFrame;
      delete host.dataset.robotHeadYaw;
      delete host.dataset.robotRootYaw;
      delete host.dataset.robotNonDark;
      delete host.dataset.robotAvgRgb;
      delete host.dataset.robotPixels;
      renderer.dispose();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const material = mesh.material;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else if (material) material.dispose();
      });
      host.removeChild(renderer.domElement);
    };
  }, [mascot]);

  return <div ref={hostRef} className={`codium-robot-stage codium-robot-stage-${mode} codium-robot-stage-${mascot}`} aria-hidden="true" />;
}

export default RobotScene;
