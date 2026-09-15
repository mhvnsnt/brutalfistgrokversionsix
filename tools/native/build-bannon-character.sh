#!/usr/bin/env bash
# Linux counterpart of tools/native/build-bannon-character.ps1
# Canon BANNON.glb named parts → Mixamo 22-joint skinned GLB → DirectX .x
# the Schwarzerblitz executable loads via Irrlicht ISkinnedMesh (smgr->getMesh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
CHAR_ID="${1:-bannon}"
if [[ "$CHAR_ID" != "bannon" ]]; then
  echo "This sandbox currently converts the canon BANNON.glb named-part master."
  echo "Other real-GLB fighters follow the same .ps1/.sh once QA-gated."
fi

SRC_GLB="native/source/BANNON.glb"
if [[ ! -f "$SRC_GLB" ]]; then
  echo "REAL_GLB_ONLY — missing $SRC_GLB"
  exit 1
fi

python3 tools/native/rig_named_parts.py \
  --glb "$SRC_GLB" \
  --out native/source/BANNON_mixamo_rigged.glb \
  --preview native/qa/bannon-named-part-preview.png

python3 tools/native/glb_to_directx_x.py \
  --glb native/source/BANNON_mixamo_rigged.glb \
  --out native/media/characters \
  --public public/native

python3 tools/native/extract_preview_anims.py
python3 tools/native/fetch_mocap_lfs.py
python3 tools/native/batch_export_mocap.py
python3 tools/native/bind_engine_anims.py
python3 tools/native/install_into_engine.py
python3 tools/native/engine_load_rehearsal.py

python3 - <<'PY'
from pathlib import Path
cfg = Path("native/media/characters/chara_bannon/Mesh1/config.txt")
x = Path("native/media/characters/chara_bannon/Mesh1/BF_bannon.x")
engine = Path("vendor/SchwarzerblitzEngine/schwarzerblitz_engine/bin/media/characters/chara_bannon/Mesh1/BF_bannon.x")
text = cfg.read_text()
for key in ("#MESH_FILENAME", "#OUTFIT_NAME", "#CHARACTER_NAME"):
    if key not in text:
        raise SystemExit(f"Missing {key}")
if x.stat().st_size < 1024:
    raise SystemExit("Suspiciously small .x mesh")
if not engine.exists() or engine.stat().st_size != x.stat().st_size:
    raise SystemExit("Engine media slot does not hold the converted .x")
print(f"PASS native resource: {x.parent.parent}")
print(f"PASS engine slot:     {engine}")
PY
