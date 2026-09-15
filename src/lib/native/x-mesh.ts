export type PreviewBone = {
  name: string;
  parent: number;
  matrix: number[];
};

export type PreviewMesh = {
  vertexCount: number;
  triangleCount: number;
  positions: ArrayLike<number>;
  normals: ArrayLike<number>;
  uvs: ArrayLike<number>;
  indices: ArrayLike<number>;
  skinIndex: ArrayLike<number>;
  skinWeight: ArrayLike<number>;
  bones: PreviewBone[];
  texture: string;
  sourceX: string;
  parsedFromEngineX?: boolean;
  headerBones?: number;
  maxWeights?: number;
};

export type AnimTrack = {
  r?: number[][];
  t?: number[][];
};

export type ClipJson = {
  clip: string;
  cat?: string;
  fps: number;
  duration: number;
  frames?: number;
  tracks: Record<string, AnimTrack>;
  x?: string;
  source?: string;
};

export type EngineStatus = {
  character: string;
  policy: string;
  sourceGlb: string;
  mesh: {
    file: string;
    vertices: number;
    triangles: number;
    bones: number;
    headerBones?: number;
    xBytes: number;
    scale: number;
    texture?: string;
  };
  engine: {
    executableLoads: string;
    getMesh?: string;
    roster: string;
    path: string;
    outfit?: string;
    installed: boolean;
    win32Note?: string;
  };
  mocap: Record<string, number>;
  bound: Array<{ engine: string; clip: string; frames?: number; x?: string }>;
  missing?: Array<{ engine: string; tried: string[] }>;
  clips: Array<{
    clip: string;
    cat?: string;
    status?: string;
    viewer?: string;
    source?: string;
    frames?: number;
  }>;
};
