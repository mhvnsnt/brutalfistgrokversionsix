#!/usr/bin/env python3
"""Open-source Mixamo rigger for Bannon named-part GLBs.

BANNON.glb ships as 15 rigid body parts (pelvis/chest/head/shL/…) with ZERO
skinned bones. The old UniRig/sew path (BANNON_rigged.glb) produced extra
unnamed joints and melted bind poses — Cronenberg beasts.

This rigger:

  * never invents geometry or textures
  * welds the 15 real parts into one vertex buffer
  * builds a Mixamo 22-joint hierarchy with identity rest rotations
    (translations only) so Mixamo mocap local quats bind cleanly
  * assigns winner-take-all rigid weights (1.0 on the owning bone)
    so a vertex cannot smear across the wrong limb
  * writes a skinned GLB whose inverse-bind matrices equal inverse(rest world)

That GLB is the only legal input to glb_to_directx_x.py.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

COMPONENT_NP = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}
TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

# Mixamo deform skeleton (no fingers — mocap still drives the 22 body joints).
BONES = [
    ("mixamorig:Hips", None),
    ("mixamorig:Spine", "mixamorig:Hips"),
    ("mixamorig:Spine1", "mixamorig:Spine"),
    ("mixamorig:Spine2", "mixamorig:Spine1"),
    ("mixamorig:Neck", "mixamorig:Spine2"),
    ("mixamorig:Head", "mixamorig:Neck"),
    ("mixamorig:LeftShoulder", "mixamorig:Spine2"),
    ("mixamorig:LeftArm", "mixamorig:LeftShoulder"),
    ("mixamorig:LeftForeArm", "mixamorig:LeftArm"),
    ("mixamorig:LeftHand", "mixamorig:LeftForeArm"),
    ("mixamorig:RightShoulder", "mixamorig:Spine2"),
    ("mixamorig:RightArm", "mixamorig:RightShoulder"),
    ("mixamorig:RightForeArm", "mixamorig:RightArm"),
    ("mixamorig:RightHand", "mixamorig:RightForeArm"),
    ("mixamorig:LeftUpLeg", "mixamorig:Hips"),
    ("mixamorig:LeftLeg", "mixamorig:LeftUpLeg"),
    ("mixamorig:LeftFoot", "mixamorig:LeftLeg"),
    ("mixamorig:LeftToeBase", "mixamorig:LeftFoot"),
    ("mixamorig:RightUpLeg", "mixamorig:Hips"),
    ("mixamorig:RightLeg", "mixamorig:RightUpLeg"),
    ("mixamorig:RightFoot", "mixamorig:RightLeg"),
    ("mixamorig:RightToeBase", "mixamorig:RightFoot"),
]

# Named part → Mixamo deform bone. Rigid 1.0 weights. Hierarchy bones without
# a part (Shoulder/Spine/Neck/Toe) still exist so Mixamo clips can rotate them.
PART_BONE = {
    "pelvis": "mixamorig:Hips",
    "chest": "mixamorig:Spine2",
    "head": "mixamorig:Head",
    "shL": "mixamorig:LeftArm",
    "elL": "mixamorig:LeftForeArm",
    "haL": "mixamorig:LeftHand",
    "shR": "mixamorig:RightArm",
    "elR": "mixamorig:RightForeArm",
    "haR": "mixamorig:RightHand",
    "hipL": "mixamorig:LeftUpLeg",
    "knL": "mixamorig:LeftLeg",
    "ftL": "mixamorig:LeftFoot",
    "hipR": "mixamorig:RightUpLeg",
    "knR": "mixamorig:RightLeg",
    "ftR": "mixamorig:RightFoot",
}


def load_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, _version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError(f"Not a GLB: {path}")
    offset = 12
    json_chunk = None
    bin_chunk = b""
    while offset + 8 <= length:
        clen, ctype = struct.unpack_from("<I4s", data, offset)
        chunk = data[offset + 8 : offset + 8 + clen]
        if ctype.startswith(b"JSON"):
            json_chunk = json.loads(chunk)
        elif ctype.startswith(b"BIN"):
            bin_chunk = chunk
        offset += 8 + clen
    if json_chunk is None:
        raise ValueError("GLB missing JSON")
    return json_chunk, bin_chunk


def read_accessor(g: dict, blob: bytes, index: int) -> np.ndarray:
    acc = g["accessors"][index]
    ncomp = TYPE_N[acc["type"]]
    count = acc["count"]
    dtype = COMPONENT_NP[acc["componentType"]]
    if "bufferView" not in acc:
        return np.zeros((count, ncomp), dtype=np.float32)
    view = g["bufferViews"][acc["bufferView"]]
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or (dtype().nbytes * ncomp)
    item = dtype().nbytes * ncomp
    if stride == item:
        arr = np.frombuffer(blob, dtype=dtype, count=count * ncomp, offset=offset)
        arr = arr.reshape(count, ncomp).copy()
    else:
        rows = []
        for i in range(count):
            start = offset + i * stride
            rows.append(np.frombuffer(blob, dtype=dtype, count=ncomp, offset=start))
        arr = np.stack(rows, axis=0)
    return arr.astype(np.float32)


def extract_png(g: dict, blob: bytes) -> Image.Image:
    images = g.get("images") or []
    if not images:
        return Image.new("RGB", (256, 256), (32, 28, 22))
    image = images[0]
    raw = None
    if "bufferView" in image:
        view = g["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        raw = blob[start : start + view["byteLength"]]
    elif "uri" in image and image["uri"].startswith("data:"):
        import base64

        raw = base64.b64decode(image["uri"].split(",", 1)[1])
    if not raw:
        return Image.new("RGB", (256, 256), (32, 28, 22))
    return Image.open(BytesIO(raw)).convert("RGBA")


def centroid(pos: np.ndarray) -> np.ndarray:
    return pos.mean(axis=0)


def mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a * (1.0 - t) + b * t


def load_named_parts(path: Path) -> tuple[dict[str, dict], Image.Image]:
    g, blob = load_glb(path)
    nodes = g.get("nodes") or []
    meshes = g.get("meshes") or []
    parts: dict[str, dict] = {}
    for node in nodes:
        if "mesh" not in node:
            continue
        name = node.get("name") or meshes[node["mesh"]].get("name") or ""
        prim = meshes[node["mesh"]]["primitives"][0]
        pos = read_accessor(g, blob, prim["attributes"]["POSITION"])
        idx = read_accessor(g, blob, prim["indices"]).astype(np.int32).reshape(-1, 3)
        uv = (
            read_accessor(g, blob, prim["attributes"]["TEXCOORD_0"])
            if "TEXCOORD_0" in prim["attributes"]
            else np.zeros((pos.shape[0], 2), dtype=np.float32)
        )
        nrm = (
            read_accessor(g, blob, prim["attributes"]["NORMAL"])
            if "NORMAL" in prim["attributes"]
            else None
        )
        parts[name] = {"pos": pos, "idx": idx, "uv": uv, "nrm": nrm}
    missing = [p for p in PART_BONE if p not in parts]
    if missing:
        raise SystemExit(f"{path} is missing named parts: {missing}")
    return parts, extract_png(g, blob)


def build_joints(parts: dict[str, dict]) -> dict[str, np.ndarray]:
    c = {name: centroid(part["pos"]) for name, part in parts.items()}
    # Articulation points sit on the seam between two parts, not at mesh centroids,
    # so a limb rotates around the joint instead of orbiting its own mass.
    hips = c["pelvis"]
    chest = c["chest"]
    head = c["head"]
    joints = {
        "mixamorig:Hips": hips,
        "mixamorig:Spine": mix(hips, chest, 0.28),
        "mixamorig:Spine1": mix(hips, chest, 0.58),
        "mixamorig:Spine2": chest,
        "mixamorig:Neck": mix(chest, head, 0.55),
        "mixamorig:Head": head,
        "mixamorig:LeftShoulder": mix(chest, c["shL"], 0.22),
        "mixamorig:LeftArm": mix(c["shL"], c["elL"], 0.08),
        "mixamorig:LeftForeArm": mix(c["shL"], c["elL"], 0.92),
        "mixamorig:LeftHand": mix(c["elL"], c["haL"], 0.85),
        "mixamorig:RightShoulder": mix(chest, c["shR"], 0.22),
        "mixamorig:RightArm": mix(c["shR"], c["elR"], 0.08),
        "mixamorig:RightForeArm": mix(c["shR"], c["elR"], 0.92),
        "mixamorig:RightHand": mix(c["elR"], c["haR"], 0.85),
        "mixamorig:LeftUpLeg": mix(hips, c["hipL"], 0.55),
        "mixamorig:LeftLeg": mix(c["hipL"], c["knL"], 0.92),
        "mixamorig:LeftFoot": mix(c["knL"], c["ftL"], 0.55),
        "mixamorig:LeftToeBase": c["ftL"] + np.array([0.04, -0.02, 0.08], dtype=np.float64),
        "mixamorig:RightUpLeg": mix(hips, c["hipR"], 0.55),
        "mixamorig:RightLeg": mix(c["hipR"], c["knR"], 0.92),
        "mixamorig:RightFoot": mix(c["knR"], c["ftR"], 0.55),
        "mixamorig:RightToeBase": c["ftR"] + np.array([0.04, -0.02, -0.08], dtype=np.float64),
    }
    return {k: np.asarray(v, dtype=np.float64) for k, v in joints.items()}


def merge_parts(parts: dict[str, dict], bone_index: dict[str, int]) -> dict:
    positions = []
    normals = []
    uvs = []
    joints = []
    weights = []
    indices = []
    base = 0
    for part_name, bone_name in PART_BONE.items():
        part = parts[part_name]
        pos = part["pos"]
        n = pos.shape[0]
        if part["nrm"] is not None:
            nrm = part["nrm"]
        else:
            nrm = np.zeros_like(pos)
            for a, b, c in part["idx"]:
                face = np.cross(pos[b] - pos[a], pos[c] - pos[a])
                nrm[a] += face
                nrm[b] += face
                nrm[c] += face
            lens = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm = np.divide(nrm, np.clip(lens, 1e-8, None))
        ji = bone_index[bone_name]
        positions.append(pos)
        normals.append(nrm)
        uvs.append(part["uv"])
        j = np.zeros((n, 4), dtype=np.uint16)
        w = np.zeros((n, 4), dtype=np.float32)
        j[:, 0] = ji
        w[:, 0] = 1.0
        joints.append(j)
        weights.append(w)
        indices.append(part["idx"] + base)
        base += n
    pos = np.concatenate(positions, axis=0).astype(np.float32)
    nrm = np.concatenate(normals, axis=0).astype(np.float32)
    uv = np.concatenate(uvs, axis=0).astype(np.float32)
    jnt = np.concatenate(joints, axis=0)
    wgt = np.concatenate(weights, axis=0)
    idx = np.concatenate(indices, axis=0).astype(np.uint32)
    # BANNON.glb is authored facing +X with +Z = character left. Mixamo / Irrlicht
    # rest pose faces +Z (three.js camera looks −Z) with +X = left.
    # Ry(+90): (x, y, z) → (z, y, −x)
    pos = np.stack([pos[:, 2], pos[:, 1], -pos[:, 0]], axis=1)
    nrm = np.stack([nrm[:, 2], nrm[:, 1], -nrm[:, 0]], axis=1)
    # Feet on the ground, hips over the origin.
    min_y = float(pos[:, 1].min())
    pos[:, 1] -= min_y
    hips_xz = pos[jnt[:, 0] == bone_index["mixamorig:Hips"]][:, [0, 2]].mean(axis=0)
    pos[:, 0] -= hips_xz[0]
    pos[:, 2] -= hips_xz[1]
    return {
        "pos": pos,
        "nrm": nrm,
        "uv": uv,
        "joints": jnt,
        "weights": wgt,
        "idx": idx,
        "ground": min_y,
        "hips_xz": hips_xz,
        "rotate": "Ry+90",
    }


def pad4(b: bytes, fill: bytes = b" ") -> bytes:
    return b + fill * ((4 - len(b) % 4) % 4)


def write_glb(path: Path, mesh: dict, joints: dict[str, np.ndarray], png: bytes) -> None:
    bone_names = [b[0] for b in BONES]
    parent_of = {b[0]: b[1] for b in BONES}
    # Armature (0) + 22 joints (1..) + mesh node
    armature = 0
    joint_node = {name: i + 1 for i, name in enumerate(bone_names)}
    mesh_node = 1 + len(bone_names)

    nodes: list[dict] = [{"name": "Armature", "children": [joint_node["mixamorig:Hips"]]}]
    ibm = np.zeros((len(bone_names), 16), dtype=np.float32)
    for i, name in enumerate(bone_names):
        world = joints[name]
        parent = parent_of[name]
        parent_world = joints[parent] if parent else np.zeros(3)
        local = world - parent_world
        node: dict = {
            "name": name,
            "translation": [float(local[0]), float(local[1]), float(local[2])],
        }
        kids = [joint_node[child] for child, p in parent_of.items() if p == name]
        if kids:
            node["children"] = kids
        nodes.append(node)
        # Column-major inverse translation.
        ibm[i] = [
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            -float(world[0]), -float(world[1]), -float(world[2]), 1,
        ]
    nodes.append({"name": "BANNON_MESH", "mesh": 0, "skin": 0})

    pos = mesh["pos"].astype(np.float32)
    nrm = mesh["nrm"].astype(np.float32)
    uv = mesh["uv"].astype(np.float32)
    jnt = mesh["joints"].astype(np.uint16)
    wgt = mesh["weights"].astype(np.float32)
    idx = mesh["idx"].astype(np.uint32)

    blobs = []
    views = []
    accessors = []

    def add_array(arr: np.ndarray, typ: str, ctype: int, target: int | None = None) -> int:
        raw = arr.tobytes()
        offset = sum(len(b) for b in blobs)
        blobs.append(raw)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target is not None:
            view["target"] = target
        views.append(view)
        acc: dict = {
            "bufferView": len(views) - 1,
            "componentType": ctype,
            "count": int(arr.shape[0]),
            "type": typ,
        }
        if arr.dtype == np.float32 and arr.ndim == 2 and arr.shape[1] in (2, 3):
            acc["min"] = arr.min(axis=0).tolist()
            acc["max"] = arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    i_pos = add_array(pos, "VEC3", 5126, 34962)
    i_nrm = add_array(nrm, "VEC3", 5126, 34962)
    i_uv = add_array(uv, "VEC2", 5126, 34962)
    i_jnt = add_array(jnt, "VEC4", 5123, 34962)
    i_wgt = add_array(wgt, "VEC4", 5126, 34962)
    i_idx = add_array(idx.reshape(-1, 1), "SCALAR", 5125, 34963)
    i_ibm = add_array(ibm, "MAT4", 5126)
    img_off = sum(len(b) for b in blobs)
    blobs.append(png)
    views.append({"buffer": 0, "byteOffset": img_off, "byteLength": len(png)})
    img_view = len(views) - 1
    bin_blob = pad4(b"".join(blobs), b"\x00")

    gltf = {
        "asset": {"version": "2.0", "generator": "brutal-fist-named-part-rigger"},
        "scene": 0,
        "scenes": [{"nodes": [armature, mesh_node]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "BANNON_SEWN_MESH",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": i_pos,
                            "NORMAL": i_nrm,
                            "TEXCOORD_0": i_uv,
                            "JOINTS_0": i_jnt,
                            "WEIGHTS_0": i_wgt,
                        },
                        "indices": i_idx,
                        "material": 0,
                    }
                ],
            }
        ],
        "skins": [
            {
                "name": "mixamo",
                "skeleton": armature,
                "joints": [joint_node[n] for n in bone_names],
                "inverseBindMatrices": i_ibm,
            }
        ],
        "materials": [
            {
                "name": "bannon",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9728, "minFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"mimeType": "image/png", "bufferView": img_view}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(bin_blob)}],
    }
    json_bytes = pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    header = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_bytes) + 8 + len(bin_blob))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        header
        + struct.pack("<I4s", len(json_bytes), b"JSON")
        + json_bytes
        + struct.pack("<I4s", len(bin_blob), b"BIN\x00")
        + bin_blob
    )


def render_preview(mesh: dict, tex: Image.Image, out: Path) -> None:
    pos = mesh["pos"]
    idx = mesh["idx"]
    uv = mesh["uv"]
    nrm = mesh["nrm"]
    w, h = 320, 240
    img = Image.new("RGB", (w, h), (12, 12, 14))
    draw = ImageDraw.Draw(img)
    tarr = np.asarray(tex.convert("RGB"))
    tw, th = tarr.shape[1], tarr.shape[0]
    center_y = float(pos[:, 1].max()) * 0.52
    rel = pos.copy()
    rel[:, 1] -= center_y
    z = rel[:, 2] + 2.8
    sx = (rel[:, 0] / z) * 150 + w / 2
    sy = h / 2 - (rel[:, 1] / z) * 150
    light = np.array([0.3, 0.85, 0.45])
    light = light / np.linalg.norm(light)
    order = []
    for i, (a, b, c) in enumerate(idx):
        order.append(((float(z[a]) + float(z[b]) + float(z[c])) / 3.0, i, a, b, c))
    order.sort(reverse=True)
    for _, _, a, b, c in order:
        n = nrm[a] + nrm[b] + nrm[c]
        shade = 0.25 + 0.75 * max(0.0, float(np.dot(n, light)) / (np.linalg.norm(n) + 1e-8))
        u = (uv[a, 0] + uv[b, 0] + uv[c, 0]) / 3.0
        v = (uv[a, 1] + uv[b, 1] + uv[c, 1]) / 3.0
        tx = int(np.clip(u, 0, 1) * (tw - 1))
        ty = int(np.clip(1.0 - v, 0, 1) * (th - 1))
        col = tuple(int(x) for x in np.clip(tarr[ty, tx] * shade, 0, 255))
        draw.polygon([(sx[a], sy[a]), (sx[b], sy[b]), (sx[c], sy[c])], fill=col)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.resize((640, 480), Image.Resampling.NEAREST).save(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", default="native/source/BANNON.glb")
    parser.add_argument("--out", default="native/source/BANNON_mixamo_rigged.glb")
    parser.add_argument("--preview", default="native/qa/bannon-named-part-preview.png")
    args = parser.parse_args()
    root = Path(".").resolve()
    src = (root / args.glb).resolve()
    if not src.exists():
        raise SystemExit(f"REAL_GLB_ONLY — missing {src}")
    parts, tex = load_named_parts(src)
    print(f"source {src.name} parts={len(parts)} tex={tex.size}")
    for name, part in parts.items():
        mn, mx = part["pos"].min(0), part["pos"].max(0)
        print(
            f"  {name:8} verts={part['pos'].shape[0]:5} tris={part['idx'].shape[0]:5} "
            f"c={centroid(part['pos']).round(3).tolist()}"
        )

    bone_names = [b[0] for b in BONES]
    bone_index = {n: i for i, n in enumerate(bone_names)}
    joints = build_joints(parts)
    mesh = merge_parts(parts, bone_index)
    # Joints live in the same space as vertices after the Y-up Mixamo bake.
    for name in list(joints):
        p = joints[name]
        p = np.array([p[2], p[1], -p[0]], dtype=np.float64)
        p[1] -= mesh["ground"]
        p[0] -= mesh["hips_xz"][0]
        p[2] -= mesh["hips_xz"][1]
        joints[name] = p

    height = float(mesh["pos"][:, 1].max() - mesh["pos"][:, 1].min())
    width = float(mesh["pos"][:, 0].max() - mesh["pos"][:, 0].min())
    if height < 1.2 or height / max(width, 1e-6) < 1.35:
        raise SystemExit(
            f"Bind-pose QA failed: height={height:.3f} width={width:.3f} — still a blob"
        )

    png_buf = BytesIO()
    tex.save(png_buf, format="PNG")
    out = root / args.out
    write_glb(out, mesh, joints, png_buf.getvalue())

    preview = root / args.preview
    render_preview(mesh, tex, preview)

    report = {
        "source": str(src.relative_to(root)),
        "out": str(out.relative_to(root)),
        "policy": "REAL_GLB_ONLY / NAMED_PART_RIGID_MIXAMO",
        "parts": list(PART_BONE),
        "bones": bone_names,
        "boneCount": len(bone_names),
        "vertices": int(mesh["pos"].shape[0]),
        "triangles": int(mesh["idx"].shape[0]),
        "height": height,
        "width": width,
        "maxWeightsPerVertex": 1,
        "preview": str(preview.relative_to(root)),
    }
    (root / "native/qa").mkdir(parents=True, exist_ok=True)
    (root / "native/qa/named-part-rig.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("vertices", "triangles", "boneCount", "height", "width")}, indent=2))
    print(f"PASS wrote {out}  preview {preview}")


if __name__ == "__main__":
    main()
