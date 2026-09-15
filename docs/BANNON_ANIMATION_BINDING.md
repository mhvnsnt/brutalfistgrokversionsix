# Bannon animation binding

The Bannon repository separates **model correctness** from **motion correctness**. Its MODEL_QA gate measures skinning residuals and explicitly states that clean skinning does not guarantee good motion; real idle/locomotion/strike clips still need to be wired through AnimationMixer/clip blending.

Brutal Fist follows that separation.

## Binding order

1. Load the real Bannon GLB.
2. Inspect its embedded animation names.
3. Normalize clip names into the Schwarzerblitz move/state vocabulary.
4. Resolve bone mapping from the Bannon/UniRig/Mixamo-compatible skeleton.
5. Preserve source clip timing; do not invent frames when source timing exists.
6. Blend clips through the fighter state machine.
7. Attach move frame data separately from animation playback.
8. QA deformation with a measured skinning gate before accepting motion.

## Required initial states

- idle / stance
- walk forward
- walk backward
- sidestep left/right
- crouch
- guard
- hit reaction
- knockdown
- wake-up
- jump
- light attack
- heavy attack
- throw / grapple where available

## Important

Animation names are metadata, not proof of correct motion. A clip must resolve to a real animation track and drive the intended skeleton. Missing clips are reported as missing; they are not silently replaced with a procedural animation.

The Schwarzerblitz move resource controls startup/active/recovery and collision semantics. The Bannon clip supplies the actual body motion. These remain separate so the fighting simulation can be measured independently of visual playback.
