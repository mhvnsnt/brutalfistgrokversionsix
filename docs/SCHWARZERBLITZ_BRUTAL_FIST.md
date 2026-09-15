# Brutal Fist / Schwarzerblitz integration boundary

## Goal

Brutal Fist is being built on top of the open-source Schwarzerblitz fighting-game engine, while retaining a browser/PWA target for Google AI Studio preview and mobile testing.

The upstream engine is a native C++ engine built around a custom Irrlicht/Schwarzerlicht renderer and SFML audio backend. Its documented skeletal-character path uses DirectX `.x` models and its supported runtime is Windows. The native source is retained in the `SchwarzerblitzEngine` submodule.

## Two runtime targets

### Browser/PWA target

- React/Three.js is the preview renderer.
- `GameEngine` owns the deterministic 60 Hz combat simulation.
- `SchwarzerblitzCompat.ts` is the explicit boundary between simulation and rendering.
- Google AI Studio can preview the game immediately because it is a normal web app.
- The PWA shell can be installed on a phone and launched fullscreen.

### Native Schwarzerblitz target

- `SchwarzerblitzEngine` remains the native engine reference/implementation.
- Native gameplay, collision, animation, input, camera and resource semantics should be ported/adapted into the compatibility boundary rather than duplicated as unrelated React logic.
- The browser runtime is not claimed to be the native C++ engine. It is the playable compatibility target while the native integration is developed.

## Integration rule

Do not add another fake UI/gameplay layer. New combat features belong in the engine boundary first. Rendering/UI consumes engine snapshots.

The next native integration stages are:

1. inventory/asset manifest parity;
2. fighter skeleton and animation-state parity;
3. collision/hitbox parity;
4. camera and stage-space parity;
5. input/state-machine parity;
6. native/WASM build target;
7. replace browser compatibility implementation with the native/WASM engine adapter where supported.

This keeps Brutal Fist as one game with two runtime targets instead of two unrelated prototypes.
