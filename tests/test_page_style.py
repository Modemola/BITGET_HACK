"""Invariants of the page's visual system.

Two rules carry the design, and both fail silently when broken: a token defined
only inside a dark block renders one theme's text on the other theme's ground,
and a regime block that moves a hue destroys the whole point of the regime
mechanic, which is that as everything else dims, one thing stays exactly as lit
as it was.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "desk.html"

#: Colours that carry meaning. Regime may dim a surface; it may never move these.
HUES = {"--lit", "--risk", "--ok", "--open", "--half"}


@pytest.fixture(scope="module")
def style() -> str:
    if not PAGE.exists():
        pytest.skip("run `python scripts/build_page.py` first")
    return re.search(r"<style>(.*?)</style>", PAGE.read_text(encoding="utf-8"), re.S).group(1)


@pytest.fixture(scope="module")
def page() -> str:
    if not PAGE.exists():
        pytest.skip("run `python scripts/build_page.py` first")
    return PAGE.read_text(encoding="utf-8")


def _bare_root(style: str) -> set[str]:
    block = re.search(r"^:root\{(.*?)\}", style, re.S | re.M)
    assert block, "no bare :root block"
    return set(re.findall(r"(--[\w-]+)\s*:", block.group(1)))


def test_every_token_is_defined_in_the_base_root(style, page):
    """A token defined only inside a dark block is the classic unreadable page."""
    missing = set(re.findall(r"var\((--[\w-]+)", page)) - _bare_root(style)
    assert not missing, f"used but never defined in bare :root: {sorted(missing)}"


def test_the_two_dark_blocks_stay_symmetric(style):
    """prefers-color-scheme and an explicit toggle must reach the same palette."""
    media = re.search(r"@media \(prefers-color-scheme:dark\)\{\s*"
                      r":root:not\(\[data-theme=\"light\"\]\)\{(.*?)\n  \}", style, re.S)
    attr = re.search(r':root\[data-theme="dark"\]\{(.*?)\}', style, re.S)
    assert media and attr, "a dark theme block is missing"
    drift = set(re.findall(r"(--[\w-]+)\s*:", media.group(1))) ^ \
            set(re.findall(r"(--[\w-]+)\s*:", attr.group(1)))
    assert not drift, f"dark blocks disagree on: {sorted(drift)}"


def test_body_paints_its_own_background(style):
    """A transparent body borrows the host's ground and breaks in one theme."""
    assert re.search(r"body\{[^}]*background:var\(--ground\)", style)


def test_regime_never_moves_a_hue(style):
    """Regime dims surfaces. It must not touch a colour that carries meaning.

    The mechanic only reads as "one thing stays on" if the lit accent is
    genuinely unchanged while everything around it recedes.
    """
    offenders = []
    for m in re.finditer(r"(:root[^{,]*\[data-regime=\"\w+\"\][^{]*)\{([^}]*)\}", style):
        selector, body = m.group(1).strip(), m.group(2)
        if not selector.rstrip().endswith("]"):
            continue                      # a component rule may *use* a hue
        moved = set(re.findall(r"(--[\w-]+)\s*:", body)) & HUES
        if moved:
            offenders.append(f"{selector} redefines {sorted(moved)}")
    assert not offenders, "regime blocks moved a hue:\n  " + "\n  ".join(offenders)


def test_regime_states_are_actually_defined(style):
    """The mechanic is inert without them."""
    for regime in ("WEEKNIGHT", "BLACKOUT"):
        assert f'[data-regime="{regime}"]' in style, f"no styling for {regime}"


def test_the_page_is_complete_at_rest(page):
    """Nothing may be parked invisible waiting on a scroll observer."""
    assert "opacity:0" not in page.replace(" ", ""), \
        "an element starts invisible; the first still frame must be complete"


def test_motion_is_bounded_and_opt_out(style):
    assert "prefers-reduced-motion" in style, "no reduced-motion escape hatch"
    durations = [float(d) for d in re.findall(r"transition:[^;}]*?([\d.]+)s", style)]
    assert durations, "transitions declared nowhere"
    assert max(durations) <= 0.6, f"a transition runs {max(durations)}s; keep motion brief"


def test_phone_width_is_handled(style):
    assert "max-width:640px" in style
    assert ".tl-scroll{overflow-x:auto" in style, \
        "the week strip must scroll in its own container, not the page body"
