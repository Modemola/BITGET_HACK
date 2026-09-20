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


def test_every_token_is_defined_or_has_a_fallback(style, page):
    """A token with neither a definition nor a fallback renders as nothing.

    `var(--i, 0)` is fine and deliberate: the stagger index is set per element as
    an inline style, so the fallback is what makes the rule safe when it is not.
    A bare `var(--x)` with no definition is the classic unreadable-page bug.
    """
    bare = _bare_root(style)
    missing = [
        name for name, fallback in re.findall(r"var\(\s*(--[\w-]+)\s*(,)?", page)
        if not fallback and name not in bare
    ]
    assert not missing, (
        f"used with neither a :root definition nor a fallback: {sorted(set(missing))}"
    )


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


def test_nothing_rests_invisible(style):
    """A resting state must be the visible one.

    Entrance animations legitimately start from opacity 0 — but only inside a
    keyframe, never as a base style. The difference matters: a keyframe start
    still leaves content on screen if the animation never runs, whereas a rule
    that sets opacity 0 and waits for something hides it permanently when that
    something fails.
    """
    without_keyframes = re.sub(
        r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", style, flags=re.S)

    offenders = []
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", without_keyframes):
        selector, body = rule.group(1).strip(), rule.group(2).replace(" ", "")
        if "opacity:0" not in body:
            continue
        # A ::before / ::after is decoration by construction — it holds no
        # readable content, so hiding it until hover conceals nothing.
        if "::before" in selector or "::after" in selector:
            continue
        offenders.append(selector.splitlines()[-1].strip())
    assert not offenders, (
        "these rules hide real content at rest; if the animation never runs it "
        f"stays hidden: {offenders}"
    )


def test_entrance_animations_hold_their_end_state(style):
    """Without `both` an element can snap back to its pre-animation state."""
    entrances = re.findall(r"\.enter[\w-]*\{animation:([^}]*)\}", style)
    assert entrances, "the entrance sequence is gone"
    for decl in entrances:
        assert "both" in decl or "forwards" in decl, \
            f"entrance animation does not hold its end state: {decl.strip()}"


def test_the_entrance_is_over_quickly(style):
    """The first still frame is what a thumbnail and a skimming reader get.

    Measures the entrance only. The beacon is an infinite ambient loop with a
    deliberately slow cycle and has nothing to do with how long the page takes
    to settle.
    """
    entrance = re.findall(
        r"\.(?:enter[\w-]*|drift-line)\{[^}]*?animation:\s*[\w-]+\s+([\d.]+)s[^}]*\}",
        style)
    assert entrance, "the entrance sequence is gone"
    delays = [float(d) for d in re.findall(r"animation-delay:\s*([\d.]+)s", style)]
    # The staggered rail delay is expressed in calc(); its worst case is the
    # last of seven items.
    stagger = re.search(r"calc\(var\(--i,\s*0\)\s*\*\s*(\d+)ms\s*\+\s*(\d+)ms\)", style)
    if stagger:
        delays.append((6 * int(stagger.group(1)) + int(stagger.group(2))) / 1000)

    worst = (max(delays) if delays else 0) + max(float(d) for d in entrance)
    assert worst <= 2.4, f"the entrance still runs at {worst:.2f}s; keep it brief"


#: Selectors whose transitions are ambient rather than a response to input. A
#: lattice cell cooling after the pointer leaves is meant to linger — that trail
#: is the effect — but it still has to be bounded.
DECORATIVE = ("lattice",)


def test_ui_transitions_stay_brief(style):
    """A transition on a control must not lag behind the person using it.

    Decoration is held to a looser bound: a cell fading back over a second reads
    as cooling, where the same duration on a button reads as broken.
    """
    slow_controls, slow_decoration = [], []
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", style):
        selector, body = rule.group(1).strip(), rule.group(2)
        for d in re.findall(r"transition:[^;}]*?([\d.]+)s", body):
            seconds = float(d)
            decorative = any(token in selector for token in DECORATIVE)
            if decorative and seconds > 1.5:
                slow_decoration.append((selector.splitlines()[-1].strip(), seconds))
            elif not decorative and seconds > 0.6:
                slow_controls.append((selector.splitlines()[-1].strip(), seconds))

    assert not slow_controls, \
        f"these transitions lag the person driving them: {slow_controls}"
    assert not slow_decoration, \
        f"ambient transitions are unbounded: {slow_decoration}"


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


def test_no_stray_control_characters_survive_into_a_build():
    """The backslash-eating trap, caught at the only place it shows.

    A CSS escape for the minus sign was eaten in transit and left U+0091 --
    an invisible control character -- followed by a literal "2". Every open
    accordion on the page rendered a stray digit where its toggle should be.

    Nothing else could see it. The HTML validated, the stylesheet parsed, jsdom
    rendered the element, and the whole suite passed; the character has no
    visible width in an editor and greps for it do not occur to anyone. So the
    check is mechanical: no control or format characters in any build, ever,
    except the whitespace that belongs there.
    """
    import unicodedata

    for name in ("web/desk.template.html", "web/desk.html", "public/index.html"):
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        offenders = []
        for index, char in enumerate(text):
            if char in "\n\r\t":
                continue
            if unicodedata.category(char) in ("Cc", "Cf"):
                line = text[:index].count("\n") + 1
                offenders.append(
                    f"{name}:{line}: U+{ord(char):04X} in "
                    f"{text[max(0, index - 40):index + 20]!r}"
                )
        assert not offenders, (
            "control characters in a shipped build -- almost always an escape "
            "eaten in transit:\n  " + "\n  ".join(offenders)
        )


def test_no_payload_figure_is_hand_written_into_the_page():
    """The convention that has been broken twice, now checked.

    CLAUDE.md says never inline a figure into the page by hand, because a data
    refresh leaves the literal contradicting the number beside it. The prompt
    sent to the language layer told the model to "State the sample size (27
    weekend blackouts)" while the payload said 28 -- so the one scored feature
    that talks to a judge in sentences was instructed to misreport the sample.

    Nothing caught it: the page renders, the figure appears nowhere on screen,
    and the model dutifully repeats whatever the prompt says.
    """
    import json

    payload = json.loads((ROOT / "web" / "data" / "desk.json").read_text(encoding="utf-8"))
    template = (ROOT / "web" / "desk.template.html").read_text(encoding="utf-8")

    # The figures most likely to be transcribed, and most damaging when stale.
    watched = {
        "summary.n_windows": payload["summary"]["n_windows"],
        "coverage.bars": payload["coverage"]["bars"],
    }
    # A near-miss is the tell: the exact value could be coincidence, but the
    # value the payload held *last* refresh appearing as a literal is a stale
    # transcription. Check a small neighbourhood around each.
    offenders = []
    for path, value in watched.items():
        for candidate in range(value - 3, value + 4):
            if candidate <= 0:
                continue
            for line_no, line in enumerate(template.splitlines(), 1):
                if "D." in line or "test" in line.lower():
                    continue  # a line that reads the payload is the correct form
                if re.search(rf"\b{candidate}\b\s*(weekend|weekends|hourly|bars)", line):
                    offenders.append(f"desk.template.html:{line_no}: {line.strip()[:88]}")

    assert not offenders, (
        "a figure is hand-written into the page instead of read from the payload "
        "(see CLAUDE.md):\n  " + "\n  ".join(offenders)
    )


def test_type_sizes_come_from_the_scale(style):
    """Sizes are tokens, not literals.

    The page carried 22 distinct font sizes, a dozen of them half a pixel apart:
    11/11.5/12/12.5 all labelling things and 13.5/14/14.5/15/15.5 all setting
    body copy. None of those differences is visible on its own, and together
    they are why the page stopped reading as one system. Literals are allowed
    only where a token is being defined or a breakpoint deliberately overrides
    one.
    """
    tokens = style[style.index(":root{"):style.index("}", style.index(":root{"))]
    literals = []
    for line_no, line in enumerate(style.splitlines(), 1):
        if "--t-" in line or "--d-" in line:
            continue                      # the scale's own definitions
        for match in re.finditer(r"font-size:([\d.]+)px", line):
            literals.append(f"line {line_no}: {match.group(0)} in {line.strip()[:70]}")
    # The two masthead sizes at phone width are a deliberate override: both drop
    # to the same value so the clock cannot outsize the product name.
    allowed = 2
    assert len(literals) <= allowed, (
        f"{len(literals)} literal font sizes; use a --t-* or --d-* token:\n  "
        + "\n  ".join(literals)
    )


def test_the_display_face_is_never_asked_for_a_weight_it_lacks(style):
    """Instrument Serif ships one weight, and synthesising the rest looks it.

    `.sec-head h2` asked for 500, so every section heading down the page was
    algorithmically smeared by the browser rather than set. Nothing failed --
    synthetic bold renders, it is just ugly -- and it was on the page's most
    repeated heading.
    """
    offenders = []
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", style):
        if "var(--display)" not in body:
            continue
        weight = re.search(r"font-weight:(\d+)", body)
        if weight and weight.group(1) != "400":
            offenders.append(f"{selector.strip()[:60]} -> font-weight:{weight.group(1)}")
    assert not offenders, (
        "the display face has only weight 400; these would be synthesised:\n  "
        + "\n  ".join(offenders)
    )


def test_the_page_cannot_scroll_sideways(style):
    """The lattice is wider than the page on purpose, and nothing clipped it.

    Inset -30% on each side so the skewed grid bleeds past the masthead, it
    extended the document instead: 1163px of scrollable width behind a 485px
    viewport, so every panel sat cut off to the right and the whole page slid
    horizontally. Measured with a real browser at the time; pinned here as the
    rule that fixed it, because CI has no browser.
    """
    root = re.search(r"html\{([^}]*)\}", style)
    assert root, "no html rule; the horizontal overflow clip is gone"
    assert re.search(r"overflow-x:\s*(clip|hidden)", root.group(1)), (
        "html no longer clips horizontal overflow, so the lattice's bleed will "
        "make the whole page scroll sideways again"
    )


def test_the_rail_travels_rather_than_teleports(style, page):
    """Clicking a tool used to jump with no travel and no arrival.

    Three parts have to stay together or the effect is worse than none: the
    scroll has to animate, the destination has to mark itself so the eye knows
    where it landed, and both have to disappear for a reader who has asked for
    less motion.
    """
    assert re.search(r"html\{[^}]*scroll-behavior:\s*smooth", style), \
        "the rail teleports again; html no longer scrolls smoothly"

    assert "@keyframes arrive-sweep" in style, "the arrival sweep is gone"
    assert "@keyframes arrive-mark" in style, "the arrival mark is gone"
    assert ".arrived::before" in style, "nothing draws the arrival"

    # The cue must not be able to rest as a solid bar across a section.
    rest = re.search(r"\.arrived::before\{([^}]*)\}", style)
    assert rest and "transform:scaleX(0)" in rest.group(1).replace(" ", ""), \
        "the arrival bar has no hidden resting state; with animations off it " \
        "would sit permanently across the section"

    reduced = re.findall(r"@media\s*\(prefers-reduced-motion:reduce\)\s*\{(.*?)\n\}",
                         style, re.S)
    assert any("scroll-behavior:auto" in block for block in reduced), \
        "smooth scrolling is not switched off for reduced motion"

    # And the script must not add the cue when the reader has asked for stillness.
    assert "prefers-reduced-motion" in page and "initRail" in page, \
        "the rail script no longer checks the motion preference"
