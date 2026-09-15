"""The seven-tool contract, and its agreement with everything else.

`tools.py` is a façade. Its whole value is that one entry point returns the same
numbers the analysis does, so the danger is not that it breaks loudly — it is
that it quietly returns something slightly different and nobody notices which
figure a reader is looking at.

That already happened once. `blackout_closes()` counted a blackout still in
progress as a completed one, giving 29 weekends where every other code path
counts 28, and every decomposition figure moved with it. The parity tests below
are what caught it.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from blackout.tools import TOOLS, Desk, load_series

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "web" / "data" / "desk.json"


@pytest.fixture(scope="module")
def desk() -> Desk:
    try:
        return Desk()
    except FileNotFoundError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="module")
def payload() -> dict:
    if not PAYLOAD.exists():
        pytest.skip("run `python -m blackout.build` first")
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


# --- the contract itself ----------------------------------------------------

def test_there_are_exactly_seven_tools():
    """The number is load-bearing: the page's rail and the submission both
    claim seven, and a mismatch makes one of them wrong."""
    assert len(TOOLS) == 7, f"the contract carries {len(TOOLS)} tools"


def test_every_tool_states_the_question_it_answers():
    for name, tool in TOOLS.items():
        assert tool.question.endswith("?"), f"{name} does not state a question"
        assert tool.name == name, f"{name} is registered under a different name"


def test_every_tool_runs_and_returns_a_plain_dict(desk):
    for name in TOOLS:
        out = desk.run(name)
        assert isinstance(out, dict) and out, f"{name} returned nothing usable"


def test_an_unknown_tool_names_the_ones_that_exist(desk):
    with pytest.raises(KeyError, match="no such tool"):
        desk.run("does_not_exist")


def test_tool_output_survives_json(desk):
    """An agent layer serialises these; a stray Timestamp would break it."""
    for name in TOOLS:
        json.dumps(desk.run(name), allow_nan=False)


# --- parity with the shipped analysis ---------------------------------------

def test_verdict_matches_the_payload(desk, payload):
    """The product's central claim must read identically wherever it is asked."""
    got, want = desk.run("premium_verdict"), payload["verdict"]
    assert got["n_weekends"] == want["n_weekends"]
    for hours in ("1h", "6h", "12h"):
        assert got["by_horizon"][hours]["token_share"] == pytest.approx(
            want[f"token_share_{hours}"], rel=1e-9), f"token_share_{hours} drifted"
    assert got["hit_rate"] == pytest.approx(want["hit_rate"], rel=1e-9)
    assert got["net_at_10bp"] == pytest.approx(want["net_at_10bp"], rel=1e-9)


def test_distribution_matches_the_payload(desk, payload):
    got, want = desk.run("divergence_distribution")["summary"], payload["summary"]
    for key in ("n_windows", "mean_abs_terminal_drift",
                "p95_abs_terminal_drift", "worst_terminal_drift"):
        assert got[key] == pytest.approx(want[key], rel=1e-9), f"{key} drifted"


def test_hedges_match_the_payload(desk, payload):
    got = {r["instrument"]: r for r in desk.run("hedge_menu")["instruments"]}
    for row in payload["hedges"]:
        mine = got.get(row["instrument"])
        assert mine, f"{row['instrument']} is missing from the tool output"
        assert mine["correlation"] == pytest.approx(row["correlation"], rel=1e-9)
        assert mine["stable"] == row["stable"]


def test_only_completed_blackouts_count(desk):
    """A window still in progress has bars but no close.

    Treating its latest bar as a close adds an unfinished weekend to every
    figure derived from these stamps — which is the bug these tests caught.
    """
    closes = desk.blackout_closes()
    assert len(closes) > 20, "too few closes to be measuring anything"
    assert closes.max() <= desk.frame.index.max()
    windows = desk.clock.blackouts()
    for stamp in closes:
        window = windows[(windows["start"] <= stamp) & (windows["end"] > stamp)]
        assert len(window) == 1, f"{stamp} does not sit inside exactly one blackout"
        assert window.iloc[0]["end"] <= desk.frame.index.max(), \
            "a blackout that has not finished is being counted as one that has"


# --- individual tools -------------------------------------------------------

def test_closure_window_reports_a_real_regime(desk):
    out = desk.run("closure_window", as_of=pd.Timestamp("2026-09-12 12:00", tz="UTC"))
    assert out["regime"] == "WEEKEND_BLACKOUT"
    assert out["hours_to_futures_open"] > 0
    assert out["next_blackout_hours"] == pytest.approx(49.0)


def test_exposure_scales_with_the_position(desk):
    as_of = pd.Timestamp("2026-09-11 19:45", tz="UTC")
    small = desk.run("exposure", usd=10_000, as_of=as_of)
    large = desk.run("exposure", usd=1_000_000, as_of=as_of)
    assert large["usd"] == 100 * small["usd"]
    # the clock does not care how much money is riding on it
    assert small["blackout_hours"] == large["blackout_hours"]


def test_analogues_default_to_the_median_conditions(desk):
    out = desk.run("historical_analogues", k=3)
    assert len(out["matches"]) == 3
    assert out["pool_size"] >= 20
    assert set(out["query"]), "no query was formed"


def test_macro_calendar_carries_its_own_evidence(desk):
    out = desk.run("macro_calendar", as_of=pd.Timestamp("2026-09-11 19:45", tz="UTC"))
    assert out["has_window"] is True
    assert out["historical_overlap"]["overlaps"] == 0, \
        "a scheduled event now falls inside a blackout; the page's claim is wrong"


def test_a_missing_series_says_which_file_and_how_to_get_it():
    with pytest.raises(FileNotFoundError, match="probe_sources"):
        load_series("NOT_A_SYMBOL")
