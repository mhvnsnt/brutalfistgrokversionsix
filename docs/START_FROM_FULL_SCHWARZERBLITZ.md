# Brutal Fist: full Schwarzerblitz starter

Brutal Fist now treats the upstream Schwarzerblitz engine repository as the native starter engine, not merely as a reference.

## Source

The repository contains SchwarzerblitzEngine as a git submodule:

- URL: https://github.com/AndreaJens/SchwarzerblitzEngine.git
- tracked revision: upstream master commit 83287a2e9c5f77408e176136ecca047067a3cc24

Clone it with:

    git clone --recurse-submodules https://github.com/mhvnsnt/Brutal-Fist.git

If already cloned:

    git submodule update --init --recursive

## Two runtimes

### Native starter/runtime

SchwarzerblitzEngine/ is the complete upstream engine source checkout. Its upstream README documents a Windows/Visual Studio/DirectX 9 native build.

### Brutal Fist PWA

The PWA is the browser test/runtime layer. It uses the same engine concepts through explicit contracts in src/engine/, but it does not pretend that a browser can directly execute the Windows/DirectX C++ binary.

## Replacement plan

1. Establish the native Schwarzerblitz build as the baseline.
2. Keep the engine source and native build reproducible through the submodule.
3. Inventory native character/move/stage/resource formats.
4. Create Bannon resource adapters for those formats.
5. Replace characters first, then animations/moves, stages, effects, audio and menus.
6. Generate PSX-style Bannon assets from canonical Bannon masters.
7. Keep the PWA playable as the rapid iteration client.
8. Add a native/WASM bridge only where it provides a real feature that cannot be represented by the browser adapter.

## Asset rule

The upstream README states that the engine source is BSD 3-Clause, while its bundled game characters, stages and music are separately restricted. Brutal Fist therefore uses the engine/source as the starter foundation and replaces those game assets with assets for which Brutal Fist has rights.

Do not copy upstream restricted game assets into the Brutal Fist repository merely because the repository is public.
