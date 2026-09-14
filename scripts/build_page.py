"""Build the page, in both the forms it has to exist in.

The same template produces two outputs, because the page is served two ways and
the two hosts give it very different things.

`web/desk.html` is a **fragment**. The Claude artifact runtime wraps it in a
document of its own, supplying the doctype, a charset, a viewport, a light
`color-scheme` and a small reset. Emitting our own `<html>` there would fight it.

`public/index.html` is a **complete document** for a static host, which supplies
none of that. Shipping the fragment to Vercel would mean no charset (every
em-dash and ± in the copy mis-renders), no viewport (a phone lays the page out
at desktop width, undoing all the responsive work) and quirks mode. The shell
below reproduces exactly what the artifact runtime provides, and nothing more,
so the two builds stay visually identical.

    python -m blackout.build && python scripts/build_page.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "desk.template.html"
DATA = ROOT / "web" / "data" / "desk.json"
FRAGMENT = ROOT / "web" / "desk.html"
STANDALONE = ROOT / "public" / "index.html"

PLACEHOLDER = "__DESK_JSON__"

DESCRIPTION = (
    "For 49 hours every weekend, one venue on earth quotes your tokenized US "
    "stock. Blackout Desk measures what that exposes you to."
)

#: Mirrors the artifact runtime's own wrapper: charset, viewport, a light
#: color-scheme, zero body margin and the two resets it applies. Anything beyond
#: this would make the static build diverge from the artifact.
SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="Blackout Desk">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; font: 14px system-ui, sans-serif; background: #fafaf9; }}
  img {{ max-width: 100%; }}
  [hidden] {{ display: none !important; }}
</style>
{page}
</head>
<body>
{body}
</body>
</html>
"""


def split_head_and_body(page: str) -> tuple[str, str]:
    """Separate what belongs in <head> from what belongs in <body>.

    The template opens with its title, font links and style block, then the
    markup. Everything up to the first element of the page proper is head
    material; the rest is body.
    """
    marker = '<div class="wrap">'
    if marker not in page:
        raise SystemExit("template no longer opens the page with .wrap; update the split")
    cut = page.index(marker)
    return page[:cut].rstrip(), page[cut:]


def main() -> int:
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"{TEMPLATE.name} has no {PLACEHOLDER} placeholder")

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    # allow_nan=False: a bare NaN token would make JSON.parse reject the whole
    # payload and render the page blank. Fail the build instead.
    blob = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    page = template.replace(PLACEHOLDER, blob)

    FRAGMENT.write_text(page, encoding="utf-8")
    print(f"wrote {FRAGMENT.relative_to(ROOT)}  ({FRAGMENT.stat().st_size / 1024:.1f} KB)  fragment, for the artifact")

    head, body = split_head_and_body(page)
    STANDALONE.parent.mkdir(parents=True, exist_ok=True)
    STANDALONE.write_text(
        SHELL.format(description=DESCRIPTION, page=head, body=body), encoding="utf-8")
    print(f"wrote {STANDALONE.relative_to(ROOT)}  ({STANDALONE.stat().st_size / 1024:.1f} KB)  standalone, for the static host")
    print(f"  payload inlined: {len(blob) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
