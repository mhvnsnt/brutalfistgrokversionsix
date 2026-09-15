#!/usr/bin/env python3
"""Replace Git LFS pointer stubs in Bannon mocap with the real FBX binaries.

Does not invent clips. Pointers that fail to download stay pointers so the
exporter can report missing_lfs instead of synthesizing motion.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import ssl

ROOT = Path(__file__).resolve().parents[2]
BANNON = ROOT / "BannonSource"
if not BANNON.exists():
    BANNON = ROOT / "vendor" / "Bannon"
FBX_ROOT = BANNON / "assets" / "mocap"
MEDIA = "https://media.githubusercontent.com/media/mhvnsnt/Bannon/main/"


def is_lfs_pointer(path: Path) -> bool:
    try:
        return path.read_bytes()[:24].startswith(b"version https://git-lfs")
    except OSError:
        return False


def fetch_one(path: Path, rel: str, ctx: ssl.SSLContext) -> tuple[str, str, int]:
    url = MEDIA + quote(rel)
    req = Request(url, headers={"User-Agent": "BrutalFistPipeline/1.0"})
    with urlopen(req, context=ctx, timeout=90) as resp:
        data = resp.read()
    if not (data.startswith(b"Kaydara FBX") or data.startswith(b"FBX")):
        return ("bad_header", rel, len(data))
    tmp = path.with_suffix(".fbx.part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return ("ok", rel, len(data))


def main() -> None:
    if not FBX_ROOT.exists():
        raise SystemExit(f"mocap folder missing: {FBX_ROOT}")
    jobs: list[tuple[Path, str]] = []
    for p in FBX_ROOT.rglob("*.fbx"):
        if is_lfs_pointer(p):
            jobs.append((p, p.relative_to(BANNON).as_posix()))
    if not jobs:
        print("no LFS pointers")
        return
    ctx = ssl.create_default_context()
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(fetch_one, p, rel, ctx) for p, rel in jobs]
        for fut in as_completed(futs):
            try:
                status, rel, info = fut.result()
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"fail {exc}")
                continue
            if status == "ok":
                ok += 1
            else:
                fail += 1
            print(f"{status:10} {rel} {info}")
    print(f"fetched {ok}/{len(jobs)} failed {fail}")


if __name__ == "__main__":
    main()
