"""The cross-venue figures, and the docs that quote them.

`test_doc_figures.py` pins prose to `desk.json`. These figures cannot go there:
they are measured on a second venue against a second sample, and the payload is
the desk's own single-venue analysis. So they get their own guard, pinned to the
script that derives them.

The guard is not optional bookkeeping. The first version of this comparison was
run ad hoc and its numbers went straight into two documents. Rebuilding it as a
script did not reproduce them -- it had derived the qualifying weekends
separately per venue, 15 against 13, and still labelled both rows "the same
window", so part of what read as a venue difference was a sample difference. The
docs now quote what `cross_venue.py` prints, and this fails if either moves.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from cross_venue import (  # noqa: E402
    BITGET, SOLANA, cross_venue, seven_by_twentyfour_start,
)
from blackout.tools import load_series  # noqa: E402


@pytest.fixture(scope="module")
def result() -> dict:
    try:
        return cross_venue()
    except FileNotFoundError as exc:
        pytest.skip(f"{exc}; run scripts/fetch_bitget.py")


# --- the comparison is actually a comparison --------------------------------

def test_both_window_rows_cover_the_same_weekends(result):
    """The claim the whole table rests on.

    If the two venues are measured over different weekends, any difference
    between them is partly a difference of sample and the table cannot separate
    the two -- which is exactly the bug this file was written after.
    """
    window_rows = [row for name, row in result["legs"].items() if name.endswith("_window")]
    assert len(window_rows) == 2
    assert window_rows[0]["n_weekends"] == window_rows[1]["n_weekends"] \
        == result["shared_weekends"], "the window rows are not the same sample"


def test_the_cutover_is_derived_from_the_data_not_assumed(result):
    """Bitget's rToken only trades through the weekend late in the sample.

    Before the cutover the series runs on the native equity clock, so there is no
    closure window in it and nothing to compare. If that stops being true -- a
    longer history, a different listing -- the month moves and the docs must too.
    """
    by_month = result["weekend_share_by_month"][BITGET]
    cutover = result["comparable_from"]
    before = [v for m, v in by_month.items() if m < cutover]
    after = [v for m, v in by_month.items() if m >= cutover]

    assert before, "no pre-cutover months; the cutover cannot be checked"
    assert max(before) < 0.15, "a month before the cutover already traded 7x24"
    assert min(after) >= 0.15, "a month after the cutover stopped trading 7x24"


def test_a_venue_that_never_trades_weekends_is_refused_not_averaged():
    """Comparing a session-only series would silently measure nothing."""
    session_only = load_series("NVDA")          # native equity: weekdays only
    assert seven_by_twentyfour_start(session_only) is None


# --- what the docs are allowed to claim -------------------------------------

def test_dispersion_ordering_replicates_on_both_venues(result):
    """The structural claim the desk is built on, stated in both documents.

    This is the one the product cannot survive losing: if the blackout stops
    being the widest regime, the page's whole premise is wrong. Ordering, not a
    decimal -- the decimal is guarded separately below.
    """
    for venue, row in result["dispersion"].items():
        assert row["WEEKEND_BLACKOUT"] > row["US_CASH"], (
            f"{venue}: the blackout is no longer wider than the cash session, "
            "which is the claim the desk exists to report"
        )


def test_the_short_window_is_not_presented_as_confirming_the_long_one(result):
    """A sanity check on our own honesty, not on the data.

    At +6h the same venue moves by tens of points purely by shortening the
    window. Both documents must keep saying so; a refresh that narrowed the gap
    would let someone quietly upgrade the caveat into a confirmation.
    """
    full = result["legs"][f"{SOLANA}_full"]["by_horizon"]["6h"]["token_share"]
    window = result["legs"][f"{SOLANA}_window"]["by_horizon"]["6h"]["token_share"]
    assert abs(window - full) > 0.15, (
        "the short-window and full-sample +6h figures have converged; the docs "
        "call them sample-sensitive and that sentence now needs rewriting"
    )


#: (doc, regex capturing one number, how to reach it in the result, tolerance)
DOC_CLAIMS: list[tuple[str, str, tuple, float]] = [
    ("docs/FINDINGS.md", r"caps the comparable sample at \*\*(\d+) weekends\*\*",
     ("shared_weekends",), 0),
    ("docs/FINDINGS.md", r"\| Solana \(NVDAx\) \| [\d.]+% \| [\d.]+% \| \*\*([\d.]+)%\*\*",
     ("dispersion", SOLANA, "WEEKEND_BLACKOUT"), 0.01),
    ("docs/FINDINGS.md", r"\| Bitget \(RNVDAUSDT\) \| [\d.]+% \| [\d.]+% \| \*\*([\d.]+)%\*\*",
     ("dispersion", BITGET, "WEEKEND_BLACKOUT"), 0.01),
    ("docs/FINDINGS.md", r"\| NVDAx, same \d+ weekends \| \d+ \| (\d+)% \(n=\d+\)",
     ("legs", f"{SOLANA}_window", "by_horizon", "1h", "token_share"), 1),
    ("docs/FINDINGS.md",
     r"\| RNVDAUSDT, same \d+ weekends \| \d+ \| (\d+)% \(n=\d+\)",
     ("legs", f"{BITGET}_window", "by_horizon", "1h", "token_share"), 1),
    ("docs/FINDINGS.md",
     r"\| RNVDAUSDT, same \d+ weekends \| \d+ \| \d+% \(n=(\d+)\)",
     ("legs", f"{BITGET}_window", "by_horizon", "1h", "n"), 0),
    ("docs/SUBMISSION.md", r"only (\d+) weekends are covered by",
     ("shared_weekends",), 0),
    ("docs/SUBMISSION.md",
     r"blackout is the widest regime on both, ([\d.]+)% and [\d.]+%",
     ("dispersion", SOLANA, "WEEKEND_BLACKOUT"), 0.01),
    ("docs/SUBMISSION.md",
     r"blackout is the widest regime on both, [\d.]+% and ([\d.]+)%",
     ("dispersion", BITGET, "WEEKEND_BLACKOUT"), 0.01),
    ("docs/SUBMISSION.md", r"at \+1h on both \((\d+)% and \d+%\)",
     ("legs", f"{SOLANA}_window", "by_horizon", "1h", "token_share"), 1),
    ("docs/SUBMISSION.md", r"at \+1h on both \(\d+% and (\d+)%\)",
     ("legs", f"{BITGET}_window", "by_horizon", "1h", "token_share"), 1),
    ("docs/SUBMISSION.md", r"moves from (\d+)% to \d+% purely by shortening",
     ("legs", f"{SOLANA}_full", "by_horizon", "6h", "token_share"), 1),
    ("docs/SUBMISSION.md", r"moves from \d+% to (\d+)% purely by shortening",
     ("legs", f"{SOLANA}_window", "by_horizon", "6h", "token_share"), 1),
]


def _reach(node, path: tuple):
    for key in path:
        node = node[key]
    return node


@pytest.mark.parametrize("doc,pattern,path,tol", DOC_CLAIMS,
                         ids=[f"{d.split('/')[-1]}:{'.'.join(map(str, p))}"
                              for d, _, p, _ in DOC_CLAIMS])
def test_documented_cross_venue_figure_is_reproducible(result, doc, pattern, path, tol):
    match = re.search(pattern, (ROOT / doc).read_text(encoding="utf-8"))
    assert match, (
        f"{doc} no longer contains the sentence this guard anchors on "
        f"(/{pattern}/). Restore it or update DOC_CLAIMS -- do not delete the "
        f"guard; these figures have no other check on them."
    )

    raw = _reach(result, path)
    # Shares and dispersions are quoted as percentages; counts as themselves.
    expected = raw if path[-1] in ("n",) or path == ("shared_weekends",) else raw * 100
    documented = float(match.group(1))
    assert documented == pytest.approx(expected, abs=tol), (
        f"{doc} says {match.group(0)!r} but cross_venue.py now gives "
        f"{expected:.4g}. Re-run `python scripts/cross_venue.py` and fix the prose."
    )
