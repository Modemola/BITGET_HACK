"""Load the built pages in a real DOM and assert they actually rendered.

Every other test in this suite reads the page as text. None of them can catch
the failure this file exists for.

On 2026-09-14 a stripped backslash turned a JavaScript string literal into a
syntax error. The HTML still validated. Every element was still in the markup.
The whole suite still passed. And the page rendered with both charts empty and
every control dead, because the entire script had failed to parse — which is
exactly what a reviewer reported seeing before anyone knew why.

So: parse the script, then run it, then count what appeared.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES = {
    "artifact fragment": ROOT / "web" / "desk.html",
    "static document": ROOT / "public" / "index.html",
}
SMOKE = ROOT / "scripts" / "smoke_page.mjs"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _page_script(html: str) -> str:
    """The page's own script: the last inline block, after the JSON payload."""
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert blocks, "the page carries no inline script at all"
    return blocks[-1]


@pytest.mark.parametrize("label,path", PAGES.items())
def test_the_page_script_parses(label, path):
    """A syntax error here kills every chart and every control, silently."""
    if not path.exists():
        pytest.skip(f"run `python scripts/build_page.py` first ({path.name} missing)")

    script = _page_script(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        js = pathlib.Path(tmp) / "page.js"
        js.write_text(script, encoding="utf-8")
        proc = subprocess.run([NODE, "--check", str(js)], capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, (
        f"the {label} script does not parse, so the page would render dead:\n{proc.stderr}"
    )


def _jsdom_available() -> bool:
    proc = subprocess.run([NODE, "-e", "require.resolve('jsdom')"],
                          cwd=ROOT, capture_output=True, text=True)
    return proc.returncode == 0


@pytest.fixture(scope="module")
def rendered() -> dict:
    if not _jsdom_available():
        pytest.skip("jsdom not installed; run `npm install`")
    page = PAGES["static document"]
    if not page.exists():
        pytest.skip("run `python scripts/build_page.py` first")
    proc = subprocess.run([NODE, str(SMOKE), str(page)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, f"smoke run failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_nothing_throws_on_load(rendered):
    assert not rendered["errors"], f"the page threw on load: {rendered['errors'][:3]}"


def test_both_charts_draw(rendered):
    """Empty SVGs are the visible symptom of a dead script."""
    for name, nodes in rendered["charts"].items():
        assert nodes > 10, f"the {name} chart rendered {nodes} nodes; it is empty"


def test_every_panel_fills(rendered):
    for name, children in rendered["panels"].items():
        assert children > 0, f"the {name} panel rendered nothing"


def test_the_controls_exist_and_are_wired(rendered):
    c = rendered["controls"]
    assert c["scrub"], "no time scrubber"
    assert c["scrubTrackBands"] > 10, \
        "the scrubber track is unpainted, so it reads as an anonymous slider"
    assert c["position"], "the position field has no value"
    assert c["sliders"] >= 2, "the analogue sliders are missing"


def test_the_tool_rail_is_complete_and_every_link_lands(rendered):
    """Feature depth is scored, and a dead anchor is worse than no anchor."""
    assert rendered["tools"] == 7, f"expected 7 tools in the rail, found {rendered['tools']}"
    assert not rendered["deadLinks"], f"tool rail points nowhere: {rendered['deadLinks']}"


def test_the_static_build_still_answers_questions(rendered):
    """The public URL cannot run the model, so it must at least demonstrate the
    question-to-answer flow from its own measurements."""
    assert rendered["answers"] >= 3, \
        f"only {rendered['answers']} answered questions on the static build"


def test_the_live_clock_reports_a_real_state(rendered):
    live = rendered["live"]
    assert live["regime"] and live["regime"] != "loading", "the regime never resolved"
    assert live["countdown"] and live["countdown"] != "—", "the countdown never populated"
    assert live["regimeStamp"] in {"US_CASH", "WEEKNIGHT", "BLACKOUT"}, \
        f"unexpected regime stamp: {live['regimeStamp']}"
