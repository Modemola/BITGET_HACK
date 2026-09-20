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


def test_the_beacon_is_attached_to_the_rendered_lane(rendered):
    """The animation is CSS, but the class it hooks is emitted by drawTimeline.

    A guard that only reads the stylesheet keeps passing while nothing animates,
    which is exactly what happened when this was first checked.
    """
    beacon = rendered["beacon"]
    assert beacon["lanes"] == 1, \
        f"expected exactly one lit lane carrying the beacon, found {beacon['lanes']}"
    assert beacon["segments"] > 10, \
        "the lit lane carries the beacon class but has no segments inside it"


def test_the_interactions_actually_respond(rendered):
    """Markup being present proves nothing; a handler that throws looks identical.

    Every static check stayed green through a syntax error that left the whole
    page dead, so the pointer handlers are dispatched here rather than inspected.
    """
    inter = rendered["interactions"]
    assert "error" not in inter, f"an interaction threw: {inter.get('error')}"

    strip = inter["stripHover"]
    assert strip["cursorShown"], "hovering the week strip shows no crosshair"
    assert strip["tipShown"], "hovering the week strip shows no readout"
    assert strip["regimeNamed"], \
        "the readout says 'outside the calendar' for a point inside the strip"

    drift = inter["driftHover"]
    assert drift["tipShown"], "hovering the drift chart shows no readout"
    assert drift["quotesQuantiles"], "the drift readout does not quote the distribution"

    assert inter["clickToScrub"], "clicking the week strip does not move the desk"
    assert inter["positionRecomputes"], "editing the position changes nothing"


def test_the_lattice_is_decoration_that_stays_cheap_and_out_of_the_way(rendered):
    """Texture behind the masthead, not a second application.

    The component this borrows from rendered 150x100 cells, each carrying an
    animation listener — fifteen thousand nodes for a background. A page that
    janks before it impresses has spent its budget badly, so the count is capped
    here and the hover is pure CSS.
    """
    lattice = rendered["lattice"]
    assert lattice["cells"] > 100, "the lattice did not build"
    assert lattice["cells"] <= 1200, (
        f"the lattice built {lattice['cells']} nodes; keep background decoration "
        "cheap or it costs more than it returns"
    )
    assert lattice["inHeader"], "the lattice escaped the masthead"
    assert not lattice["swallowsStrip"], \
        "the lattice contains the week strip's pointer target and would swallow it"


def test_magnitude_bars_are_honest(rendered):
    """A bar that overruns its track, or leans the wrong way, misreads the data.

    These sit beside signed figures, so the side of centre is the sign and the
    distance from it is the magnitude. Getting either wrong tells a trader the
    opposite of what the number says.
    """
    bars = rendered["bars"]
    assert bars["diverging"] > 0 and bars["magnitude"] > 0, "the bars did not render"
    assert not bars["outOfTrack"], \
        f"bars overrun their track: {bars['outOfTrack'][:4]}"
    assert bars["signsMatchValues"], \
        "a diverging bar leans opposite to the figure printed beside it"


def test_every_tool_has_a_numbered_section(rendered):
    """The rail and the page should reinforce each other, not disagree."""
    assert rendered["sectionNumbers"] == rendered["tools"], (
        f"{rendered['tools']} tools in the rail but "
        f"{rendered['sectionNumbers']} numbered sections"
    )


def test_the_position_field_fits_the_figure_it_states(rendered):
    """The heading must not clip the number every panel below it is built on.

    At a fixed 5.2ch the default rendered as "$250,00" -- the page stating a
    position ten times smaller than the one the exposure, the hedge costs and
    the language layer were all computed from. Nothing caught it: the value was
    correct everywhere it was *used*, and only the one place it was *displayed*
    was wrong, which no assertion about the number could ever see.
    """
    field = rendered["position"]
    assert field, "the editable position field is gone"
    assert field["value"], "the field renders empty"

    # Width is set from the value's length by initPosition; a stylesheet default
    # that never gets updated would show up here as a missing or short width.
    assert field["width"].endswith("ch"), (
        f"position width is {field['width']!r}; it should be sized in ch from "
        "the value's length, not left to a fixed rule"
    )
    assert field["ch"] >= field["chars"], (
        f"the field is {field['ch']}ch wide but holds {field['chars']} characters "
        f"({field['value']!r}) - the figure in the heading is being clipped"
    )

def test_the_copy_reads_like_a_person_wrote_it(rendered):
    """Two tells, checked against the rendered text rather than the source.

    Em dashes strewn through prose, and a file path handed to a reader as
    provenance when they have no checkout to open it in. The dash also has a
    legitimate job here - it is what a formatter returns for a value that could
    not be computed - so a hit is either prose to rewrite or a null in the
    payload, and both are worth knowing about.
    """
    dashes = rendered["copy"]["emDashes"]
    assert not dashes, (
        "em dashes in the rendered copy. If a hit is prose, rewrite it; if it "
        "is a lone placeholder, the payload carries a null that should not be "
        "there. Hits: " + " | ".join(dashes)
    )

    paths = rendered["copy"]["filePaths"]
    assert not paths, (
        "file paths shown to a reader who has no checkout to open them in; "
        f"link to the thing itself instead. Hits: {paths}"
    )
