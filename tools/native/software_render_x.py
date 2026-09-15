#!/usr/bin/env python3
"""CPU render of the converted DirectX .x mesh (320x240 engine target)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / "public" / "native" / "chara_bannon" / "preview.json"
TEX = ROOT / "public" / "native" / "chara_bannon" / "bannon.png"
OUT = ROOT / "public" / "native" / "chara_bannon" / "native-frame.png"
QA = ROOT / "native" / "qa" / "native-frame.png"


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


def main() -> None:
    data = json.loads(PREVIEW.read_text())
    pos = np.array(data["positions"], dtype=np.float32).reshape(-1, 3)
    nrm = np.array(data["normals"], dtype=np.float32).reshape(-1, 3)
    uvs = np.array(data["uvs"], dtype=np.float32).reshape(-1, 2)
    idx = np.array(data["indices"], dtype=np.int32).reshape(-1, 3)
    tex = Image.open(TEX).convert("RGB")
    tw, th = tex.size
    tex_arr = np.asarray(tex)

    w, h = 320, 240
    eye = np.array([0.0, 0.9, 3.15], dtype=np.float64)
    target = np.array([0.0, 0.82, 0.0], dtype=np.float64)
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
        ty = int(np.clip(1.0 - v, 0, 1) * (th - 1))
        sample = tex_arr[ty, tx].astype(np.float32)
        rgb = tuple(int(x) for x in np.clip(sample * shade, 0, 255))
        pts = [(sx[a], sy[a]), (sx[b], sy[b]), (sx[c], sy[c])]
        draw.polygon(pts, fill=rgb)

    out = img.resize((640, 480), Image.Resampling.NEAREST)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT)
    QA.parent.mkdir(parents=True, exist_ok=True)
    out.save(QA)
    print(f"wrote {OUT} ({data['vertexCount']} verts, {data['triangleCount']} tris)")


if __name__ == "__main__":
    main()
