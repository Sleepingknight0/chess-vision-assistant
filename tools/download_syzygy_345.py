"""Download the 3-4-5-piece Syzygy tablebase (~1 GB) from lichess.

Files live at:
  https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/<NAME>.rtbw
  https://tablebase.lichess.ovh/tables/standard/3-4-5-dtz/<NAME>.rtbz

There is no directory index, so we generate every candidate material name and
skip the non-canonical ones (they 404). Resumable: existing good files skip.
"""

from __future__ import annotations

import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from itertools import combinations_with_replacement
from pathlib import Path

BASE = "https://tablebase.lichess.ovh/tables/standard"
OUT = Path(__file__).resolve().parent.parent / "engines" / "syzygy"
PIECES = "QRBNP"  # value order → gives sorted piece strings


def candidate_names() -> list[str]:
    names: set[str] = set()
    for total in (1, 2, 3):  # non-king pieces → 3,4,5 men
        for wn in range(total + 1):
            bn = total - wn
            for wm in combinations_with_replacement(PIECES, wn):
                for bm in combinations_with_replacement(PIECES, bn):
                    names.add(f"K{''.join(wm)}vK{''.join(bm)}")
    return sorted(names)


def fetch(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "ChessVisionAssistant/1.0"})
    last: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                if r.status != 200:
                    return 0
                data = r.read()  # only write after a complete read → no partials
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0
            last = e
        except (urllib.error.URLError, ssl.SSLError, socket.timeout, ConnectionError, OSError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    print(f"  WARN giving up on {dest.name}: {last}", flush=True)
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = candidate_names()
    jobs = []
    for name in names:
        jobs.append((f"{BASE}/3-4-5-wdl/{name}.rtbw", OUT / f"{name}.rtbw"))
        jobs.append((f"{BASE}/3-4-5-dtz/{name}.rtbz", OUT / f"{name}.rtbz"))

    total_bytes = 0
    got = 0
    for i, (url, dest) in enumerate(jobs, 1):
        if dest.is_file() and dest.stat().st_size > 200:
            total_bytes += dest.stat().st_size
            got += 1
            continue
        n = fetch(url, dest)
        if n > 0:
            total_bytes += n
            got += 1
        if i % 20 == 0 or n > 500_000:
            print(
                f"[{i}/{len(jobs)}] files={got} "
                f"total={total_bytes/1e6:.1f} MB  last={dest.name if n else 'skip'}",
                flush=True,
            )
    print(f"DONE: {got} files, {total_bytes/1e6:.1f} MB in {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
