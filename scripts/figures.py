"""Print the canonical figures, in a stable order, one per line.

Two jobs.

For a person: after refreshing the data, this is the list of numbers the prose
has to be brought back in line with. `tests/test_doc_figures.py` will tell you
*that* something drifted; this tells you what it drifted to.

For CI: the refresh workflow captures this before and after a data pull and puts
the diff in the pull request, so the reviewer sees exactly what moved without
reading a 25KB JSON blob.

Output is `key<TAB>value`, sorted, ASCII, and free of timestamps, so a plain
`diff` of two runs shows only genuine movement.

    python scripts/figures.py
    python scripts/figures.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "web" / "data" / "desk.json"


def figures(payload: dict) -> dict[str, str]:
    """The numbers the documents quote, formatted exactly as they appear there."""
    summary = payload.get("summary", {})
    verdict = payload.get("verdict", {})
    coverage = payload.get("coverage", {})
    calendar = payload.get("calendar_stats", {})
    dispersion = {d["regime"]: d for d in payload.get("dispersion", [])}

    def pct(value, places=2):
        return "-" if value is None else f"{value * 100:.{places}f}%"

    out = {
        "coverage.bars": str(coverage.get("bars", "-")),
        "coverage.start": str(coverage.get("start", "-"))[:10],
        "coverage.end": str(coverage.get("end", "-"))[:10],
        "coverage.beta": f"{coverage.get('beta', float('nan')):.2f}",
        "windows.n": str(summary.get("n_windows", "-")),
        "drift.mean_abs": pct(summary.get("mean_abs_terminal_drift")),
        "drift.p95_abs": pct(summary.get("p95_abs_terminal_drift")),
        "drift.worst": pct(summary.get("worst_terminal_drift")),
        "drift.share_beyond_1pct": pct(summary.get("share_exceeding_1pct"), 0),
        "verdict.token_share_1h": pct(verdict.get("token_share_1h"), 0),
        "verdict.token_share_6h": pct(verdict.get("token_share_6h"), 0),
        "verdict.token_share_12h": pct(verdict.get("token_share_12h"), 0),
        "verdict.hit_rate": pct(verdict.get("hit_rate"), 1),
        "verdict.net_at_10bp": pct(verdict.get("net_at_10bp"), 3),
        "calendar.overlaps": str(calendar.get("overlaps", "-")),
        "calendar.events_considered": str(calendar.get("events_considered", "-")),
        "calendar.windows": str(calendar.get("windows", "-")),
        "events.upcoming": str(len(payload.get("events", []))),
    }
    for regime in ("US_CASH", "WEEKNIGHT", "WEEKEND_BLACKOUT"):
        row = dispersion.get(regime)
        out[f"dispersion.{regime}.std"] = pct(row["std"]) if row else "-"
    for hedge in payload.get("hedges", []):
        name = hedge["instrument"]
        out[f"hedge.{name}.corr"] = f"{hedge['correlation']:+.2f}"
        out[f"hedge.{name}.stable"] = str(bool(hedge["stable"])).lower()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON instead of key/value lines")
    args = ap.parse_args()

    if not PAYLOAD.exists():
        print("no payload; run `python -m blackout.build` first", file=sys.stderr)
        return 1

    values = figures(json.loads(PAYLOAD.read_text(encoding="utf-8")))
    if args.json:
        print(json.dumps(values, indent=1, sort_keys=True))
    else:
        for key in sorted(values):
            print(f"{key}\t{values[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
