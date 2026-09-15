import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { ClipJson, PreviewMesh } from "@/lib/native/x-mesh";

type Props = {
  mesh: PreviewMesh;
  textureUrl: string;
  clip: ClipJson | null;
  psx: boolean;
  playing: boolean;
};

function buildSkeleton(data: PreviewMesh) {
  const bones: THREE.Bone[] = [];
  for (const b of data.bones) {
    const bone = new THREE.Bone();
    bone.name = b.name;
    const m = new THREE.Matrix4().fromArray(b.matrix).transpose();
    const pos = new THREE.Vector3();
    const quat = new THREE.Quaternion();
    const scl = new THREE.Vector3();
    m.decompose(pos, quat, scl);
    bone.position.copy(pos);
    bone.quaternion.copy(quat);
    bone.scale.copy(scl);
    bones.push(bone);
  }
  for (let i = 0; i < data.bones.length; i++) {
    const p = data.bones[i].parent;
    if (p >= 0 && p < bones.length) bones[p].add(bones[i]);
  }
  const roots = data.bones.map((b, i) => (b.parent < 0 ? i : -1)).filter((i) => i >= 0);
  const root = new THREE.Group();
  root.name = "Armature";
  for (const i of roots) root.add(bones[i]);
  return { bones, root, skeleton: new THREE.Skeleton(bones) };
}

function sampleTrack(
  keys: number[][] | undefined,
  time: number,
  n: number,
  fallback: number[],
  fps: number,
) {
  if (!keys || keys.length === 0) return fallback;
  const hasTime = keys[0].length === n + 1;
  if (!hasTime) {
    const i = Math.min(keys.length - 1, Math.max(0, Math.round(time * fps)));
    return keys[i];
  }
  if (time <= keys[0][0]) return keys[0].slice(1);
  if (time >= keys[keys.length - 1][0]) return keys[keys.length - 1].slice(1);
  for (let i = 0; i < keys.length - 1; i++) {
    const t0 = keys[i][0];
    const t1 = keys[i + 1][0];
    if (time >= t0 && time <= t1) {
      const u = t1 === t0 ? 0 : (time - t0) / (t1 - t0);
      const a = keys[i];
      const b = keys[i + 1];
      if (n === 4) {
        const q = new THREE.Quaternion(a[1], a[2], a[3], a[4]);
        const q2 = new THREE.Quaternion(b[1], b[2], b[3], b[4]);
        q.slerp(q2, u);
        return [q.x, q.y, q.z, q.w];
      }
      const out = [];
      for (let k = 1; k <= n; k++) out.push(a[k] * (1 - u) + b[k] * u);
      return out;
    }
  }
  return keys[keys.length - 1].slice(1);
}

export function RingCanvas({ mesh, textureUrl, clip, psx, playing }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const clipRef = useRef(clip);
  const playingRef = useRef(playing);
  clipRef.current = clip;
  playingRef.current = playing;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    const renderer = new THREE.WebGLRenderer({ antialias: !psx, alpha: false });
    renderer.setClearColor(0x0a0a0b, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a0a0b, 10, 24);
    const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 40);

    scene.add(new THREE.HemisphereLight(0xd8d4cc, 0x1c1812, 0.9));
    const key = new THREE.DirectionalLight(0xf4f1e8, 1.4);
    key.position.set(2.4, 5.2, 3.2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xb8c0c8, 0.5);
    fill.position.set(-2.6, 2.2, 1.4);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0x9aa4b2, 0.55);
    rim.position.set(-3, 1.4, -2);
    scene.add(rim);

    const ringGeo = new THREE.CylinderGeometry(2.4, 2.4, 0.08, 16);
    const ringMat = new THREE.MeshStandardMaterial({
      color: 0x1c1c1f,
      roughness: 0.92,
      metalness: 0.08,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.y = -0.04;
    scene.add(ring);
    const apron = new THREE.Mesh(
      new THREE.TorusGeometry(2.42, 0.04, 6, 16),
      new THREE.MeshStandardMaterial({ color: 0x2a2a30, roughness: 0.7 }),
    );
    apron.rotation.x = Math.PI / 2;
    apron.position.y = 0.02;
    scene.add(apron);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(mesh.positions as ArrayLike<number>, 3));
    geo.setAttribute("normal", new THREE.Float32BufferAttribute(mesh.normals as ArrayLike<number>, 3));
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(mesh.uvs as ArrayLike<number>, 2));
    geo.setIndex(Array.from(mesh.indices as ArrayLike<number>));
    geo.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(mesh.skinIndex as ArrayLike<number>, 4));
    geo.setAttribute("skinWeight", new THREE.Float32BufferAttribute(mesh.skinWeight as ArrayLike<number>, 4));
    geo.computeBoundingBox();

    const { bones, root, skeleton } = buildSkeleton(mesh);
    const restQuat = bones.map((b) => b.quaternion.clone());
    const restPos = bones.map((b) => b.position.clone());

    const tex = new THREE.TextureLoader().load(textureUrl);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.flipY = false;
    tex.magFilter = THREE.NearestFilter;
    tex.minFilter = THREE.NearestFilter;
    tex.generateMipmaps = false;

    const mat = new THREE.MeshStandardMaterial({
      map: tex,
      roughness: 0.72,
      metalness: 0.06,
    });
    const skinned = new THREE.SkinnedMesh(geo, mat);
    skinned.add(root);
    skinned.bind(skeleton);
    skinned.frustumCulled = false;
    scene.add(skinned);

    let rt: THREE.WebGLRenderTarget | null = null;
    const quadScene = new THREE.Scene();
    const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial());
    quadScene.add(quad);

    const drag = { on: false, lx: 0, ly: 0, yaw: Math.PI + 0.28, pitch: 0.1 };
    let cancelled = false;
    let last = performance.now();
    let elapsed = 0;
    let lastClip = clipRef.current;

    const onDown = (e: PointerEvent) => {
      drag.on = true;
      drag.lx = e.clientX;
      drag.ly = e.clientY;
      el.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!drag.on) return;
      drag.yaw += (e.clientX - drag.lx) * 0.005;
      drag.pitch = Math.max(-0.2, Math.min(0.55, drag.pitch + (e.clientY - drag.ly) * 0.004));
      drag.lx = e.clientX;
      drag.ly = e.clientY;
    };
    const onUp = () => {
      drag.on = false;
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);

    const resize = () => {
      const w = el.clientWidth || 640;
      const h = el.clientHeight || 480;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const dpr = psx ? 1 : Math.min(window.devicePixelRatio || 1, 2);
      renderer.setPixelRatio(psx ? 1 : dpr);
      if (psx) {
        rt?.dispose();
        rt = new THREE.WebGLRenderTarget(320, 240);
        rt.texture.magFilter = THREE.NearestFilter;
        rt.texture.minFilter = THREE.NearestFilter;
        (quad.material as THREE.MeshBasicMaterial).map = rt.texture;
      } else if (rt) {
        rt.dispose();
        rt = null;
      }
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const boneIndex = new Map(bones.map((b, i) => [b.name, i]));

    const tick = (now: number) => {
      if (cancelled) return;
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      elapsed += dt;
      if (!drag.on) drag.yaw += 0.12 * (playingRef.current ? 1 : 0.2) * dt;

      const dist = 3.35;
      camera.position.set(
        Math.sin(drag.yaw) * dist,
        1.05 + drag.pitch * 1.4,
        Math.cos(drag.yaw) * dist,
      );
      camera.lookAt(0, 0.88, 0);

      const active = clipRef.current;
      if (active !== lastClip) {
        elapsed = 0;
        lastClip = active;
      }
      if (active && playingRef.current && active.duration > 0) {
        const time = elapsed % active.duration;
        const fps = active.fps || 30;
        for (let i = 0; i < bones.length; i++) {
          bones[i].quaternion.copy(restQuat[i]);
          bones[i].position.copy(restPos[i]);
        }
        for (const [name, track] of Object.entries(active.tracks)) {
          const i = boneIndex.get(name);
          if (i == null) continue;
          const r = sampleTrack(track.r, time, 4, [0, 0, 0, 1], fps);
          bones[i].quaternion.set(r[0], r[1], r[2], r[3]);
          if (track.t && track.t.length && name.toLowerCase().includes("hips")) {
            const p = sampleTrack(track.t, time, 3, [0, 0, 0], fps);
            bones[i].position.set(p[0], p[1], p[2]);
          }
        }
        skeleton.update();
      } else {
        for (let i = 0; i < bones.length; i++) {
          bones[i].quaternion.copy(restQuat[i]);
          bones[i].position.copy(restPos[i]);
        }
        skeleton.update();
      }

      if (psx && rt) {
        renderer.setRenderTarget(rt);
        renderer.render(scene, camera);
        renderer.setRenderTarget(null);
        renderer.render(quadScene, quadCam);
      } else {
        renderer.render(scene, camera);
      }
    };
    renderer.setAnimationLoop(tick);

    return () => {
      cancelled = true;
      renderer.setAnimationLoop(null);
      ro.disconnect();
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      geo.dispose();
      mat.dispose();
      tex.dispose();
      ringGeo.dispose();
      ringMat.dispose();
      rt?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [mesh, textureUrl, psx]);

  return <div ref={wrapRef} className="absolute inset-0 touch-none" />;
}
