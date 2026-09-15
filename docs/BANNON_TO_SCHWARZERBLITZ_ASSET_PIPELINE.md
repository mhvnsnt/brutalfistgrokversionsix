# Bannon -> Schwarzerblitz character replacement

## Selection law

A Brutal Fist fighter is eligible only when a real `.glb` exists in the Bannon source model bank.

Procedural Three.js / MDickie fallback bodies are excluded.

The Bannon source documents that some model entries had been incorrectly pointed at characters with no GLB and no roster entry; those are not allowed into Brutal Fist.

## Identity law

The imported fighter keeps the Bannon roster identity:

- id
- display name
- biography
- role
- DNA
- stats
- payback
- manager
- attire definitions

Only the engine representation changes.

## Animation law

Use Bannon's real animation data first:

1. GLB-embedded AnimationClips
2. Bannon mocap FBX library
3. authored move clips
4. WR3D/Unity animation conversion outputs where their source data is valid

Procedural pose synthesis is not promoted as a replacement for real animation when a real clip exists.

The Bannon repository documents a 182-FBX mocap library and a STUDIO.clips runtime library, plus authored combat clips. These are the source pools to map into Schwarzerblitz move resources.

## PSX conversion law

Canonical master -> derived PSX asset.

Never destroy or overwrite the master.

Starting targets:

- character geometry: 18k triangles or lower after QA
- texture atlas target: 256x256
- nearest filtering
- no unnecessary mipmaps
- low-resolution render target
- controlled vertex precision/quantization
- preserved skeleton and animation bindings

The target is the visual language of late-90s/early-2000s low-poly fighters: restrained geometry, low-resolution textures, strong silhouettes, and deliberately limited precision. Tekken 3's PS1 conversion is a useful reference because the port reduced character polygon counts and overall resolution to fit the hardware.

## QA gates

A character is promoted only if:

- GLB exists
- it is actually the roster character
- skin exists and deforms
- bind pose is valid
- animation clips resolve
- no procedural fallback is silently substituted
- geometry/texture budgets pass
- PSX preview is visually legible
