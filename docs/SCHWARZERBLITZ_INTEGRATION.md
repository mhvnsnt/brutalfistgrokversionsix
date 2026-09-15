# Brutal Fist / Schwarzerblitz Integration

Brutal Fist is being built on top of the open-source Schwarzerblitz engine architecture, not as a 2D React mockup.

## Runtime split

- PWA / Google AI Studio: Vite + React + Three.js, fixed 60 Hz simulation.
- Native target: the SchwarzerblitzEngine gitlink, using the upstream C++ engine and native renderer.
- Parity boundary: src/engine/SchwarzerblitzCompat.ts.
- Game rules: src/engine/GameEngine.ts and data contracts in src/types.ts.
- Asset runtime: public GLB loading; no Drive OAuth is required for a public file.
- Presentation: React is menu/HUD only. It does not own combat state.

## What is already represented

- 60 Hz fixed-step simulation
- fighter neutral/startup/active/recovery/hitstun/blockstun/KO states
- frame data
- hitboxes and hurtboxes
- guard/blockstun
- pushback and body separation
- facing
- animation-state selection from GLB clips
- camera tracking of the active fighters
- mobile controls and keyboard controls
- PWA shell
- public asset loading
- Schwarzerblitz-oriented motion-input buffer

## Native parity rule

Do not replace the native Schwarzerblitz source with a new unrelated game framework.

When a browser feature is added, express it as an engine-neutral contract first, then implement the browser adapter. When the native engine is changed, map the same contract into the native/WASM adapter.

The upstream Schwarzerblitz source contains dedicated AI, effect/shader, and engine code under schwarzerblitz_engine/SchwarzerblitzEngine. The repository is retained as a gitlink so its history and licensing remain intact.

## Next integration order

1. Map native fighter/state structures into the parity contract.
2. Map native move/animation resources into Brutal Fist data.
3. Map stage/camera rules.
4. Replace starter move constants with resource-driven move definitions.
5. Add round/match flow.
6. Add training/debug instrumentation.
7. Build the native/WASM adapter without changing browser gameplay contracts.

The PWA remains the immediate playable/test target while native parity is developed.
