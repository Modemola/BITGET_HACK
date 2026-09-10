"""The page reimplements analogue retrieval in JavaScript. This proves it agrees.

`blackout.analogues.find_analogues` is tested, reviewed and trusted. The published
page cannot import it, so `desk.template.html` carries a second implementation of
the same weighted-Euclidean-over-z-scores retrieval. Two implementations of one
algorithm is a standing invitation to drift, and a drifted copy would not error --
it would quietly show a trader the wrong five weekends.

So this extracts the real functions out of the template (never a copy pasted here,
which would drift in its own right), runs them under Node against the same payload
the page ships, and requires identical ordering and distances.

Skipped when Node is unavailable, so the suite still runs on a bare machine.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from blackout.analogues import find_analogues

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "desk.template.html"
PAYLOAD = ROOT / "web" / "data" / "desk.json"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Boundaries of the pure retrieval block inside the page script.
BLOCK_START = "var WEIGHTS ="
BLOCK_END = "function nextWindowHours()"

QUERIES = [
    {"realised_vol_5d": 0.55, "premium_at_close": 0.005, "window_hours": 49.0},
    {"realised_vol_5d": 0.30, "premium_at_close": -0.004, "window_hours": 49.0},
    {"realised_vol_5d": 0.70, "premium_at_close": 0.012, "window_hours": 73.0},
    {"realised_vol_5d": 0.48},                                    # partial query
    {"premium_at_close": 0.0, "window_hours": 49.0},              # partial query
]


def extract_retrieval_js() -> str:
    """Pull the retrieval functions straight out of the template."""
    src = TEMPLATE.read_text(encoding="utf-8")
    if BLOCK_START not in src or BLOCK_END not in src:
        pytest.fail(
            "the retrieval block moved in desk.template.html; update BLOCK_START/BLOCK_END "
            "rather than deleting this test -- it is the only thing keeping the page's "
            "copy of the algorithm honest"
        )
    block = src[src.index(BLOCK_START):src.index(BLOCK_END)]
    assert "document." not in block and "window." not in block, \
        "retrieval block picked up a DOM reference and is no longer pure"
    return block


def run_js(rows: list[dict], query: dict, k: int) -> list[dict]:
    js = extract_retrieval_js() + f"""
const rows = {json.dumps(rows)};
const out = findAnalogues(rows, {json.dumps(query)}, {k});
console.log(JSON.stringify(out.map(r => ({{
  window_start: r.window_start, distance: r.distance
}}))));
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "parity.mjs"
        path.write_text(js, encoding="utf-8")
        proc = subprocess.run([NODE, str(path)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"node failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    if not PAYLOAD.exists():
        pytest.skip("run `python -m blackout.build` first")
    data = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    features = data.get("analogue_features") or []
    if not features:
        pytest.skip("payload carries no analogue features")
    return features


@pytest.mark.parametrize("query", QUERIES)
def test_js_retrieval_matches_python(rows, query):
    """Same windows, same order, same distances."""
    k = 5
    js = run_js(rows, query, k)

    df = pd.DataFrame(rows)
    py = find_analogues(df, query, k=k)

    assert len(js) == len(py), f"{len(js)} matches in JS vs {len(py)} in Python"

    js_windows = [r["window_start"] for r in js]
    py_windows = [pd.Timestamp(w).isoformat() for w in py["window_start"]]
    assert [w[:19] for w in js_windows] == [w[:19] for w in py_windows], \
        "the page would show a different set of weekends than the analysis does"

    for got, want in zip((r["distance"] for r in js), py["distance"]):
        assert got == pytest.approx(want, rel=1e-9), "distance metrics have diverged"


def test_js_ignores_features_the_query_omits(rows):
    """A partial query must not silently match on unsupplied features."""
    full = run_js(rows, {"realised_vol_5d": 0.55, "premium_at_close": 0.005}, 5)
    vol_only = run_js(rows, {"realised_vol_5d": 0.55}, 5)
    assert [r["window_start"] for r in full] != [r["window_start"] for r in vol_only], \
        "adding a feature to the query changed nothing, so it is being ignored"


def test_js_handles_an_unknown_feature_without_crashing(rows):
    """Payload gaining a field the page does not weight must not break retrieval."""
    out = run_js(rows, {"realised_vol_5d": 0.5, "not_a_feature": 1.0}, 3)
    assert len(out) == 3


# --- the live clock ---------------------------------------------------------

CLOCK_START = "function currentRun(now)"
CLOCK_END = "function tick()"


def extract_clock_js() -> str:
    src = TEMPLATE.read_text(encoding="utf-8")
    if CLOCK_START not in src or CLOCK_END not in src:
        pytest.fail("the clock helpers moved in desk.template.html; update the markers")
    block = src[src.index(CLOCK_START):src.index(CLOCK_END)]
    assert "document." not in block and "window." not in block, \
        "clock helpers picked up a DOM reference and are no longer pure"
    return block


def run_clock_js(payload: dict, stamps: list[int]) -> list[dict]:
    js = f"""
var D = {json.dumps({"regime_runs": payload["regime_runs"],
                     "blackout_windows": payload["blackout_windows"]})};
function isBlackout(regime){{ return regime.indexOf("BLACKOUT") >= 0; }}
""" + extract_clock_js() + f"""
const stamps = {json.dumps(stamps)};
console.log(JSON.stringify(stamps.map(t => {{
  const run = currentRun(t);
  return {{
    t: t,
    regime: run ? run.regime : null,
    dark: run ? isBlackout(run.regime) : null,
    next_reference: nextReferenceAt(t),
    next_blackout: nextBlackoutAt(t)
  }};
}})));
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "clock.mjs"
        path.write_text(js, encoding="utf-8")
        proc = subprocess.run([NODE, str(path)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"node failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def payload() -> dict:
    if not PAYLOAD.exists():
        pytest.skip("run `python -m blackout.build` first")
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


def test_page_clock_agrees_with_the_calendar_at_every_hour(payload):
    """The page's regime must match ClosureClock for the whole shipped horizon.

    The clock is the one thing on the page that is genuinely live, so a
    disagreement here shows a trader the wrong state at the moment it matters.
    """
    from blackout import ClosureClock

    runs = payload["regime_runs"]
    stamps = list(range(runs[0]["start"], runs[-1]["end"], 3600))
    js = run_clock_js(payload, stamps)

    clock = ClosureClock(start="2025-06-01", end="2027-12-31")
    idx = pd.to_datetime(stamps, unit="s", utc=True)
    expected = clock.annotate(idx)["regime"].astype(str).tolist()

    mismatches = [
        (pd.Timestamp(r["t"], unit="s", tz="UTC"), r["regime"], want)
        for r, want in zip(js, expected) if r["regime"] != want
    ]
    assert not mismatches, f"page clock disagrees with the calendar at {mismatches[:5]}"


def test_blackout_hours_show_a_countdown_to_the_reference_returning(payload):
    """During a blackout the page must count toward a reference price, not away."""
    runs = payload["regime_runs"]
    dark = [r for r in runs if "BLACKOUT" in r["regime"]]
    assert dark, "shipped horizon contains no blackout to verify"

    probe = dark[0]
    stamps = [probe["start"], probe["start"] + 3600, probe["end"] - 3600]
    js = run_clock_js(payload, stamps)

    for row in js:
        assert row["dark"] is True
        assert row["next_reference"] is not None, "no reference return to count toward"
        assert row["next_reference"] > row["t"]
        # and it must land at the end of this blackout, not some later one
        assert row["next_reference"] == probe["end"], "countdown targets the wrong reopen"


def test_open_hours_count_toward_the_next_blackout(payload):
    runs = payload["regime_runs"]
    lit = [r for r in runs if "BLACKOUT" not in r["regime"]]
    assert lit
    probe = lit[0]
    js = run_clock_js(payload, [probe["start"] + 60])[0]
    assert js["dark"] is False
    assert js["next_blackout"] is not None and js["next_blackout"] > js["t"]


def test_countdown_never_runs_past_the_end_of_the_shipped_calendar(payload):
    """Beyond the horizon the page must say so rather than invent a time."""
    last = payload["regime_runs"][-1]["end"]
    js = run_clock_js(payload, [last + 86400])[0]
    assert js["regime"] is None, "page claims a regime beyond the data it shipped"


# --- formatters -------------------------------------------------------------

def test_formatters_render_missing_values_instead_of_throwing():
    """A value the build could not compute arrives as null, not NaN.

    `blackout.build._json_safe` converts non-finite numbers to null so the
    payload stays valid JSON. That pushes the problem into the page: calling
    `.toFixed()` on a null throws, and one bad cell would take down the whole
    table it sits in. Every formatter must degrade to a dash instead.
    """
    src = TEMPLATE.read_text(encoding="utf-8")
    start = src.index("function has(v)")
    end = src.index("var FILL =")
    js = src[start:end] + """
const cases = [null, undefined, NaN, Infinity, -Infinity];
const out = {};
for (const [name, fn] of [["pct",pct],["sgn",sgn],["usd",usd]]) {
  out[name] = cases.map(v => fn(v));
}
out.fix = cases.map(v => fix(v, 2));
out.good = [pct(0.05), sgn(-0.05), usd(1234.6), fix(0.7649, 2)];
console.log(JSON.stringify(out));
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "fmt.mjs"
        path.write_text(js, encoding="utf-8")
        proc = subprocess.run([NODE, str(path)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if proc.returncode != 0:
        pytest.fail(f"a formatter threw on a missing value:\n{proc.stderr}")

    out = json.loads(proc.stdout)
    for name in ("pct", "sgn", "usd", "fix"):
        assert all(v == "—" for v in out[name]), \
            f"{name} rendered something other than a dash for a missing value: {out[name]}"
    assert out["good"] == ["5.00%", "-5.00%", "$1,235", "0.76"], \
        f"formatters broke on real values: {out['good']}"
