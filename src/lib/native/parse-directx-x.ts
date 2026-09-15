/** Minimal DirectX .x text parser for Schwarzerblitz/Irrlicht skeletal meshes. */

export type XBone = {
  name: string;
  parent: number;
  matrix: number[]; // 16 floats, DirectX row-major (translation in last row)
};

export type XMesh = {
  positions: Float32Array;
  normals: Float32Array;
  uvs: Float32Array;
  indices: Uint32Array;
  skinIndex: Uint16Array;
  skinWeight: Float32Array;
  bones: XBone[];
  textureName: string;
  vertexCount: number;
  triangleCount: number;
};

function stripComments(src: string): string {
  return src.replace(/\/\/[^\n]*/g, "");
}

function readMatrix(block: string): number[] {
  const nums = block.match(/-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+/g);
  if (!nums || nums.length < 16) return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  return nums.slice(0, 16).map(Number);
}

function extractBalanced(src: string, openIdx: number): { inner: string; end: number } {
  let depth = 0;
  for (let i = openIdx; i < src.length; i++) {
    const ch = src[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return { inner: src.slice(openIdx + 1, i), end: i + 1 };
    }
  }
  throw new Error("Unbalanced brace in .x file");
}

function parseFrames(src: string): XBone[] {
  const bones: XBone[] = [];

  const walk = (block: string, parent: number) => {
    let i = 0;
    while (i < block.length) {
      const slice = block.slice(i);
      const match = /Frame\s+([A-Za-z0-9_]+)\s*\{/.exec(slice);
      if (!match || match.index == null) return;
      const abs = i + match.index;
      const brace = block.indexOf("{", abs);
      const { inner, end } = extractBalanced(block, brace);
      const name = match[1];
      if (name !== "Root") {
        const mtxMatch = inner.match(/FrameTransformMatrix\s*\{([^}]*)\}/);
        const matrix = mtxMatch
          ? readMatrix(mtxMatch[1])
          : [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
        const idx = bones.length;
        bones.push({ name, parent, matrix });
        walk(inner, idx);
      } else {
        walk(inner, parent);
      }
      i = end;
    }
  };

  walk(src, -1);
  return bones;
}

function parseMeshBlock(
  meshInner: string,
  boneIndex: Map<string, number>,
): Omit<XMesh, "bones"> {
  const tex = meshInner.match(/TextureFilename\s*\{\s*"([^"]+)"/);
  const textureName = tex?.[1] ?? "bannon.png";

  const header = meshInner.match(/^\s*(\d+);/);
  if (!header) throw new Error("Mesh missing vertex count");
  const vertexCount = Number(header[1]);

  const vertSection = meshInner.slice(header.index! + header[0].length);
  const faceCountMatch = vertSection.match(/(\d+);(?=\s*3;)/);
  if (!faceCountMatch) throw new Error("Mesh missing face count");
  const triangleCount = Number(faceCountMatch[1]);

  const vertText = vertSection.slice(0, faceCountMatch.index);
  const vertNums = vertText.match(/-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+/g);
  if (!vertNums || vertNums.length < vertexCount * 3) throw new Error("Vertex list truncated");
  const positions = new Float32Array(vertexCount * 3);
  for (let i = 0; i < vertexCount * 3; i++) positions[i] = Number(vertNums[i]);

  const afterVerts = vertSection.slice(faceCountMatch.index! + faceCountMatch[0].length);
  const faceNums = afterVerts.match(/\d+/g);
  if (!faceNums) throw new Error("Face list truncated");
  const indices = new Uint32Array(triangleCount * 3);
  let fi = 0;
  let cursor = 0;
  while (fi < triangleCount && cursor < faceNums.length) {
    const n = Number(faceNums[cursor++]);
    for (let k = 0; k < n; k++) indices[fi * 3 + k] = Number(faceNums[cursor++]);
    fi++;
  }

  const normals = new Float32Array(vertexCount * 3);
  const nrmStart = meshInner.search(/MeshNormals\s*\{/);
  if (nrmStart >= 0) {
    const brace = meshInner.indexOf("{", nrmStart);
    const { inner } = extractBalanced(meshInner, brace);
    const nCount = inner.match(/^\s*(\d+);/);
    const nText = nCount ? inner.slice(nCount.index! + nCount[0].length) : inner;
    const nNums = nText.match(/-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+/g) ?? [];
    for (let i = 0; i < Math.min(vertexCount * 3, nNums.length); i++) normals[i] = Number(nNums[i]);
  }

  const uvs = new Float32Array(vertexCount * 2);
  const uvStart = meshInner.search(/MeshTextureCoords\s*\{/);
  if (uvStart >= 0) {
    const brace = meshInner.indexOf("{", uvStart);
    const { inner } = extractBalanced(meshInner, brace);
    const uCount = inner.match(/^\s*(\d+);/);
    const uText = uCount ? inner.slice(uCount.index! + uCount[0].length) : inner;
    const uNums = uText.match(/-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+/g) ?? [];
    for (let i = 0; i < Math.min(vertexCount * 2, uNums.length); i++) uvs[i] = Number(uNums[i]);
  }

  const skinIndex = new Uint16Array(vertexCount * 4);
  const skinWeight = new Float32Array(vertexCount * 4);
  const filled = new Uint8Array(vertexCount);
  let searchFrom = 0;
  while (true) {
    const found = meshInner.indexOf("SkinWeights", searchFrom);
    if (found < 0) break;
    const brace = meshInner.indexOf("{", found);
    if (brace < 0) break;
    const { inner, end } = extractBalanced(meshInner, brace);
    searchFrom = end;
    const nameMatch = inner.match(/"([^"]+)"/);
    if (!nameMatch) continue;
    const bi = boneIndex.get(nameMatch[1]);
    if (bi == null) continue;
    const nMatch = inner.match(/;\s*(\d+);/);
    const n = nMatch ? Number(nMatch[1]) : 0;
    if (n <= 0) continue;
    const afterCount = inner.slice(inner.indexOf(nMatch![0]) + nMatch![0].length);
    const ints = afterCount.match(/-?\d+/g) ?? [];
    const floats = afterCount.match(/-?\d+\.\d+(?:[eE][+-]?\d+)?/g) ?? [];
    const idxs = ints.slice(0, n).map(Number);
    const ws = floats.slice(0, n).map(Number);
    for (let i = 0; i < n; i++) {
      const vi = idxs[i];
      if (vi < 0 || vi >= vertexCount) continue;
      const slot = filled[vi];
      if (slot < 4) {
        skinIndex[vi * 4 + slot] = bi;
        skinWeight[vi * 4 + slot] = ws[i] ?? 0;
        filled[vi] = slot + 1;
      }
    }
  }
  for (let i = 0; i < vertexCount; i++) {
    const b = i * 4;
    const sum = skinWeight[b] + skinWeight[b + 1] + skinWeight[b + 2] + skinWeight[b + 3];
    if (sum > 1e-8) {
      skinWeight[b] /= sum;
      skinWeight[b + 1] /= sum;
      skinWeight[b + 2] /= sum;
      skinWeight[b + 3] /= sum;
    } else {
      skinWeight[b] = 1;
    }
  }

  return { positions, normals, uvs, indices, skinIndex, skinWeight, textureName, vertexCount, triangleCount };
}

export function parseDirectXText(source: string): XMesh {
  if (!source.startsWith("xof ")) throw new Error("Not a DirectX .x file");
  const text = stripComments(source);
  const meshMatch = text.match(/Mesh\s*\{/);
  if (!meshMatch || meshMatch.index == null) throw new Error("No Mesh block in .x");
  const brace = text.indexOf("{", meshMatch.index);
  const { inner } = extractBalanced(text, brace);
  const bones = parseFrames(text.slice(0, meshMatch.index));
  const boneIndex = new Map(bones.map((b, i) => [b.name, i]));
  const mesh = parseMeshBlock(inner, boneIndex);
  return { ...mesh, bones };
}

export function xMeshToPreview(mesh: XMesh, sourceX: string) {
  return {
    vertexCount: mesh.vertexCount,
    triangleCount: mesh.triangleCount,
    positions: mesh.positions,
    normals: mesh.normals,
    uvs: mesh.uvs,
    indices: mesh.indices,
    skinIndex: mesh.skinIndex,
    skinWeight: mesh.skinWeight,
    bones: mesh.bones,
    texture: mesh.textureName,
    sourceX,
    parsedFromEngineX: true,
    headerBones: mesh.bones.length,
  };
}
