#!/usr/bin/env python3
"""embed_model.py - splice hall_thruster_model.json into the viewer's blob.

The viewer has to open straight off the filesystem, so the model cannot be
fetch()ed (file:// requests are blocked as cross-origin). It lives inline in
<script id="model-data"> instead, the same way gridded_ion.html carries its
model. This replaces JUST that element's content and leaves the rest of the
5xx-line viewer byte-identical.

Full regen:
    python build_thruster.py hall_thruster_3D.STEP     # colored STEP
    python build_model.py    hall_thruster_model.json  # tessellate
    python embed_model.py                              # splice into the viewer

Runs on stock Python - it needs no CAD packages, so it does not need the cadenv.
"""
import re
import sys
from pathlib import Path

OPEN = '<script id="model-data" type="application/json">'
CLOSE = '</script>'


def main():
    here = Path(__file__).parent
    html_path = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "hall_thruster.html"
    json_path = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "hall_thruster_model.json"

    html = html_path.read_text(encoding="utf-8")
    blob = json_path.read_text(encoding="utf-8").strip()

    if "</script" in blob:
        raise SystemExit("model JSON contains '</script' and would break the tag")

    start = html.index(OPEN) + len(OPEN)
    end = html.index(CLOSE, start)
    old = end - start
    html = html[:start] + blob + html[end:]

    html_path.write_text(html, encoding="utf-8")
    n = len(re.findall(r'"name":', blob))
    print(f"spliced {len(blob):,} bytes ({n} components) into {html_path.name} "
          f"(was {old:,} bytes)")


if __name__ == "__main__":
    main()
