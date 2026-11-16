"""Build index.html (the NextBurn Coverage Console) with a snapshot of every result, setting and chart embedded.

Usage: python console/build_console.py [--no-images]
The page works when opened directly from disk, on GitHub Pages, or served by console/console_server.py (live mode).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_lib  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-images", action="store_true", help="leave the charts out (smaller page)")
    a = ap.parse_args(argv)
    info = console_lib.write_index(images=not a.no_images)
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
