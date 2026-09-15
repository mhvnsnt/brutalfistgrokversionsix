# Native-first playable gate

The authoritative game runtime is Schwarzerblitz native, not a browser mock.

The upstream engine is a Windows/DirectX 9/Win32 application. It loads skeletal
characters exclusively as DirectX `.x` files:

```
FK_Character::loadMeshsAndEffects
  meshfile = characterDirectory + outfitDirectory + outfitFilename
  mesh = (ISkinnedMesh*)smgr->getMesh(meshfile.c_str())
```

Brutal Fist therefore has two explicit targets:

1. Native playable: Schwarzerblitz engine + converted Bannon resources.
2. PWA preview: a browser client that inspects the **same** `.x` the exe loads.
   It is never presented as the native engine itself.

## First playable milestone — current status

| Gate | State |
| --- | --- |
| Real BANNON.glb (canon named-part, no procedural body) | PASS |
| Open-source Mixamo 22-joint rigger (rigid 1.0 weights) | PASS — no UniRig unnamed bones, no Cronenberg bind pose |
| Converted to DirectX `.x` skeletal mesh | PASS — `Mesh1/BF_bannon.x` 13,560 verts / 17,984 tris / 22 bones |
| Installed in engine media slot | PASS — `chara_bannon` is roster index 0 |
| `smgr->getMesh` rehearsal on that file | PASS — parsed + rasterized from the engine copy |
| Idle + walk + run from real Mixamo GLB clips | PASS |
| Attack / hit / knockdown from real FBX | PASS — 158 motion clips (103 Mixamo + 55 J-rig) |
| Win32 Schwarzerblitz.exe run | BLOCKED in this sandbox — the public engine repo ships headers, Irrlicht.lib, DLLs and media, not the compiled exe. Visual Studio / DirectX 9 is required to build `schwarzerblitz_engine/bin/Schwarzerblitz.exe`. |

## Pipeline

```
BANNON.glb  (15 named parts, steel mask / dreads / vale tudo)
        ↓  tools/native/rig_named_parts.py
           Mixamo 22-joint + rigid weights (open-source, no UniRig)
BANNON_mixamo_rigged.glb
        ↓  tools/native/glb_to_directx_x.py
Mesh1/BF_bannon.x + config.txt + bones.txt + character.txt
        ↓  tools/native/batch_export_mocap.py
animations/*.x   (Mixamo + J_* retarget, REAL_FBX_ONLY)
        ↓  tools/native/bind_engine_anims.py
jab.x / heavy.x / hitReaction.x / …
        ↓  tools/native/install_into_engine.py
schwarzerblitz_engine/bin/media/characters/chara_bannon
        ↓  tools/native/engine_load_rehearsal.py
parse the installed .x  →  320×240 frame  →  engine-mesh.json
```

Entry points: `tools/native/build-bannon-character.ps1` (Windows) and
`tools/native/build-bannon-character.sh` (Linux).

`BANNON_rigged.glb` is kept as historical UniRig output. It is **not** the
conversion source — its extra `bone_10`–`bone_19` joints and sewn weights
are what melted the bind pose.

Only after a Windows box compiles and runs the exe against this media tree
should the roster conversion expand past Bannon.
