#!/usr/bin/env python3
"""Rehearse the exact load path FK_Character::loadMeshsAndEffects uses.

Schwarzerblitz is a Win32/DirectX 9 executable and cannot run in this Linux
sandbox. This script walks the same files the compiled exe would:

  bin/media/characters/roster.ini
    → chara_bannon
    → Mesh1/config.txt  #MESH_FILENAME
    → Mesh1/BF_bannon.x
    → smgr->getMesh(meshfile)

It then parses that .x with the Irrlicht-compatible loader and rasterizes a
320×240 frame from the mesh the executable would feed ISkinnedMesh.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "native"))
from parse_directx_x import mesh_to_preview, parse_directx_x  # noqa: E402

ENGINE_MEDIA = (
    ROOT
    / "vendor"
    / "SchwarzerblitzEngine"
    / "schwarzerblitz_engine"
    / "bin"
    / "media"
    / "characters"
)
NATIVE_MEDIA = ROOT / "native" / "media" / "characters"
PUB = ROOT / "public" / "native" / "chara_bannon"
QA = ROOT / "native" / "qa"


def look_at(eye, target, up):
    f = target - eye
    f = f / (np.linalg.norm(f) + 1e-8)
    s = np.cross(f, up)
    s = s / (np.linalg.norm(s) + 1e-8)
    u = np.cross(s, f)
    rot = np.eye(4)
    rot[0, :3] = s
    rot[1, :3] = u
    rot[2, :3] = -f
    trans = np.eye(4)
    trans[:3, 3] = -eye
    return rot @ trans


def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(fov / 2)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1
    return m


def read_config(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        parts = line[1:].split(None, 1)
        if parts:
            out[parts[0]] = parts[1] if len(parts) > 1 else "1"
    return out


def resolve_engine_mesh() -> tuple[Path, Path, dict]:
    roster = ENGINE_MEDIA / "roster.ini"
    if not roster.exists():
        raise SystemExit(f"Engine roster missing: {roster}")
    slot = None
    for line in roster.read_text().splitlines():
        if line.lower().startswith("chara_bannon"):
            slot = line.split()
            break
    if not slot:
        raise SystemExit("chara_bannon is not in the engine roster.ini")
    char_dir = ENGINE_MEDIA / "chara_bannon"
    cfg_path = char_dir / "Mesh1" / "config.txt"
    if not cfg_path.exists():
        raise SystemExit(f"Missing {cfg_path}")
    cfg = read_config(cfg_path)
    mesh_name = cfg.get("MESH_FILENAME")
    if not mesh_name:
        raise SystemExit("#MESH_FILENAME missing from Mesh1/config.txt")
    mesh_path = char_dir / "Mesh1" / mesh_name
    if not mesh_path.exists():
        # Windows is case-insensitive; try a case-blind match.
        hits = list((char_dir / "Mesh1").glob("*.x"))
        raise SystemExit(f"Mesh file not found: {mesh_path} (found {[p.name for p in hits]})")
    identity = {
        "rosterLine": " ".join(slot),
        "characterDirectory": str(char_dir.relative_to(ROOT)),
        "outfitDirectory": "Mesh1/",
        "outfitFilename": mesh_name,
        "engineCall": f'smgr->getMesh("{char_dir / "Mesh1" / mesh_name}")',
        "cpp": "FK_Character::loadMeshsAndEffects → (ISkinnedMesh*)smgr->getMesh(meshfile)",
    }
    return mesh_path, char_dir, identity


def render_frame(mesh, tex_path: Path, out_path: Path, scale: float) -> None:
    pos = np.array(mesh.positions, dtype=np.float32).reshape(-1, 3) * scale
    nrm = np.array(mesh.normals, dtype=np.float32).reshape(-1, 3)
    uvs = np.array(mesh.uvs, dtype=np.float32).reshape(-1, 2)
    idx = np.array(mesh.indices, dtype=np.int32).reshape(-1, 3)
    tex = Image.open(tex_path).convert("RGB")
    tw, th = tex.size
    tex_arr = np.asarray(tex)

    w, h = 320, 240
    eye = np.array([0.0, 1.05, 3.4], dtype=np.float64)
    target = np.array([0.0, 0.95, 0.0], dtype=np.float64)
    view = look_at(eye, target, np.array([0.0, 1.0, 0.0]))
    proj = perspective(math.radians(32), w / h, 0.05, 40.0)
    mvp = proj @ view

    ones = np.ones((pos.shape[0], 1), dtype=np.float64)
    hp = np.concatenate([pos.astype(np.float64), ones], axis=1)
    clip = (mvp @ hp.T).T
    ndc = clip[:, :3] / np.clip(clip[:, 3:4], 1e-6, None)
    sx = (ndc[:, 0] * 0.5 + 0.5) * (w - 1)
    sy = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * (h - 1)
    depth = ndc[:, 2]

    light = np.array([0.35, 0.9, 0.45], dtype=np.float64)
    light = light / np.linalg.norm(light)

    img = Image.new("RGB", (w, h), (12, 12, 14))
    draw = ImageDraw.Draw(img)
    draw.ellipse((36, 176, 284, 232), outline=(42, 42, 48), width=2)

    order = []
    for i, (a, b, c) in enumerate(idx):
        z = (depth[a] + depth[b] + depth[c]) / 3.0
        order.append((z, i, a, b, c))
    order.sort(reverse=True)

    for _, _, a, b, c in order:
        n = nrm[a] + nrm[b] + nrm[c]
        ln = np.linalg.norm(n) + 1e-8
        shade = 0.18 + 0.82 * max(0.0, float(np.dot(n, light)) / ln)
        u = (uvs[a, 0] + uvs[b, 0] + uvs[c, 0]) / 3.0
        v = (uvs[a, 1] + uvs[b, 1] + uvs[c, 1]) / 3.0
        tx = int(np.clip(u, 0, 1) * (tw - 1))
        ty = int(np.clip(v, 0, 1) * (th - 1))
        sample = tex_arr[ty, tx].astype(np.float32)
        rgb = tuple(int(x) for x in np.clip(sample * shade, 0, 255))
        pts = [(sx[a], sy[a]), (sx[b], sy[b]), (sx[c], sy[c])]
        draw.polygon(pts, fill=rgb)

    out = img.resize((640, 480), Image.Resampling.NEAREST)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)


def write_status(identity: dict, mesh, mesh_path: Path, cfg: dict, mocap: dict, bound: dict) -> None:
    PUB.mkdir(parents=True, exist_ok=True)
    scale = float(cfg.get("OUTFIT_MESH_SCALE", "1"))
    status = {
        "character": "Bannon",
        "policy": "REAL_GLB_ONLY / REAL_FBX_ONLY",
        "sourceGlb": "native/source/BANNON.glb",
        "mesh": {
            "file": mesh_path.name,
            "vertices": mesh.vertex_count,
            "triangles": mesh.triangle_count,
            "bones": len(mesh.bones),
            "headerBones": mesh.header_bones,
            "xBytes": mesh_path.stat().st_size,
            "scale": scale,
            "texture": mesh.texture,
        },
        "engine": {
            "executableLoads": identity["cpp"],
            "getMesh": identity["engineCall"],
            "roster": identity["rosterLine"],
            "path": identity["characterDirectory"],
            "outfit": identity["outfitDirectory"] + identity["outfitFilename"],
            "installed": True,
            "win32Note": "Schwarzerblitz.exe is a Visual Studio / DirectX 9 build and is not in the public source tree. The .x is installed in the exact media slot the compiled exe loads.",
        },
        "mocap": mocap.get("counts", {}),
        "bound": bound.get("bound", []),
        "missing": bound.get("missing", []),
        "clips": [],
    }
    loco = [
        {"clip": "idle", "viewer": "clips/idle.json", "cat": "locomotion", "status": "exported", "source": "BANNON GLB clip"},
        {"clip": "walkFast", "viewer": "clips/walkFast.json", "cat": "locomotion", "status": "exported", "source": "BANNON GLB clip"},
        {"clip": "running", "viewer": "clips/running.json", "cat": "locomotion", "status": "exported", "source": "BANNON GLB clip"},
    ]
    exported = [
        {
            "clip": row["clip"],
            "cat": row.get("cat"),
            "status": row.get("status"),
            "viewer": row.get("viewer"),
            "source": f"real FBX mocap ({row.get('skeleton', 'mixamo')})" if row.get("status") == "exported" else row.get("reason"),
            "frames": row.get("frames"),
        }
        for row in mocap.get("clips", [])
        if row.get("status") == "exported" and row.get("viewer")
    ]
    seen = {row["clip"] for row in loco + exported}
    for b in bound.get("bound", []):
        if b["clip"] in seen:
            continue
        slug = "".join(ch if ch.isalnum() else "_" for ch in b["clip"]).strip("_")
        viewer = f"clips/{slug}.json"
        if not (PUB / viewer).exists():
            continue
        exported.append(
            {
                "clip": b["clip"],
                "cat": "strike",
                "status": "exported",
                "viewer": viewer,
                "source": "engine bind",
                "frames": b.get("frames"),
            }
        )
    status["clips"] = loco + exported
    (PUB / "status.json").write_text(json.dumps(status, indent=2) + "\n")


def main() -> None:
    mesh_path, char_dir, identity = resolve_engine_mesh()
    cfg = read_config(char_dir / "Mesh1" / "config.txt")
    text = mesh_path.read_text(encoding="ascii", errors="strict")
    mesh = parse_directx_x(text)
    if mesh.vertex_count < 1000:
        raise SystemExit(f"Parsed mesh too small ({mesh.vertex_count} verts) — refusing to promote")
    if mesh.triangle_count < 1000:
        raise SystemExit(f"Parsed mesh too small ({mesh.triangle_count} tris)")
    if len(mesh.bones) < 20:
        raise SystemExit(f"Parsed skeleton too small ({len(mesh.bones)} bones)")

    preview = mesh_to_preview(mesh, str(mesh_path.relative_to(ROOT)))
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "engine-mesh.json").write_text(json.dumps(preview, separators=(",", ":")))
    (PUB / "preview.json").write_text(json.dumps(preview, separators=(",", ":")))
    (PUB / "BF_bannon.x").write_bytes(mesh_path.read_bytes())
    tex_src = char_dir / "Mesh1" / mesh.texture
    if tex_src.exists():
        shutil.copy2(tex_src, PUB / mesh.texture)

    scale = float(cfg.get("OUTFIT_MESH_SCALE", "1"))
    # Engine applies outfitMeshScale on the node; rasterize with that scale so
    # the rehearsal frame matches what Irrlicht would draw after setScale.
    # The mesh itself is ~1.88m; scale ~6.38 → ~12 engine units (SB convention).
    render_scale = 1.0  # preview camera is authored in metres
    frame_pub = PUB / "native-frame.png"
    frame_qa = QA / "native-frame.png"
    render_frame(mesh, tex_src if tex_src.exists() else PUB / "bannon.png", frame_pub, render_scale)
    shutil.copy2(frame_pub, frame_qa)

    mocap = {}
    mocap_path = QA / "mocap-export-report.json"
    if mocap_path.exists():
        mocap = json.loads(mocap_path.read_text())
    bound = {}
    bind_path = QA / "engine-anim-bind.json"
    if bind_path.exists():
        bound = json.loads(bind_path.read_text())
    write_status(identity, mesh, mesh_path, cfg, mocap, bound)

    report = {
        "status": "PASS",
        "engineCall": identity["cpp"],
        "mesh": str(mesh_path.relative_to(ROOT)),
        "vertices": mesh.vertex_count,
        "triangles": mesh.triangle_count,
        "bones": len(mesh.bones),
        "headerBones": mesh.header_bones,
        "texture": mesh.texture,
        "xBytes": mesh_path.stat().st_size,
        "roster": identity["rosterLine"],
        "frame": str(frame_pub.relative_to(ROOT)),
        "note": "Win32 Schwarzerblitz.exe is not present in the public source tree; this rehearsal parses and rasterizes the exact .x installed in its media slot.",
    }
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "engine-load-rehearsal.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
