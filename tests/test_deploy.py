"""The page ships to two hosts that give it very different things.

`web/desk.html` is a fragment: the Claude artifact runtime wraps it in a
document, so emitting our own would fight it. `public/index.html` is a complete
document, because a static host supplies nothing.

Getting that backwards is silent in both directions. A fragment on a static host
renders without a charset (every em-dash and plus-minus in the copy breaks) and
without a viewport (a phone lays it out at desktop width, undoing every
responsive rule). A full document handed to the artifact runtime nests one
document inside another.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "web" / "desk.html"
STANDALONE = ROOT / "public" / "index.html"
VERCEL = ROOT / "vercel.json"


def _read(path: pathlib.Path) -> str:
    if not path.exists():
        pytest.skip(f"run `python scripts/build_page.py` first ({path.name} missing)")
    return path.read_text(encoding="utf-8")


def _payload(html: str) -> dict:
    blob = re.search(r'<script id="desk-data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    return json.loads(blob.replace(chr(60) + chr(92) + "/", "</"))


@pytest.fixture(scope="module")
def fragment() -> str:
    return _read(FRAGMENT)


@pytest.fixture(scope="module")
def standalone() -> str:
    return _read(STANDALONE)


def test_the_artifact_build_stays_a_fragment(fragment):
    """The runtime supplies the document; ours must not."""
    lowered = fragment.lower()
    for tag in ("<!doctype", "<html", "<body"):
        assert tag not in lowered, \
            f"{tag} in the artifact build would nest a document inside the runtime's"


def test_the_static_build_is_a_complete_document(standalone):
    lowered = standalone.lower()
    assert lowered.lstrip().startswith("<!doctype html>")
    assert "<html lang=" in lowered
    assert lowered.rstrip().endswith("</html>")


def test_the_static_build_declares_a_charset(standalone):
    """Without it the em-dashes and plus-minus signs throughout the copy break."""
    head = standalone[:standalone.index("</head>")]
    assert re.search(r'<meta charset="utf-8">', head, re.I), "no charset in <head>"
    assert "—" in standalone or "±" in standalone, \
        "expected non-ASCII copy, which is exactly what needs the charset"


def test_the_static_build_declares_a_viewport(standalone):
    """Without it a phone renders the page at desktop width."""
    assert re.search(r'<meta name="viewport"[^>]*width=device-width', standalone), \
        "no viewport; every responsive rule in the page would be inert on mobile"


def test_both_builds_carry_the_same_payload(fragment, standalone):
    assert _payload(fragment) == _payload(standalone), \
        "the two builds disagree; rebuild with scripts/build_page.py"


def test_head_material_lands_in_the_head(standalone):
    head_end = standalone.index("</head>")
    for needle in ("<title>", "<style>", "fonts.googleapis.com"):
        assert standalone.index(needle) < head_end, f"{needle} escaped the <head>"


def test_the_page_markup_lands_in_the_body(standalone):
    body_start = standalone.index("<body>")
    assert standalone.index('<div class="wrap">') > body_start
    assert standalone.index('id="desk-data"') > body_start


# --- hosting configuration --------------------------------------------------

@pytest.fixture(scope="module")
def vercel() -> dict:
    if not VERCEL.exists():
        pytest.skip("vercel.json missing")
    return json.loads(VERCEL.read_text(encoding="utf-8"))


def test_vercel_serves_the_standalone_build(vercel):
    assert vercel["outputDirectory"] == "public", \
        "Vercel must serve public/, which holds the complete document"
    assert vercel.get("buildCommand") is None, \
        "the page is committed already; a build container would add risk, not safety"


def test_csp_allows_the_fonts_the_page_actually_loads(vercel, standalone):
    """A CSP that blocks the font host fails silently: the type system just
    falls back and nobody sees an error."""
    csp = next(h["value"] for h in vercel["headers"][0]["headers"]
               if h["key"] == "Content-Security-Policy")
    if "fonts.googleapis.com" in standalone:
        assert "fonts.googleapis.com" in csp, "stylesheet host is not permitted"
        assert "fonts.gstatic.com" in csp, "font files host is not permitted"
    assert "'unsafe-inline'" in csp.split("script-src")[1].split(";")[0], \
        "the page's scripts are inline; blocking them leaves a dead page"


def test_security_headers_are_present(vercel):
    keys = {h["key"] for h in vercel["headers"][0]["headers"]}
    assert {"Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy"} <= keys
