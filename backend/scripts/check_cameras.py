"""
Karabük FWI — host camera diagnostic.

A pure-OpenCV probe that reports which local camera indices are
visible from THIS process and whether each one can deliver an
actual frame. Useful when the Monitoring tab in the dashboard
shows an "unavailable" state and you need to find out *why* — a
permission problem, a wrong DSHOW index, the device already in
use, or simply Docker not having passthrough.

Usage
-----
    # from the project root
    python backend/scripts/check_cameras.py

    # probe a specific number of indices (default 4)
    python backend/scripts/check_cameras.py --max-index 8

The script never starts a long-running capture loop — every probe
is opened and immediately released. Safe to run alongside the
backend.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ``src.*`` and ``configs.*`` importable when invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring import cameras as cams  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-index",
        type=int,
        default=4,
        help="Number of OpenCV indices to probe (0..N-1). Default 4.",
    )
    args = ap.parse_args()

    runtime = cams.runtime_context()
    print("--- runtime ---")
    print(f"  host_os                        : {runtime['host_os']}")
    print(f"  in_docker                      : {runtime['in_docker']}")
    print(f"  camera_passthrough_supported   : {runtime['camera_passthrough_supported']}")
    if runtime["in_docker"] and not runtime["camera_passthrough_supported"]:
        print(
            "  [HINT] Cameras are not reachable from inside this Docker "
            "container on a Windows host. Run this script (and the "
            "backend) directly on your host instead."
        )
    print()

    print(f"--- probing OpenCV indices 0..{args.max_index - 1} ---")
    devices = cams.discover_devices(max_index=args.max_index)
    if not devices:
        print(
            "  [FAIL] No probe results returned. opencv-python may be "
            "missing from this environment."
        )
        return 1

    for d in devices:
        idx = d["index"]
        opened = d["opened"]
        flag = "OK" if opened else "--"
        assigned = d.get("assigned_to") or "(unassigned)"
        if opened:
            print(
                f"  [{flag}] index={idx}  {d['width']}x{d['height']} "
                f"@ ~{d['fps']}fps  -> role: {assigned}"
            )
        else:
            print(
                f"  [{flag}] index={idx}  could not open  -> role: {assigned}"
            )

    opened_count = sum(1 for d in devices if d["opened"])
    print()
    print(f"--- summary ---")
    print(f"  opened_devices : {opened_count} / {len(devices)}")
    print(f"  current mapping: {[(c.cam_id, c.index) for c in cams.CAMERAS.values()]}")
    if opened_count == 0 and not runtime["in_docker"]:
        print(
            "  [HINT] No OpenCV indices opened on this host. Possible causes:\n"
            "         - the camera app/another process holds the device\n"
            "         - Windows privacy settings block camera access\n"
            "         - no camera is connected\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
