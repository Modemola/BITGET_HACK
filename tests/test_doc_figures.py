"""Every figure quoted in the docs must still match the data.

The submission, the README and CLAUDE.md all quote specific numbers, and judges
read those numbers. Prose cannot be generated the way `RESEARCH_TASK.md` is, so
it drifts silently: refreshing the data moves every derived figure in the
payload while the sentences around them keep asserting last week's values.

That happened on 2026-09-14. A single new weekend moved the hit rate from 48.1%
to 46.4% and the net-of-costs figure by an order of magnitude, and five
documents kept quoting the old ones.

So each entry below pins a *labelled* figure to the payload field it came from.
When a refresh moves the data, this fails and names the file and the sentence to
fix. Add an entry whenever a doc starts quoting a new number.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "web" / "data" / "desk.json"


@pytest.fixture(scope="module")
def data() -> dict:
    if not PAYLOAD.exists():
        pytest.skip("run `python -m blackout.build` first")
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


def _get(data: dict, path: str):
    node = data
    for key in path.split("."):
        node = node[key]
    return node


#: (doc, regex capturing one number, payload path, transform, tolerance)
#: The regex must anchor on surrounding words so it cannot match a stray number.
CLAIMS: list[tuple[str, str, str, str, float]] = [
    # --- submission metrics table (what judges read most closely) ---
    ("docs/SUBMISSION.md", r"Weekend blackouts analysed \| (\d+)",
     "summary.n_windows", "int", 0),
    ("docs/SUBMISSION.md", r"Mean absolute terminal drift \| ([\d.]+)%",
     "summary.mean_abs_terminal_drift", "pct", 0.01),
    ("docs/SUBMISSION.md", r"p95 / worst terminal drift \| ([\d.]+)%",
     "summary.p95_abs_terminal_drift", "pct", 0.01),
    ("docs/SUBMISSION.md", r"p95 / worst terminal drift \| [\d.]+% / ([\d.]+)%",
     "summary.worst_terminal_drift", "pct", 0.01),
    ("docs/SUBMISSION.md", r"Weekends ending beyond ±1% \| (\d+)%",
     "summary.share_exceeding_1pct", "pct0", 1),
    ("docs/SUBMISSION.md", r"Hit rate fading the premium \| ([\d.]+)%",
     "verdict.hit_rate", "pct", 0.05),
    ("docs/SUBMISSION.md", r"Net per weekend at 10bp round-trip \| −([\d.]+)%",
     "verdict.net_at_10bp", "negpct", 0.005),
    ("docs/SUBMISSION.md", r"Scheduled rate decisions inside a blackout \| (\d+) of",
     "calendar_stats.overlaps", "int", 0),
    ("docs/SUBMISSION.md", r"Scheduled rate decisions inside a blackout \| \d+ of (\d+)",
     "calendar_stats.events_considered", "int", 0),

    # The convergence rate went stale silently: measured on 27 weekends, it
    # stayed at 85% in five sentences after a refresh took the sample to 28 and
    # the figure to 79%. It is the number the whole finding is built to
    # overturn, so it is pinned everywhere it is quoted.
    ("docs/SUBMISSION.md", r"converged at the reopen \*\*(\d+)%\*\*",
     "verdict.converged_share", "pct0", 1),
    ("docs/SUBMISSION.md", r"The (\d+)% convergence figure",
     "verdict.converged_share", "pct0", 1),
    ("docs/SUBMISSION.md", r"the (\d+)% convergence figure to be",
     "verdict.converged_share", "pct0", 1),
    ("docs/FINDINGS.md", r"moved toward zero at the reopen \*\*(\d+)%\*\*",
     "verdict.converged_share", "pct0", 1),
    ("docs/FINDINGS.md", r"It was not, because a (\d+)%",
     "verdict.converged_share", "pct0", 1),

    # --- submission prose ---
    ("docs/SUBMISSION.md", r"returns a \*\*([\d.]+)%\*\* hit rate",
     "verdict.hit_rate", "pct", 0.05),
    ("docs/SUBMISSION.md", r"\*\*−([\d.]+)%\*\* per weekend after 10bp",
     "verdict.net_at_10bp", "negpct", 0.005),
    ("docs/SUBMISSION.md", r"the observed \*\*([\d.]+)% mean\*\*",
     "summary.mean_abs_terminal_drift", "pct", 0.01),
    ("docs/SUBMISSION.md", r"\*\*([\d.]+)% worst\*\* weekend divergence",
     "summary.worst_terminal_drift", "pct", 0.01),
    ("docs/SUBMISSION.md", r"\*\*Research validation \(observed\).\*\* ([\d,]+) hourly bars",
     "coverage.bars", "int_comma", 0),

    # --- README and project instructions ---
    ("README.md", r"(\d+) weekend blackouts", "summary.n_windows", "int", 0),
    ("CLAUDE.md", r"The honest sample is (\d+) weekends", "summary.n_windows", "int", 0),
    ("docs/RESEARCH_TASK.md", r"With (\d+) weekend blackouts the range is",
     "summary.n_windows", "int", 0),
    ("docs/FINDINGS.md", r"The sample is (\d+) weekends", "summary.n_windows", "int", 0),
]

#: Hedge figures live in a list, not at a fixed path, so they get their own
#: check. The data refresh on 2026-09-14 moved BTC's correlation and the
#: submission kept quoting the old one - exactly the drift CLAIMS exists to stop.
HEDGE_CLAIMS = [
    ("docs/SUBMISSION.md", r"BTC hedge: correlation / variance removed \| \+([\d.]+) /",
     "BTC-USD", "correlation", 0.01),
    ("docs/SUBMISSION.md", r"BTC hedge: correlation / variance removed \| \+[\d.]+ / (\d+)%",
     "BTC-USD", "risk_reduction", 1.0),
]


def _expected(kind: str, raw) -> float:
    if kind == "int":
        return float(raw)
    if kind == "int_comma":
        return float(raw)
    if kind == "pct":
        return float(raw) * 100
    if kind == "pct0":
        return round(float(raw) * 100)
    if kind == "negpct":
        return abs(float(raw)) * 100
    raise ValueError(kind)


def _parse(kind: str, text: str) -> float:
    return float(text.replace(",", ""))


@pytest.mark.parametrize("doc,pattern,path,kind,tol", CLAIMS,
                         ids=[f"{d.split('/')[-1]}:{p[:38]}" for d, p, _, _, _ in CLAIMS])
def test_documented_figure_matches_the_data(data, doc, pattern, path, kind, tol):
    text = (ROOT / doc).read_text(encoding="utf-8")
    match = re.search(pattern, text)
    assert match, (
        f"{doc} no longer contains the sentence this guard anchors on "
        f"(/{pattern}/). Either restore it or update CLAIMS - do not delete the "
        f"guard, it is what stops the docs quoting stale numbers."
    )
    documented = _parse(kind, match.group(1))
    expected = _expected(kind, _get(data, path))
    assert documented == pytest.approx(expected, abs=tol), (
        f"{doc} says {match.group(0)!r} but {path} is now {expected:.4g}. "
        f"The data moved and the prose did not."
    )


def test_every_claim_points_at_a_real_payload_field(data):
    """A guard aimed at a field that no longer exists protects nothing."""
    for doc, pattern, path, _, _ in CLAIMS:
        try:
            _get(data, path)
        except KeyError:
            pytest.fail(f"CLAIMS entry for {doc} targets missing payload field {path}")


def test_docs_do_not_call_the_premium_an_arbitrage():
    """The one phrasing the product exists to prevent.

    Stated as a project convention in CLAUDE.md; enforced here so it cannot creep
    into copy that a reader would take at face value.
    """
    # S2_BRIEF.md is Bitget's own rules text, reproduced verbatim; its
    # "Arbitrage" sub-theme name is theirs, not our copy.
    ours = [p for p in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md"))
            if p.name != "S2_BRIEF.md"]

    # The dangerous claim is that the premium *is* an opportunity. Verb forms
    # ("arbitraged away", "tried to arbitrage") describe a mechanism or our own
    # abandoned attempt and are fine.
    asserts_opportunity = re.compile(
        r"(?<!not )(?<!not an )\b(is|are|was|remains?)\s+(a|an)\s+(real\s+)?arbitrage\b"
        r"|\barbitrage opportunity\b", re.I)
    denial = re.compile(r"\bnot (an?|a real) arbitrage\b|\bis not\b|\bnever\b|\bno longer\b", re.I)
    # Reported speech: describing the mistake someone else makes is the point of
    # several passages, and is the opposite of asserting it ourselves.
    attributed = re.compile(
        r"\b(will call it|calls? it|read(s|ing)? it as|treats? it as|mistakes? it for|"
        r"assumes?|everyone|competing tool|other tools?|would call)\b", re.I)

    offenders = []
    for path in ours:
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            if not asserts_opportunity.search(line):
                continue
            # Prose wraps, so the correction often sits on the next line
            # ("...will call it an arbitrage opportunity. Blackout Desk tells /
            # the trader it is information"). Judge a small window, not one line.
            window = " ".join(lines[max(0, n - 2): n + 2])
            if denial.search(window) or attributed.search(window):
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:90]}")
    assert not offenders, (
        "copy describes the weekend premium as an arbitrage opportunity:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("doc,pattern,instrument,field,tol", HEDGE_CLAIMS,
                         ids=[f"{i}:{f}" for _, _, i, f, _ in HEDGE_CLAIMS])
def test_documented_hedge_figure_matches_the_data(data, doc, pattern, instrument, field, tol):
    row = next((h for h in data["hedges"] if h["instrument"] == instrument), None)
    assert row, f"{instrument} is no longer priced in the payload"

    match = re.search(pattern, (ROOT / doc).read_text(encoding="utf-8"))
    assert match, f"{doc} no longer contains the hedge sentence this guard anchors on"

    documented = float(match.group(1))
    expected = row[field] * (100 if field == "risk_reduction" else 1)
    assert documented == pytest.approx(expected, abs=tol), (
        f"{doc} says {match.group(0)!r} but {instrument}.{field} is now {expected:.4g}"
    )
