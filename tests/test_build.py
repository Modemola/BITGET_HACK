"""Contract tests for the published payload.

The page has no backend, so `web/data/desk.json` is the entire truth it renders
from. Two failure modes matter more than the rest:

  * a non-finite number renders the whole page blank, because Python writes a
    bare `NaN` token that `JSON.parse` rejects outright, and
  * a hardcoded figure goes stale on the next data refresh while every derived
    number around it moves, leaving the page quietly contradicting the analysis.

Both are silent. Neither shows up as an error anyone would notice.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "web" / "data" / "desk.json"
PAGE = ROOT / "web" / "desk.html"

REQUIRED_KEYS = {
    "generated_at", "coverage", "summary", "regime_shares", "dispersion", "drift",
    "terminal_gaps", "hedges", "blackout_windows", "regime_runs", "demo", "verdict",
    "analogue_features", "analogue_feature_names", "analogue_defaults",
}


@pytest.fixture(scope="module")
def payload() -> dict:
    if not PAYLOAD.exists():
        pytest.skip("run `python -m blackout.build` first")
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


def _walk(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, node


def test_payload_carries_everything_the_page_reads(payload):
    missing = REQUIRED_KEYS - set(payload)
    assert not missing, f"page reads keys the build no longer emits: {sorted(missing)}"


def test_no_non_finite_numbers_anywhere(payload):
    """One NaN renders the entire page blank. There is no partial failure here."""
    bad = [p for p, v in _walk(payload)
           if isinstance(v, float) and not math.isfinite(v)]
    assert not bad, f"non-finite values would break JSON.parse at: {bad[:5]}"


def test_payload_text_holds_no_bare_nan_tokens():
    raw = PAYLOAD.read_text(encoding="utf-8")
    for token in ("NaN", "Infinity", "-Infinity"):
        assert f": {token}" not in raw and f", {token}" not in raw, \
            f"{token} is not valid JSON and JSON.parse will reject the payload"


def test_verdict_is_derived_from_the_data_not_transcribed(payload):
    """The page's headline evidence must move with the data like everything else.

    These four numbers are the product's central claim. They were once literals
    copied out of an ad-hoc analysis, which meant a refresh would leave them
    contradicting the very figures printed beside them.
    """
    from blackout import ClosureClock, Regime
    from blackout.basis import add_premium, decompose_closure, hourly_frame
    from blackout.build import ANALYSIS_START, load

    clock = ClosureClock(start="2025-06-01", end="2027-12-31")
    df = hourly_frame({"x": load("NVDAx"), "nvda": load("NVDA"), "nq": load("NQ_F")}, clock)
    df = add_premium(df, token="x", native="nvda")
    d = df[df.index >= ANALYSIS_START].dropna(subset=["prem"])

    closes = pd.DatetimeIndex([
        d[(d.index >= w["start"]) & (d.index < w["end"])].index.max()
        for _, w in clock.blackouts().iterrows()
        if w["regime"] == Regime.WEEKEND_BLACKOUT.value
        and w["start"] >= d.index.min() and w["end"] <= d.index.max()
        and len(d[(d.index >= w["start"]) & (d.index < w["end"])]) >= 20
    ])

    for hours, label in ((1, "1h"), (6, "6h"), (12, "12h")):
        stats = decompose_closure(d, closes, token="x", horizon_h=hours)
        assert payload["verdict"][f"token_share_{label}"] == pytest.approx(
            stats["token_share"], rel=1e-9), f"token_share_{label} no longer matches the data"

    twelve = decompose_closure(d, closes, token="x", horizon_h=12)
    assert payload["verdict"]["hit_rate"] == pytest.approx(twelve["hit_rate"], rel=1e-9)
    assert payload["verdict"]["net_at_10bp"] == pytest.approx(
        twelve["token_leg_pnl"] - 0.0010, rel=1e-9)


def test_the_finding_still_holds_or_the_product_needs_rewriting(payload):
    """A guard on the claim itself, not just its arithmetic.

    The page tells traders the weekend premium is an information lead rather
    than an arbitrage. If a data refresh ever overturns that, the copy is wrong
    and this must fail loudly rather than let the page keep asserting it.
    """
    v = payload["verdict"]
    assert v["token_share_6h"] < 0.5, \
        "the token leg now drives most of the closure - the central claim has flipped"
    assert v["net_at_10bp"] < 0, \
        "fading the premium is now profitable after costs - the page's advice is wrong"
    assert 0.4 < v["hit_rate"] < 0.6, \
        "fading is no longer a coin flip - re-run the research before shipping"


def test_sample_size_travels_with_every_distribution(payload):
    """A distribution without its n is the thing that misleads a reader."""
    for row in payload["drift"]:
        assert row["n_windows"] >= 5, "a bucket thin enough to mislead is being shipped"
        assert row["n_windows"] <= row["n"]
    assert payload["summary"]["n_windows"] == payload["verdict"]["n_weekends"]


def test_analogue_rows_expose_outcomes_only_alongside_features(payload):
    names = set(payload["analogue_feature_names"])
    for row in payload["analogue_features"]:
        assert names & set(row), "analogue row carries none of the declared features"
        assert "terminal_drift" in row, "outcome missing; retrieval would show nothing"


def test_generated_page_matches_the_current_payload():
    """A stale desk.html would publish yesterday's numbers under today's claims."""
    if not PAGE.exists():
        pytest.skip("run `python scripts/build_page.py` first")
    import re
    html = PAGE.read_text(encoding="utf-8")
    blob = re.search(r'<script id="desk-data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    embedded = json.loads(blob.replace("<\\/", "</"))
    current = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert embedded["verdict"] == current["verdict"], \
        "desk.html is stale - rebuild it with scripts/build_page.py"
    assert embedded["coverage"] == current["coverage"]
