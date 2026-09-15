#!/usr/bin/env python3
"""Parse a Schwarzerblitz/Irrlicht text DirectX .x skeletal mesh.

This is the Linux stand-in for Irrlicht CXMeshFileLoader / ISkinnedMesh.
It reads the same xof 0303txt files FK_Character::loadMeshsAndEffects feeds
to smgr->getMesh().
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class XBone:
    name: str
    parent: int
    matrix: list[float]


@dataclass
class XMesh:
    positions: list[float]
    normals: list[float]
    uvs: list[float]
    indices: list[int]
    skin_index: list[int]
    skin_weight: list[float]
    bones: list[XBone]
    texture: str
    vertex_count: int
    triangle_count: int
    max_weights: int = 4
    header_bones: int = 0


def _floats(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+", text)]


def _extract_balanced(src: str, open_idx: int) -> tuple[str, int]:
    depth = 0
    for i in range(open_idx, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[open_idx + 1 : i], i + 1
    raise ValueError("Unbalanced brace in .x file")


def _parse_frames(src: str) -> list[XBone]:
    bones: list[XBone] = []

    def walk(block: str, parent: int) -> None:
        i = 0
        while True:
            m = re.search(r"Frame\s+([A-Za-z0-9_]+)\s*\{", block[i:])
            if not m:
                return
            abs_i = i + m.start()
            brace = block.find("{", abs_i)
            inner, end = _extract_balanced(block, brace)
            name = m.group(1)
            if name != "Root":
                mtx_m = re.search(r"FrameTransformMatrix\s*\{([^}]*)\}", inner)
                matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
                if mtx_m:
                    nums = _floats(mtx_m.group(1))
                    if len(nums) >= 16:
                        matrix = nums[:16]
                idx = len(bones)
                bones.append(XBone(name=name, parent=parent, matrix=matrix))
                walk(inner, idx)
            else:
                walk(inner, parent)
            i = end

    walk(src, -1)
    return bones


def parse_directx_x(text: str) -> XMesh:
    if not text.startswith("xof "):
        raise ValueError("Not a DirectX .x file")
    text = re.sub(r"//[^\n]*", "", text)
    mesh_m = re.search(r"Mesh\s*\{", text)
    if not mesh_m:
        raise ValueError("No Mesh block")
    inner, _ = _extract_balanced(text, text.find("{", mesh_m.start()))
    bones = _parse_frames(text)
    bone_index = {b.name: i for i, b in enumerate(bones)}

    header = re.match(r"\s*(\d+);", inner)
    if not header:
        raise ValueError("Mesh missing vertex count")
    vertex_count = int(header.group(1))
    after = inner[header.end() :]
    face_m = re.search(r"(\d+);(?=\s*3;)", after)
    if not face_m:
        raise ValueError("Mesh missing face count")
    triangle_count = int(face_m.group(1))
    vert_nums = _floats(after[: face_m.start()])
    if len(vert_nums) < vertex_count * 3:
        raise ValueError("Vertex list truncated")
    positions = vert_nums[: vertex_count * 3]

    after_faces = after[face_m.end() :]
    ints = [int(x) for x in re.findall(r"\d+", after_faces)]
    indices: list[int] = []
    cursor = 0
    while len(indices) < triangle_count * 3 and cursor < len(ints):
        n = ints[cursor]
        cursor += 1
        indices.extend(ints[cursor : cursor + n])
        cursor += n

    normals = [0.0] * (vertex_count * 3)
    nrm_m = re.search(r"MeshNormals\s*\{", inner)
    if nrm_m:
        n_inner, _ = _extract_balanced(inner, inner.find("{", nrm_m.start()))
        n_nums = _floats(n_inner)
        # first int is count
        if n_nums:
            n_count = int(n_nums[0])
            src = n_nums[1 : 1 + n_count * 3]
            for i, v in enumerate(src):
                if i < len(normals):
                    normals[i] = v

    uvs = [0.0] * (vertex_count * 2)
    uv_m = re.search(r"MeshTextureCoords\s*\{", inner)
    if uv_m:
        u_inner, _ = _extract_balanced(inner, inner.find("{", uv_m.start()))
        u_nums = _floats(u_inner)
        if u_nums:
            u_count = int(u_nums[0])
            src = u_nums[1 : 1 + u_count * 2]
            for i, v in enumerate(src):
                if i < len(uvs):
                    uvs[i] = v

    tex = "bannon.png"
    tex_m = re.search(r'TextureFilename\s*\{\s*"([^"]+)"', inner)
    if tex_m:
        tex = tex_m.group(1)

    skin_index = [0] * (vertex_count * 4)
    skin_weight = [0.0] * (vertex_count * 4)
    filled = [0] * vertex_count
    header_bones = 0
    max_w = 4
    hdr = re.search(r"XSkinMeshHeader\s*\{\s*(\d+);\s*(\d+);\s*(\d+);", inner)
    if hdr:
        max_w = int(hdr.group(1))
        header_bones = int(hdr.group(3))

    for wm in re.finditer(r"SkinWeights\s*\{", inner):
        w_inner, _ = _extract_balanced(inner, inner.find("{", wm.start()))
        name_m = re.search(r'"([^"]+)"', w_inner)
        if not name_m:
            continue
        name = name_m.group(1)
        bi = bone_index.get(name)
        if bi is None:
            continue
        n_m = re.search(r";\s*(\d+);", w_inner)
        if not n_m:
            continue
        n = int(n_m.group(1))
        if n <= 0:
            continue
        rest = w_inner[w_inner.index(n_m.group(0)) + len(n_m.group(0)) :]
        idxs = [int(x) for x in re.findall(r"-?\d+", rest)][:n]
        weights = [float(x) for x in re.findall(r"-?\d+\.\d+(?:[eE][+-]?\d+)?", rest)][:n]
        for i in range(n):
            vi = idxs[i]
            if vi < 0 or vi >= vertex_count:
                continue
            slot = filled[vi]
            if slot < 4:
                skin_index[vi * 4 + slot] = bi
                skin_weight[vi * 4 + slot] = weights[i] if i < len(weights) else 0.0
                filled[vi] = slot + 1

    for i in range(vertex_count):
        b = i * 4
        total = skin_weight[b] + skin_weight[b + 1] + skin_weight[b + 2] + skin_weight[b + 3]
        if total > 1e-8:
            skin_weight[b] /= total
            skin_weight[b + 1] /= total
            skin_weight[b + 2] /= total
            skin_weight[b + 3] /= total
        else:
            skin_weight[b] = 1.0

    return XMesh(
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices[: triangle_count * 3],
        skin_index=skin_index,
        skin_weight=skin_weight,
        bones=bones,
        texture=tex,
        vertex_count=vertex_count,
        triangle_count=triangle_count,
        max_weights=max_w,
        header_bones=header_bones,
    )


def mesh_to_preview(mesh: XMesh, source_x: str) -> dict:
    return {
        "vertexCount": mesh.vertex_count,
        "triangleCount": mesh.triangle_count,
        "positions": [round(x, 6) for x in mesh.positions],
        "normals": [round(x, 5) for x in mesh.normals],
        "uvs": [round(x, 5) for x in mesh.uvs],
        "indices": mesh.indices,
        "skinIndex": mesh.skin_index,
        "skinWeight": [round(x, 5) for x in mesh.skin_weight],
        "bones": [
            {"name": b.name, "parent": b.parent, "matrix": [round(x, 6) for x in b.matrix]}
            for b in mesh.bones
        ],
        "texture": mesh.texture,
        "sourceX": source_x,
        "parsedFromEngineX": True,
        "headerBones": mesh.header_bones,
        "maxWeights": mesh.max_weights,
    }
