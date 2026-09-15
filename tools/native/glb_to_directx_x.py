#!/usr/bin/env python3
"""Convert a skinned glTF/GLB fighter into Schwarzerblitz/Irrlicht DirectX .x resources.

This is the Linux implementation of the build-bannon-character pipeline.
Assimp is not required: the writer emits the same text .x templates the
upstream engine already loads (xof 0303txt 0032 + Frame/Mesh/SkinWeights).
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
COMPONENT_NP = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}
TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

BONE_MAP = {
    "HEAD": "mixamorig_Head",
    "NECK": "mixamorig_Neck",
    "TORSO": "mixamorig_Spine2",
    "SPINE": "mixamorig_Spine",
    "HIPS": "mixamorig_Hips",
    "SHOULDER_L": "mixamorig_LeftShoulder",
    "SHOULDER_R": "mixamorig_RightShoulder",
    "ELBOW_L": "mixamorig_LeftArm",
    "ELBOW_R": "mixamorig_RightArm",
    "WRIST_L": "mixamorig_LeftHand",
    "WRIST_R": "mixamorig_RightHand",
    "LEG_L": "mixamorig_LeftUpLeg",
    "LEG_R": "mixamorig_RightUpLeg",
    "KNEE_L": "mixamorig_LeftLeg",
    "KNEE_R": "mixamorig_RightLeg",
    "ANKLE_L": "mixamorig_LeftFoot",
    "ANKLE_R": "mixamorig_RightFoot",
    "FOOT_L": "mixamorig_LeftToeBase",
    "FOOT_R": "mixamorig_RightToeBase",
    "THUMB_L": "mixamorig_LeftHandThumb2",
    "THUMB_R": "mixamorig_RightHandThumb2",
    "FINGERS_L": "mixamorig_LeftHandIndex2",
    "FINGERS_R": "mixamorig_RightHandIndex2",
}


def sanitize(name: str | None) -> str:
    if not name:
        return "unnamed"
    return name.replace(":", "_").replace(" ", "_").replace(".", "_")


def load_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
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
        raise ValueError("GLB missing JSON chunk")
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
    stride = view.get("byteStride") or (COMPONENT_SIZE[acc["componentType"]] * ncomp)
    if stride == COMPONENT_SIZE[acc["componentType"]] * ncomp:
        arr = np.frombuffer(blob, dtype=dtype, count=count * ncomp, offset=offset)
        arr = arr.reshape(count, ncomp).copy()
    else:
        item = COMPONENT_SIZE[acc["componentType"]] * ncomp
        rows = []
        for i in range(count):
            start = offset + i * stride
            rows.append(np.frombuffer(blob, dtype=dtype, count=ncomp, offset=start))
        arr = np.stack(rows, axis=0)
    if acc.get("normalized"):
        if dtype == np.uint8:
            arr = arr.astype(np.float32) / 255.0
        elif dtype == np.uint16:
            arr = arr.astype(np.float32) / 65535.0
        else:
            arr = arr.astype(np.float32)
    else:
        arr = arr.astype(np.float32)
    return arr


def quat_to_mat(q: np.ndarray) -> np.ndarray:
    x, y, z, w = q.tolist()
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = 1 - 2 * (yy + zz)
    m[0, 1] = 2 * (xy - wz)
    m[0, 2] = 2 * (xz + wy)
    m[1, 0] = 2 * (xy + wz)
    m[1, 1] = 1 - 2 * (xx + zz)
    m[1, 2] = 2 * (yz - wx)
    m[2, 0] = 2 * (xz - wy)
    m[2, 1] = 2 * (yz + wx)
    m[2, 2] = 1 - 2 * (xx + yy)
    return m


def node_local_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        m = np.array(node["matrix"], dtype=np.float64).reshape(4, 4, order="F")
        return m
    t = np.array(node.get("translation", [0, 0, 0]), dtype=np.float64)
    r = np.array(node.get("rotation", [0, 0, 0, 1]), dtype=np.float64)
    s = np.array(node.get("scale", [1, 1, 1]), dtype=np.float64)
    tm = np.eye(4, dtype=np.float64)
    tm[:3, 3] = t
    rm = quat_to_mat(r)
    sm = np.diag([s[0], s[1], s[2], 1.0])
    return tm @ rm @ sm


def fmt_f(v: float) -> str:
    return f"{v: .6f}"


def write_matrix_dx(m: np.ndarray, indent: str) -> str:
    # numpy is column-vector / column-major conceptually; DirectX .x wants
    # row-major with translation in the last row.
    r = m.T
    rows = []
    for i in range(4):
        rows.append(
            indent
            + ", ".join(fmt_f(r[i, j]) for j in range(4))
            + ("," if i < 3 else ";;")
        )
    return "\n".join(rows)


def extract_png(g: dict, blob: bytes, out_path: Path, size: int = 256) -> str:
    images = g.get("images") or []
    if not images:
        img = Image.new("RGB", (size, size), (32, 28, 22))
        img.save(out_path)
        return out_path.name
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
        img = Image.new("RGB", (size, size), (32, 28, 22))
        img.save(out_path)
        return out_path.name
    from io import BytesIO

    im = Image.open(BytesIO(raw)).convert("RGBA")
    im = im.resize((size, size), Image.Resampling.NEAREST)
    im.save(out_path)
    return out_path.name


def write_frame(node_idx: int, nodes: list[dict], children_of: dict[int, list[int]], indent: str) -> str:
    node = nodes[node_idx]
    name = sanitize(node.get("name") or f"node_{node_idx}")
    local = node_local_matrix(node)
    lines = [
        f"{indent}Frame {name} {{",
        f"{indent}  FrameTransformMatrix {{",
        write_matrix_dx(local, indent + "    "),
        f"{indent}  }}",
    ]
    for child in children_of.get(node_idx, []):
        lines.append(write_frame(child, nodes, children_of, indent + "  "))
    lines.append(f"{indent}}} // End of {name}")
    return "\n".join(lines)


def convert_mesh(glb_path: Path, out_dir: Path, tex_name: str = "bannon.png") -> dict:
    g, blob = load_glb(glb_path)
    nodes = g.get("nodes") or []
    skins = g.get("skins") or []
    meshes = g.get("meshes") or []
    if not skins or not meshes:
        raise ValueError("GLB is missing a skin or mesh")

    skin = skins[0]
    joints = list(skin["joints"])
    ibm_raw = read_accessor(g, blob, skin["inverseBindMatrices"])
    ibm = np.stack([ibm_raw[i].reshape(4, 4, order="F") for i in range(len(joints))]).astype(np.float64)

    mesh_node = next(i for i, n in enumerate(nodes) if n.get("mesh") is not None)
    mesh = meshes[nodes[mesh_node]["mesh"]]
    prim = mesh["primitives"][0]
    attrs = prim["attributes"]
    positions = read_accessor(g, blob, attrs["POSITION"])
    normals = read_accessor(g, blob, attrs["NORMAL"]) if "NORMAL" in attrs else None
    uvs = read_accessor(g, blob, attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else None
    joints_attr = read_accessor(g, blob, attrs["JOINTS_0"]).astype(np.int32)
    weights_attr = read_accessor(g, blob, attrs["WEIGHTS_0"])
    indices = read_accessor(g, blob, prim["indices"]).astype(np.int32).reshape(-1)
    faces = indices.reshape(-1, 3)
    nverts = positions.shape[0]
    nfaces = faces.shape[0]

    # Bake mesh-node local transform into vertices (usually identity).
    mesh_local = node_local_matrix(nodes[mesh_node])
    if not np.allclose(mesh_local, np.eye(4)):
        ones = np.ones((nverts, 1))
        hp = np.concatenate([positions, ones], axis=1) @ mesh_local.T
        positions = hp[:, :3]
        nrm_m = np.linalg.inv(mesh_local[:3, :3]).T
        if normals is not None:
            normals = (normals @ nrm_m.T)
            norms = np.linalg.norm(normals, axis=1, keepdims=True)
            normals = np.divide(normals, np.clip(norms, 1e-8, None))

    if normals is None:
        normals = np.zeros_like(positions)
        for a, b, c in faces:
            n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
            normals[a] += n
            normals[b] += n
            normals[c] += n
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.divide(normals, np.clip(norms, 1e-8, None))
    if uvs is None:
        uvs = np.zeros((nverts, 2), dtype=np.float32)

    # Per-bone influence lists
    bone_verts: list[list[int]] = [[] for _ in joints]
    bone_weights: list[list[float]] = [[] for _ in joints]
    max_per_vertex = 0
    for vi in range(nverts):
        count = 0
        for k in range(joints_attr.shape[1]):
            w = float(weights_attr[vi, k])
            j = int(joints_attr[vi, k])
            if w <= 1e-8 or j < 0:
                continue
            bone_verts[j].append(vi)
            bone_weights[j].append(w)
            count += 1
        max_per_vertex = max(max_per_vertex, count)

    children_of: dict[int, list[int]] = defaultdict(list)
    parents = {i: None for i in range(len(nodes))}
    for i, node in enumerate(nodes):
        for c in node.get("children") or []:
            children_of[i].append(c)
            parents[c] = i

    # Skeleton root: first joint whose parent is not a joint.
    joint_set = set(joints)
    hips = joints[0]
    skeleton_parent = parents.get(hips)
    armature_idx = skeleton_parent if skeleton_parent is not None else hips

    # Only emit joint Frames — mesh nodes under Armature used to leak extra
    # unnamed bones into the .x and that is what melted the bind pose.
    joint_children: dict[int, list[int]] = defaultdict(list)
    for i, kids in children_of.items():
        if i == armature_idx or i in joint_set:
            joint_children[i] = [c for c in kids if c in joint_set]

    tex_path = out_dir / tex_name
    extract_png(g, blob, tex_path, 256)

    lines = [
        "xof 0303txt 0032",
        "",
        "template XSkinMeshHeader {",
        "  <3cf169ce-ff7c-44ab-93c0-f78f62d172e2>",
        "  WORD nMaxSkinWeightsPerVertex;",
        "  WORD nMaxSkinWeightsPerFace;",
        "  WORD nBones;",
        "}",
        "",
        "template SkinWeights {",
        "  <6f0d123b-bad2-4167-a0d0-80224f25fabb>",
        "  STRING transformNodeName;",
        "  DWORD nWeights;",
        "  array DWORD vertexIndices[nWeights];",
        "  array float weights[nWeights];",
        "  Matrix4x4 matrixOffset;",
        "}",
        "",
        "Frame Root {",
        "  FrameTransformMatrix {",
        "     1.000000, 0.000000, 0.000000, 0.000000,",
        "     0.000000, 1.000000, 0.000000, 0.000000,",
        "     0.000000, 0.000000, 1.000000, 0.000000,",
        "     0.000000, 0.000000, 0.000000, 1.000000;;",
        "  }",
        write_frame(armature_idx, nodes, joint_children, "  "),
        "  Mesh { // BANNON_SEWN",
        f"    {nverts};",
    ]
    for i, p in enumerate(positions):
        comma = "," if i < nverts - 1 else ";"
        lines.append(f"    {fmt_f(p[0])};{fmt_f(p[1])};{fmt_f(p[2])};{comma}")
    lines.append(f"    {nfaces};")
    for i, fce in enumerate(faces):
        comma = "," if i < nfaces - 1 else ";"
        lines.append(f"    3; {int(fce[0])},{int(fce[1])},{int(fce[2])};{comma}")

    lines.append("    MeshNormals {")
    lines.append(f"      {nverts};")
    for i, n in enumerate(normals):
        comma = "," if i < nverts - 1 else ";"
        lines.append(f"      {fmt_f(n[0])};{fmt_f(n[1])};{fmt_f(n[2])};{comma}")
    lines.append(f"      {nfaces};")
    for i, fce in enumerate(faces):
        comma = "," if i < nfaces - 1 else ";"
        lines.append(f"      3; {int(fce[0])},{int(fce[1])},{int(fce[2])};{comma}")
    lines.append("    }")

    lines.append("    MeshTextureCoords {")
    lines.append(f"      {nverts};")
    for i, uv in enumerate(uvs):
        comma = "," if i < nverts - 1 else ";"
        lines.append(f"      {fmt_f(uv[0])};{fmt_f(1.0 - uv[1])};{comma}")
    lines.append("    }")

    lines.append("    MeshMaterialList {")
    lines.append("      1;")
    lines.append(f"      {nfaces};")
    for i in range(nfaces):
        comma = "," if i < nfaces - 1 else ";"
        lines.append(f"      0{comma}")
    lines.append("      Material {")
    lines.append("        1.000000;1.000000;1.000000;1.000000;;")
    lines.append("        16.000000;")
    lines.append("        0.100000;0.100000;0.100000;;")
    lines.append("        0.000000;0.000000;0.000000;;")
    lines.append(f'        TextureFilename {{"{tex_name}";}}')
    lines.append("      }")
    lines.append("    }")

    lines.append("    XSkinMeshHeader {")
    lines.append(f"      {max(max_per_vertex, 1)};")
    lines.append(f"      {max(max_per_vertex, 1) * 3};")
    lines.append(f"      {len(joints)};")
    lines.append("    }")

    for ji, node_idx in enumerate(joints):
        name = sanitize(nodes[node_idx].get("name") or f"joint_{ji}")
        idxs = bone_verts[ji]
        ws = bone_weights[ji]
        lines.append("    SkinWeights {")
        lines.append(f'      "{name}";')
        lines.append(f"      {len(idxs)};")
        if idxs:
            for k, vi in enumerate(idxs):
                comma = "," if k < len(idxs) - 1 else ";"
                lines.append(f"      {vi}{comma}")
            for k, w in enumerate(ws):
                comma = "," if k < len(ws) - 1 else ";"
                lines.append(f"      {fmt_f(w)}{comma}")
        lines.append(write_matrix_dx(ibm[ji], "      "))
        lines.append(f"    }} // End of {name} skin weights")

    lines.append("  } // End of BANNON_SEWN mesh")
    lines.append("} // End of Root")
    lines.append("")

    mins = positions.min(axis=0)
    maxs = positions.max(axis=0)
    height = float(maxs[1] - mins[1])
    report = {
        "source": str(glb_path),
        "vertices": int(nverts),
        "triangles": int(nfaces),
        "bones": [sanitize(nodes[j].get("name")) for j in joints],
        "boneCount": len(joints),
        "maxWeightsPerVertex": int(max_per_vertex),
        "boundsMin": [float(x) for x in mins],
        "boundsMax": [float(x) for x in maxs],
        "height": height,
        "suggestedMeshScale": float(12.0 / height) if height > 1e-4 else 1.0,
        "texture": tex_name,
        "armatureNode": sanitize(nodes[armature_idx].get("name")),
        "hips": sanitize(nodes[hips].get("name")),
    }
    joint_parent = {i: None for i in range(len(nodes))}
    for i, node in enumerate(nodes):
        for c in node.get("children") or []:
            joint_parent[c] = i
    node_to_joint = {node_idx: ji for ji, node_idx in enumerate(joints)}
    preview_bones = []
    for ji, node_idx in enumerate(joints):
        pnode = joint_parent.get(node_idx)
        parent_ji = node_to_joint[pnode] if pnode in node_to_joint else -1
        local = node_local_matrix(nodes[node_idx])
        preview_bones.append(
            {
                "name": sanitize(nodes[node_idx].get("name")),
                "parent": int(parent_ji),
                "matrix": local.T.flatten().round(6).tolist(),
            }
        )
    preview = {
        "vertexCount": int(nverts),
        "triangleCount": int(nfaces),
        "positions": np.asarray(positions, dtype=np.float32).reshape(-1).round(6).tolist(),
        "normals": np.asarray(normals, dtype=np.float32).reshape(-1).round(5).tolist(),
        "uvs": np.asarray(uvs, dtype=np.float32).reshape(-1).round(5).tolist(),
        "indices": np.asarray(faces, dtype=np.int32).reshape(-1).tolist(),
        "skinIndex": np.asarray(joints_attr, dtype=np.int32).reshape(-1).tolist(),
        "skinWeight": np.asarray(weights_attr, dtype=np.float32).reshape(-1).round(5).tolist(),
        "bones": preview_bones,
        "texture": tex_name,
        "sourceX": "BF_bannon.x",
    }
    return {
        "text": "\n".join(lines),
        "report": report,
        "preview": preview,
        "armature_idx": armature_idx,
        "g": g,
        "blob": blob,
        "nodes": nodes,
        "children_of": children_of,
        "joints": joints,
    }


def convert_animation(anim_glb: Path, mesh_glb: Path, fps: int = 30) -> tuple[str, int]:
    mesh_g, _ = load_glb(mesh_glb)
    anim_g, anim_blob = load_glb(anim_glb)
    mesh_nodes = mesh_g.get("nodes") or []
    mesh_names = {sanitize(n.get("name")) for n in mesh_nodes}
    anim_nodes = anim_g.get("nodes") or []
    animations = anim_g.get("animations") or []
    if not animations:
        raise ValueError(f"No animations in {anim_glb}")
    animation = animations[0]

    # Rest-pose frames from the MESH skeleton so Irrlicht can match joints.
    children_of: dict[int, list[int]] = defaultdict(list)
    parents = {}
    for i, node in enumerate(mesh_nodes):
        for c in node.get("children") or []:
            children_of[i].append(c)
            parents[c] = i
    skins = mesh_g.get("skins") or []
    hips = skins[0]["joints"][0]
    armature_idx = parents.get(hips, hips)

    # Collect per-bone keys from the animation GLB.
    channels = animation.get("channels") or []
    samplers = animation.get("samplers") or []
    by_bone: dict[str, dict[str, list[tuple[float, list[float]]]]] = defaultdict(lambda: {"rotation": [], "scale": [], "translation": []})
    duration = 0.0
    for ch in channels:
        node = anim_nodes[ch["target"]["node"]]
        name = sanitize(node.get("name"))
        if name not in mesh_names:
            continue
        path = ch["target"]["path"]
        if path == "weights":
            continue
        samp = samplers[ch["sampler"]]
        times = read_accessor(anim_g, anim_blob, samp["input"]).reshape(-1)
        values = read_accessor(anim_g, anim_blob, samp["output"])
        key_path = {"rotation": "rotation", "scale": "scale", "translation": "translation"}[path]
        for t, row in zip(times, values):
            by_bone[name][key_path].append((float(t), [float(x) for x in row.tolist()]))
            duration = max(duration, float(t))

    frame_count = max(1, int(round(duration * fps)))
    lines = [
        "xof 0303txt 0032",
        "",
        "Frame Root {",
        "  FrameTransformMatrix {",
        "     1.000000, 0.000000, 0.000000, 0.000000,",
        "     0.000000, 1.000000, 0.000000, 0.000000,",
        "     0.000000, 0.000000, 1.000000, 0.000000,",
        "     0.000000, 0.000000, 0.000000, 1.000000;;",
        "  }",
        write_frame(armature_idx, mesh_nodes, children_of, "  "),
        "}",
        "",
        "AnimationSet Global {",
    ]

    def keys_to_frames(pairs: list[tuple[float, list[float]]], ncomp: int, fallback: list[float]) -> list[tuple[int, list[float]]]:
        if not pairs:
            return [(0, fallback), (frame_count, fallback)]
        out = []
        for t, val in pairs:
            fr = int(round(t * fps))
            out.append((fr, val if len(val) == ncomp else (val + [0] * ncomp)[:ncomp]))
        if out[0][0] != 0:
            out.insert(0, (0, out[0][1]))
        if out[-1][0] != frame_count:
            out.append((frame_count, out[-1][1]))
        # collapse duplicate frames
        collapsed = []
        for fr, val in out:
            if collapsed and collapsed[-1][0] == fr:
                collapsed[-1] = (fr, val)
            else:
                collapsed.append((fr, val))
        return collapsed

    for bone, tracks in by_bone.items():
        rot = keys_to_frames(tracks["rotation"], 4, [0, 0, 0, 1])
        scl = keys_to_frames(tracks["scale"], 3, [1, 1, 1])
        pos = keys_to_frames(tracks["translation"], 3, [0, 0, 0])
        lines.append("  Animation {")
        lines.append(f"    {{{bone}}}")
        lines.append("    AnimationKey { // Rotation")
        lines.append("      0;")
        lines.append(f"      {len(rot)};")
        for i, (fr, val) in enumerate(rot):
            end = ";;," if i < len(rot) - 1 else ";;;"
            lines.append(f"      {fr};4; {fmt_f(val[0])},{fmt_f(val[1])},{fmt_f(val[2])},{fmt_f(val[3])}{end}")
        lines.append("    }")
        lines.append("    AnimationKey { // Scale")
        lines.append("      1;")
        lines.append(f"      {len(scl)};")
        for i, (fr, val) in enumerate(scl):
            end = ";;," if i < len(scl) - 1 else ";;;"
            lines.append(f"      {fr};3; {fmt_f(val[0])},{fmt_f(val[1])},{fmt_f(val[2])}{end}")
        lines.append("    }")
        lines.append("    AnimationKey { // Position")
        lines.append("      2;")
        lines.append(f"      {len(pos)};")
        for i, (fr, val) in enumerate(pos):
            end = ";;," if i < len(pos) - 1 else ";;;"
            lines.append(f"      {fr};3; {fmt_f(val[0])},{fmt_f(val[1])},{fmt_f(val[2])}{end}")
        lines.append("    }")
        lines.append("  }")
    lines.append("} // End of AnimationSet Global")
    lines.append("")
    return "\n".join(lines), frame_count


def parse_x_mesh_stats(text: str) -> dict:
    if not text.startswith("xof 0303txt"):
        raise ValueError("Not a text DirectX .x file")
    if "Mesh {" not in text:
        raise ValueError("Missing Mesh block")
    if "XSkinMeshHeader" not in text:
        raise ValueError("Missing XSkinMeshHeader")
    bones = text.count('SkinWeights {') - 1  # subtract template
    if bones < 1:
        raise ValueError("No SkinWeights")
    return {"bytes": len(text.encode("ascii", errors="replace")), "skinWeightBlocks": bones}


def write_character_pack(out_root: Path, report: dict, idle_frames: int, walk_frames: int, run_frames: int, identity: dict) -> None:
    char_dir = out_root / "chara_bannon"
    mesh_dir = char_dir / "Mesh1"
    anim_dir = char_dir / "animations"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    anim_dir.mkdir(parents=True, exist_ok=True)

    scale = report["suggestedMeshScale"]
    (mesh_dir / "config.txt").write_text(
        "\n".join(
            [
                "#MESH_FILENAME BF_bannon.x",
                "#OUTFIT_NAME Classic_Black_and_Gold",
                "#AVAILABLE_FROM_START 1",
                "#CHARACTER_NAME Bannon",
                "#CHARACTER_SHORTNAME Bannon",
                f"#OUTFIT_MESH_SCALE {scale:.6f}",
                "#NO_BACKFACE",
                "",
            ]
        ),
        encoding="ascii",
    )

    bones_txt = "\n".join(f"{logical}  {actual}" for logical, actual in BONE_MAP.items()) + "\n"
    (char_dir / "bones.txt").write_text(bones_txt, encoding="ascii")

    stance_end = max(idle_frames, 1)
    walk_end = max(walk_frames, 1)
    run_end = max(run_frames, 1)
    (char_dir / "character.txt").write_text(
        "\n".join(
            [
                "#NAME Bannon",
                "#SHORTNAME Bannon",
                "#AI_TYPE aggressor",
                "#BACKFACECULLINGOFF",
                "#HIT_SFX hit.png",
                "#MOVESFILE moves.txt",
                "#BONESFILE bones.txt",
                "#LIFE 250.0",
                "#WALKSPEED 60.0",
                "#WEIGHT 1.1",
                f"#STANCE idle 0 {stance_end}",
                f"#WALKING walkFast 0 {walk_end}",
                f"#RUNNING running 0 {run_end}",
                f"#SIDESTEP walkFast 0 {walk_end}",
                f"#STANDGUARD idle 0 {stance_end}",
                f"#CROUCHGUARD idle 0 {stance_end}",
                f"#CROUCHING idle 0 {stance_end}",
                f"#LOWSTANCE idle 0 {stance_end}",
                f"#HITHIGHWEAKFRONT idle 0 {min(4, stance_end)}",
                f"#HITMEDWEAKFRONT idle 0 {min(4, stance_end)}",
                f"#HITLOWWEAKFRONT idle 0 {min(4, stance_end)}",
                f"#HITHIGHWEAKBACK idle 0 {min(4, stance_end)}",
                f"#HITMEDWEAKBACK idle 0 {min(4, stance_end)}",
                f"#HITLOWWEAKBACK idle 0 {min(4, stance_end)}",
                f"#HITMEDSTRONG idle 0 {min(8, stance_end)}",
                f"#HITMEDSTRONGBACK idle 0 {min(8, stance_end)}",
                f"#HITLOWSTRONG idle 0 {min(8, stance_end)}",
                f"#HITLOWSTRONGBACK idle 0 {min(8, stance_end)}",
                f"#HITHIGHSTRONG idle 0 {min(8, stance_end)}",
                f"#HITHIGHSTRONGBACK idle 0 {min(8, stance_end)}",
                f"#HITFLIGHTSTRONG idle 0 {min(8, stance_end)}",
                f"#HITFLIGHTSTRONGBACK idle 0 {min(8, stance_end)}",
                f"#WAKEUP idle 0 {stance_end}",
                f"#GROUNDEDSUPINE idle 0 {stance_end}",
                f"#GROUNDEDPRONE idle 0 {stance_end}",
                f"#GROUNDEDSUPINEROTATION idle 0 {stance_end}",
                f"#GROUNDEDPRONEROTATION idle 0 {stance_end}",
                f"#WINPOSE idle 0 {stance_end}",
                f"#INTRO idle 0 {stance_end}",
                f"#SUPINELANDING idle 0 {stance_end}",
                f"#JUMPING idle 0 {stance_end}",
                "",
            ]
        ),
        encoding="ascii",
    )

    (char_dir / "moves.txt").write_text(
        "\n".join(
            [
                "#MOVE Jab",
                "#DISPLAY_NAME Jab",
                "#RANGE 0.0 90.0",
                "#ANIMATION idle",
                f"#FRAMES 0 {min(12, stance_end)}",
                "#STANCE Ground",
                "#DELAY_AFTER_MOVE_MS 120",
                "#INPUT",
                "A",
                "#INPUT_END",
                "",
                "#MOVE Heavy",
                "#DISPLAY_NAME Heavy",
                "#RANGE 0.0 110.0",
                "#ANIMATION idle",
                f"#FRAMES 0 {min(18, stance_end)}",
                "#STANCE Ground",
                "#DELAY_AFTER_MOVE_MS 200",
                "#INPUT",
                "B",
                "#INPUT_END",
                "",
            ]
        ),
        encoding="ascii",
    )
    (char_dir / "additionalHitboxes.txt").write_text("", encoding="ascii")
    (char_dir / "bannon.identity.txt").write_text(
        "\n".join(
            [
                f"BannonId={identity.get('id', 'bannon')}",
                f"DisplayName={identity.get('name', 'Bannon')}",
                f"Bio={identity.get('bio', '')}",
                "SourceGLB=native/source/BANNON.glb",
                "Rig=named-part Mixamo 22-joint (rigid weights)",
                "Policy=REAL_GLB_ONLY",
                "MeshFormat=DirectX.x",
                f"Triangles={report['triangles']}",
                f"Bones={report['boneCount']}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # Tiny generated hit spark so we do not copy restricted upstream art.
    spark = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for y in range(64):
        for x in range(64):
            dx, dy = x - 32, y - 32
            d = math.sqrt(dx * dx + dy * dy)
            if d < 8:
                spark.putpixel((x, y), (255, 240, 180, 255))
            elif d < 18:
                spark.putpixel((x, y), (212, 160, 23, 180))
    spark.save(char_dir / "hit.png")
    portrait = Image.open(mesh_dir / "bannon.png").resize((128, 128), Image.Resampling.NEAREST)
    portrait.save(mesh_dir / "portrait.png")
    portrait.save(char_dir / "selectionPreview0.png")
    portrait.save(char_dir / "fightPreview.png")

    (out_root / "roster.ini").write_text("chara_bannon    0\n", encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", default="native/source/BANNON_mixamo_rigged.glb")
    parser.add_argument("--out", default="native/media/characters")
    parser.add_argument("--public", default="public/native")
    args = parser.parse_args()

    root = Path(".").resolve()
    glb = (root / args.glb).resolve()
    out_root = root / args.out
    public = root / args.public
    char_dir = out_root / "chara_bannon"
    mesh_dir = char_dir / "Mesh1"
    anim_dir = char_dir / "animations"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    anim_dir.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)

    converted = convert_mesh(glb, mesh_dir, "bannon.png")
    x_text = converted["text"]
    report = converted["report"]
    stats = parse_x_mesh_stats(x_text)
    if stats["bytes"] < 1024:
        raise SystemExit("Suspiciously small .x mesh")
    x_path = mesh_dir / "BF_bannon.x"
    x_path.write_text(x_text, encoding="ascii")

    idle_frames = walk_frames = run_frames = 1
    anim_map = {
        "idle": root / "native/source/idle.glb",
        "walkFast": root / "native/source/walking.glb",
        "running": root / "native/source/running.glb",
    }
    frame_counts = {}
    for name, path in anim_map.items():
        if path.exists():
            text, frames = convert_animation(path, glb)
            (anim_dir / f"{name}.x").write_text(text, encoding="ascii")
            frame_counts[name] = frames
    idle_frames = frame_counts.get("idle", 1)
    walk_frames = frame_counts.get("walkFast", 1)
    run_frames = frame_counts.get("running", 1)

    roster = json.loads((root / "native/source/roster.json").read_text())
    identity = next((c for c in roster if c.get("id") == "bannon"), roster[0])
    write_character_pack(out_root, report, idle_frames, walk_frames, run_frames, identity)

    report.update(
        {
            "xFile": str(x_path.relative_to(root)),
            "xBytes": stats["bytes"],
            "skinWeightBlocks": stats["skinWeightBlocks"],
            "idleFrames": idle_frames,
            "walkFrames": walk_frames,
            "runFrames": run_frames,
            "enginePath": "schwarzerblitz_engine/bin/media/characters/chara_bannon",
            "status": "PASS",
        }
    )
    qa_dir = root / "native/qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "bannon-mesh-report.json").write_text(json.dumps(report, indent=2) + "\n")

    # Public copies for the in-browser .x viewer (same bytes the engine loads).
    pub_char = public / "chara_bannon"
    pub_char.mkdir(parents=True, exist_ok=True)
    (pub_char / "BF_bannon.x").write_bytes(x_path.read_bytes())
    (pub_char / "bannon.png").write_bytes((mesh_dir / "bannon.png").read_bytes())
    (pub_char / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (pub_char / "preview.json").write_text(json.dumps(converted["preview"], separators=(",", ":")), encoding="utf-8")
    for name in ("idle", "walkFast", "running"):
        src = anim_dir / f"{name}.x"
        if src.exists():
            (pub_char / f"{name}.x").write_bytes(src.read_bytes())

    print(f"PASS native resource: {char_dir}")
    print(json.dumps({k: report[k] for k in ('vertices','triangles','boneCount','xBytes','idleFrames','suggestedMeshScale')}, indent=2))


if __name__ == "__main__":
    main()
