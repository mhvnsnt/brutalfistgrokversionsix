#!/usr/bin/env python3
"""Write compact viewer JSON from the real idle/walk/run GLBs (not procedural)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "native"))
from glb_to_directx_x import load_glb, read_accessor, sanitize  # type: ignore

MESH = ROOT / "native" / "source" / "BANNON_mixamo_rigged.glb"
if not MESH.exists():
    MESH = ROOT / "native" / "source" / "BANNON.glb"
OUT = ROOT / "public" / "native" / "chara_bannon" / "clips"


def dump_glb_anim(path: Path, mesh_names: set[str]) -> dict:
    g, blob = load_glb(path)
    nodes = g.get("nodes") or []
    animation = (g.get("animations") or [None])[0]
    if not animation:
        raise ValueError(f"no animation in {path}")
    channels = animation.get("channels") or []
    samplers = animation.get("samplers") or []
    tracks: dict[str, dict] = defaultdict(lambda: {"r": [], "t": []})
    duration = 0.0
    for ch in channels:
        node = nodes[ch["target"]["node"]]
        name = sanitize(node.get("name"))
        if name not in mesh_names:
            continue
        path_k = ch["target"]["path"]
        samp = samplers[ch["sampler"]]
        times = read_accessor(g, blob, samp["input"]).reshape(-1)
        values = read_accessor(g, blob, samp["output"])
        for t, row in zip(times, values):
            duration = max(duration, float(t))
            arr = [float(x) for x in row.tolist()]
            if path_k == "rotation":
                tracks[name]["r"].append([round(float(t), 5), *[round(x, 5) for x in arr]])
            elif path_k == "translation":
                tracks[name]["t"].append([round(float(t), 5), *[round(x, 5) for x in arr]])
    return {
        "duration": duration,
        "fps": 30,
        "tracks": {k: v for k, v in tracks.items() if v["r"] or v["t"]},
    }


def main() -> None:
    g, _ = load_glb(MESH)
    mesh_names = {sanitize(n.get("name")) for n in g.get("nodes") or []}
    OUT.mkdir(parents=True, exist_ok=True)
    mapping = {
        "idle": ROOT / "native" / "source" / "idle.glb",
        "walkFast": ROOT / "native" / "source" / "walking.glb",
        "running": ROOT / "native" / "source" / "running.glb",
    }
    index = []
    for name, path in mapping.items():
        data = dump_glb_anim(path, mesh_names)
        data["clip"] = name
        data["cat"] = "locomotion"
        data["x"] = f"{name}.x"
        data["source"] = "real GLB clip"
        (OUT / f"{name}.json").write_text(json.dumps(data, separators=(",", ":")))
        index.append({"clip": name, "viewer": f"clips/{name}.json", "cat": "locomotion", "status": "exported"})
        print(name, "tracks", len(data["tracks"]), "dur", round(data["duration"], 3))
    (OUT / "locomotion.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
