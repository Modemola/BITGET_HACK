"""Inline the precomputed payload into the page template.

The published artifact has no backend, so the JSON is embedded rather than
fetched. Keeping template and data separate means the page stays readable and a
rebuild is one command:

    python -m blackout.build && python scripts/build_page.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "desk.template.html"
DATA = ROOT / "web" / "data" / "desk.json"
OUT = ROOT / "web" / "desk.html"

PLACEHOLDER = "__DESK_JSON__"


def main() -> int:
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"{TEMPLATE.name} has no {PLACEHOLDER} placeholder")

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    # Compact separators keep the inlined blob small. A literal "</" inside a
    # JSON string would close the <script> element early, so neutralise it --
    # the escape is still valid JSON and parses back identically.
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")

    OUT.write_text(template.replace(PLACEHOLDER, blob), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  payload inlined: {len(blob) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
