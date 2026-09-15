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


def test_the_single_theme_is_a_choice_not_an_omission(style):
    """The page commits to one dark world, so it must say so explicitly.

    Committing is legitimate here because the two themes are not equivalent
    renderings: the accent is 9.2:1 against the void and 3.6:1 against white,
    where it degrades from a lit lamp to ochre. But a page that merely *forgot*
    its light palette looks identical in the source to one that chose, so the
    declaration has to be present.
    """
    assert "color-scheme: dark" in style or "color-scheme:dark" in style, \
        "the page must declare its scheme, or form controls render for the wrong one"
    assert "prefers-color-scheme" not in style, \
        "a colour-scheme media query means the commitment was reverted by halves"
    assert "[data-theme=" not in style, \
        "a theme stamp means the commitment was reverted by halves"


def _lstar(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


def _token(style: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*:\s*(#[0-9A-Fa-f]{{6}})", style)
    assert match, f"{name} is not defined as a literal colour"
    return match.group(1)


def test_the_void_separates_from_the_page(style):
    """The hero image is a column of void, and it has to be visible.

    An earlier palette put --void 2.5 L* from --ground, below the threshold of
    noticing, so the blackout column in the week strip and the page darkening at
    the start of a blackout were both invisible in the only theme that ships.
    Contrast ratios hide this: the same pair reads 1.05:1, which sounds like a
    rounding error rather than the design failing.
    """
    gap = _lstar(_token(style, "--ground")) - _lstar(_token(style, "--void"))
    assert gap >= 6.0, (
        f"--void sits only {gap:.1f} L* from --ground; the blackout column and the "
        "regime shift will not read. Lift the ground, do not darken the void."
    )


def test_the_accent_still_burns_against_the_void(style):
    """--lit is the one thing left on when everything else goes dark."""
    void, lit = _token(style, "--void"), _token(style, "--lit")

    def relative_luminance(colour):
        h = colour.lstrip("#")
        ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted([relative_luminance(lit), relative_luminance(void)], reverse=True)
    assert (hi + 0.05) / (lo + 0.05) >= 7.0, \
        "the accent no longer reads against the void it is supposed to light"


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


def test_ui_transitions_stay_brief(style):
    """A transition responds to something a person did; it must not lag behind them."""
    durations = [float(d) for d in re.findall(r"transition:[^;}]*?([\d.]+)s", style)]
    assert durations, "transitions declared nowhere"
    assert max(durations) <= 0.6, f"a transition runs {max(durations)}s; keep motion brief"


def test_looping_animation_is_slow_enough_to_be_ambient(style):
    """An infinite loop must read as breathing, never as flashing.

    Three flashes a second is the seizure threshold, so anything looping forever
    is held well below it — and well below that again, because the point of the
    beacon is that the lane is alive, not that it is blinking for attention.
    """
    loops = re.findall(r"animation:\s*[\w-]+\s+([\d.]+)s[^;}]*infinite", style)
    assert loops, "the beacon animation is gone"
    slowest = min(float(d) for d in loops)
    assert slowest >= 1.5, \
        f"a looping animation cycles every {slowest}s; that reads as a flash"


def test_all_motion_can_be_switched_off(style):
    """Both kinds — the transitions and the infinite loop — must yield."""
    assert "prefers-reduced-motion" in style, "no reduced-motion escape hatch"

    # Brace matching across nested media queries is not worth a regex; reading a
    # window after each declaration is enough to prove the opt-out is there.
    reduced = "".join(
        style[m.end():m.end() + 400]
        for m in re.finditer(r"prefers-reduced-motion:\s*reduce", style)
    ).replace(" ", "")
    assert "animation:none" in reduced, \
        "reduced motion does not stop the looping animation"
    assert "transition:none" in reduced, \
        "reduced motion does not stop transitions"


def test_the_beacon_marks_the_lane_that_stays_lit(style):
    """The animation has to carry the argument, not decorate the page.

    It belongs to the rToken lane specifically, and it intensifies in a blackout
    because that is the moment the lane is the only thing still transmitting.
    """
    assert ".lane-lit{animation:" in style.replace(" ", ""),         "the beacon is not attached to the lit lane"
    assert re.search(r':root\[data-regime="BLACKOUT"\]\s*\.lane-lit\s*\{[^}]*animation:', style),         "the beacon does not change when the lane becomes the only one lit"


def test_phone_width_is_handled(style):
    assert "max-width:640px" in style
    assert ".tl-scroll{overflow-x:auto" in style, \
        "the week strip must scroll in its own container, not the page body"
