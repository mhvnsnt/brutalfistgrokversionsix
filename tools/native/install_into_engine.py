#!/usr/bin/env python3
"""Install chara_bannon into the Schwarzerblitz engine media tree.

This is the folder the native executable loads:
  schwarzerblitz_engine/bin/media/characters/<id>/
  Mesh1/<file.x> via smgr->getMesh()
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "native" / "media" / "characters" / "chara_bannon"
TARGETS = [
    ROOT / "native" / "schwarzerblitz_engine" / "bin" / "media" / "characters",
    ROOT
    / "vendor"
    / "SchwarzerblitzEngine"
    / "schwarzerblitz_engine"
    / "bin"
    / "media"
    / "characters",
]


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    mesh = dst / "Mesh1"
    fp = mesh / "FightPreview.png"
    src_fp = dst / "fightPreview.png"
    if src_fp.exists() and not fp.exists():
        shutil.copy2(src_fp, fp)


def upsert_roster(roster: Path) -> None:
    lines = []
    if roster.exists():
        lines = [ln.rstrip("\n") for ln in roster.read_text().splitlines() if ln.strip()]
    kept = []
    for ln in lines:
        name = ln.split()[0].lower() if ln.split() else ""
        if name == "chara_bannon":
            continue
        kept.append(ln)
    # Bannon is roster 0. Shift any other 0 so the exe does not load two starters.
    rewritten = ["chara_bannon    0"]
    used = {0}
    for ln in kept:
        parts = ln.split()
        if len(parts) < 2:
            rewritten.append(ln)
            continue
        try:
            idx = int(parts[-1])
        except ValueError:
            rewritten.append(ln)
            continue
        if idx in used and idx >= 0:
            idx = max(used) + 1
        used.add(idx)
        rewritten.append(f"{parts[0]}    {idx}")
    roster.write_text("\n".join(rewritten) + "\n", encoding="ascii")


def main() -> None:
    x = SRC / "Mesh1" / "BF_bannon.x"
    if not x.exists():
        raise SystemExit("Run build-bannon-character first")
    installed = []
    for target in TARGETS:
        # native/schwarzerblitz_engine is a symlink into vendor; still install.
        target.mkdir(parents=True, exist_ok=True)
        copy_tree(SRC, target / "chara_bannon")
        upsert_roster(target / "roster.ini")
        installed.append(str((target / "chara_bannon").relative_to(ROOT)))
        print(f"installed {target / 'chara_bannon'}")
    print(f"mesh bytes={x.stat().st_size} slots={len(installed)}")


if __name__ == "__main__":
    main()
