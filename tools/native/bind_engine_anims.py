#!/usr/bin/env python3
"""Bind exported real mocap .x clips into the Schwarzerblitz character files.

Never invents motion. If a desired clip did not export, the field is left on
the already-converted Bannon GLB locomotion (idle/walkFast/running) or reported
missing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAR = ROOT / "native" / "media" / "characters" / "chara_bannon"
ANIM = CHAR / "animations"
REPORT = ROOT / "native" / "qa" / "mocap-export-report.json"

# Engine animation name -> preferred mocap clip titles (first exported wins).
ALIASES = {
    "jab": ["Combo Punch", "Body Jab Cross", "Illegal Elbow Punch", "Illegal Elbow Punch (1)", "Illegal Knee"],
    "heavy": ["Drop Kick", "Hurricane Kick", "JayKick", "Illegal Knee", "Heavy Weapon Swing"],
    "kick": ["Hurricane Kick", "JayKick", "Drop Kick", "FenceM-Kick"],
    "hitReaction": ["Hit Reaction", "Hit To Body", "Hit To Head", "Hit On The Back", "Big Rib Hit"],
    "knockdown": ["Falling Flat Impact", "Falling Forward Death", "Defeat", "Dying Backwards"],
    "block": ["Esquiva 4", "Esquiva 3", "Corkscrew Evade", "Body Block"],
    "evade": ["Corkscrew Evade", "Esquiva 4", "Ginga Backward", "Cartwheel"],
    "taunt": ["Capoeira", "Taunt", "Taunt2", "Ginga Backward", "Ginga Sideways 2"],
    "getup": ["Kip Up", "Corkscrew Kip Up"],
    "intro": ["Idle", "Box Idle", "Action Idle To Standing Idle"],
}


def main() -> None:
    if not REPORT.exists():
        raise SystemExit("Run batch_export_mocap.py first")
    data = json.loads(REPORT.read_text())
    by_name = {
        row["clip"]: row
        for row in data.get("clips") or []
        if row.get("status") == "exported"
    }
    bound = []
    missing = []
    for engine_name, candidates in ALIASES.items():
        src = None
        picked = None
        for title in candidates:
            row = by_name.get(title)
            if not row:
                continue
            path = ROOT / row["x"]
            if path.exists():
                src = path
                picked = row
                break
        if src is None:
            missing.append({"engine": engine_name, "tried": candidates})
            continue
        dest = ANIM / f"{engine_name}.x"
        shutil.copy2(src, dest)
        bound.append(
            {
                "engine": engine_name,
                "clip": picked["clip"],
                "frames": picked.get("frames"),
                "x": str(dest.relative_to(ROOT)),
            }
        )

    jab = next((b for b in bound if b["engine"] == "jab"), None)
    heavy = next((b for b in bound if b["engine"] == "heavy"), None)
    kick = next((b for b in bound if b["engine"] == "kick"), None)
    hit = next((b for b in bound if b["engine"] == "hitReaction"), None)
    down = next((b for b in bound if b["engine"] == "knockdown"), None)
    block = next((b for b in bound if b["engine"] == "block"), None)
    evade = next((b for b in bound if b["engine"] == "evade"), None)
    taunt = next((b for b in bound if b["engine"] == "taunt"), None)
    getup = next((b for b in bound if b["engine"] == "getup"), None)
    intro = next((b for b in bound if b["engine"] == "intro"), None)

    def move_block(name: str, display: str, anim: str, frames: int, rng: str, delay: int, inp: str) -> str:
        end = max(8, min(40, int(frames or 16) // 6))
        return "\n".join(
            [
                f"#MOVE {name}",
                f"#DISPLAY_NAME {display}",
                f"#RANGE {rng}",
                f"#ANIMATION {anim}",
                f"#FRAMES 0 {end}",
                "#STANCE Ground",
                f"#DELAY_AFTER_MOVE_MS {delay}",
                "#INPUT",
                inp,
                "#INPUT_END",
                "",
            ]
        )

    moves: list[str] = []
    if jab:
        moves.append(move_block("Jab", "Jab", "jab", jab["frames"] or 12, "0.0 90.0", 120, "A"))
    if heavy:
        moves.append(move_block("Heavy", "Heavy", "heavy", heavy["frames"] or 18, "0.0 110.0", 200, "B"))
    if kick:
        moves.append(move_block("Hurricane_Kick", "Hurricane_Kick", "kick", kick["frames"] or 18, "0.0 130.0", 220, "v + B"))
    if taunt:
        moves.append(move_block("Taunt", "Taunt", "taunt", taunt["frames"] or 20, "0.0 40.0", 180, "T"))
    if evade:
        moves.append(move_block("Evade", "Evade", "evade", evade["frames"] or 16, "0.0 80.0", 160, "v + T"))
    if moves:
        (CHAR / "moves.txt").write_text("\n".join(moves), encoding="ascii")

    # Keep GLB locomotion; overlay hit/knockdown/guard when real mocap exists.
    char_path = CHAR / "character.txt"
    text = char_path.read_text()
    if hit:
        n = max(4, min(20, int(hit["frames"] or 8) // 10))
        for key in (
            "HITHIGHWEAKFRONT",
            "HITMEDWEAKFRONT",
            "HITLOWWEAKFRONT",
            "HITHIGHWEAKBACK",
            "HITMEDWEAKBACK",
            "HITLOWWEAKBACK",
            "HITMEDSTRONG",
            "HITMEDSTRONGBACK",
            "HITLOWSTRONG",
            "HITLOWSTRONGBACK",
            "HITHIGHSTRONG",
            "HITHIGHSTRONGBACK",
            "HITFLIGHTSTRONG",
            "HITFLIGHTSTRONGBACK",
        ):
            text = replace_line(text, key, f"hitReaction 0 {n}")
    if down:
        n = max(6, min(40, int(down["frames"] or 8) // 6))
        for key in (
            "GROUNDEDSUPINE",
            "GROUNDEDPRONE",
            "GROUNDEDSUPINEROTATION",
            "GROUNDEDPRONEROTATION",
            "SUPINELANDING",
        ):
            text = replace_line(text, key, f"knockdown 0 {n}")
    if block:
        n = max(4, min(20, int(block["frames"] or 8) // 10))
        text = replace_line(text, "STANDGUARD", f"block 0 {n}")
        text = replace_line(text, "CROUCHGUARD", f"block 0 {n}")
    if getup:
        n = max(6, min(30, int(getup["frames"] or 8) // 8))
        text = replace_line(text, "WAKEUP", f"getup 0 {n}")
    if taunt:
        n = max(8, min(40, int(taunt["frames"] or 8) // 8))
        text = replace_line(text, "WINPOSE", f"taunt 0 {n}")
    if intro:
        n = max(8, min(60, int(intro["frames"] or 8) // 6))
        text = replace_line(text, "INTRO", f"intro 0 {n}")
    char_path.write_text(text, encoding="ascii")

    out = {
        "policy": "REAL_FBX_ONLY aliases into engine animation names",
        "bound": bound,
        "missing": missing,
    }
    (ROOT / "native" / "qa" / "engine-anim-bind.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(json.dumps({"bound": len(bound), "missing": len(missing)}, indent=2))


def replace_line(text: str, key: str, value: str) -> str:
    token = f"#{key} "
    lines = []
    for line in text.splitlines():
        if line.startswith(token):
            lines.append(f"#{key} {value}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
