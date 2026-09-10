"""Fetch scheduled macro events from primary sources into data/macro_events.csv.

The desk's seventh tool answers "what is scheduled between now and the reopen?".
That question is worthless if the answer is invented, so every event here is
parsed from the issuing authority rather than recalled or hand-typed.

Currently sourced: FOMC rate decisions from federalreserve.gov.

The calendar page carries each meeting twice, and the two forms have opposite
strengths. A meeting that has *happened* has a statement link
(monetary20260128a1.pdf) giving the exact decision date. A meeting still ahead
has only a displayed month and day range ("15-16*"). The tool is forward
looking, so the range is the form that matters -- but it is also the form that
is easy to misparse, especially when a meeting straddles a month boundary.

So this parses the ranges for every meeting and then *checks them against the
statement dates* wherever both exist. Past meetings validate the parser that
future meetings depend on. If that agreement ever breaks, the run fails rather
than writing dates nobody has checked.

    python scripts/fetch_events.py
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "macro_events.csv"

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
HEADERS = {"User-Agent": "Mozilla/5.0 (blackout-desk research)"}
TIMEOUT = 30

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
FOMC_RELEASE_ET = (14, 0)          # the statement drops at 14:00 ET

_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"]
# A meeting that straddles a month is labelled with abbreviations ("Jan/Feb"),
# while every other row spells the month out. Accept both, or the straddling
# meetings silently vanish from the calendar.
MONTHS = {name: i for i, name in enumerate(_MONTH_NAMES, start=1)}
MONTHS.update({name[:3]: i for i, name in enumerate(_MONTH_NAMES, start=1)})

PANEL_RE = re.compile(r'<a id="\d+">(\d{4}) FOMC Meetings</a>')
ROW_RE = re.compile(
    r'fomc-meeting__month[^>]*>\s*(?:<strong>)?(.*?)(?:</strong>)?\s*</div>\s*'
    r'<div[^>]*fomc-meeting__date[^>]*>\s*(.*?)\s*</div>',
    re.S)
STATEMENT_RE = re.compile(r"monetary(\d{4})(\d{2})(\d{2})a1?\.(?:pdf|htm)")


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").strip()


def parse_meeting_rows(html: str) -> list[dict]:
    """Every meeting on the page, from its displayed month and day range.

    Handles the month-straddling form, where the month cell reads
    "January/February" and the range runs 31-1: the decision is the second day,
    which belongs to the second month.
    """
    panels = list(PANEL_RE.finditer(html))
    out = []
    for i, panel in enumerate(panels):
        year = int(panel.group(1))
        chunk = html[panel.end(): panels[i + 1].start() if i + 1 < len(panels) else len(html)]

        for row in ROW_RE.finditer(chunk):
            months = [m for m in re.split(r"[/\-]", _clean(row.group(1))) if m.strip()]
            days = re.findall(r"\d+", _clean(row.group(2)))
            if not months or not days:
                continue

            month_name = months[-1].strip()          # decision falls in the later month
            if month_name not in MONTHS:
                continue
            month = MONTHS[month_name]
            day = int(days[-1])                      # decision is the final day

            # A straddling meeting rolls into the next year only across December.
            row_year = year + 1 if (len(months) > 1
                                    and months[0].strip()[:3] == "Dec"
                                    and month == 1) else year
            try:
                local = datetime(row_year, month, day, *FOMC_RELEASE_ET, tzinfo=ET)
            except ValueError:
                continue
            out.append({"date": local.astimezone(UTC), "year": year})
    return out


def parse_statement_dates(html: str) -> set[str]:
    """Exact decision dates for meetings that have already happened."""
    return {f"{y}-{m}-{d}" for y, m, d in
            (mt.groups() for mt in STATEMENT_RE.finditer(html))}


def fetch_fomc() -> pd.DataFrame:
    r = requests.get(FOMC_URL, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    html = r.text

    rows = parse_meeting_rows(html)
    if not rows:
        raise SystemExit("no FOMC meeting rows parsed; the page layout changed")

    statements = parse_statement_dates(html)
    parsed = {d["date"].astimezone(ET).strftime("%Y-%m-%d") for d in rows}

    # Past meetings appear in both forms. Every statement date must be one the
    # range parser also produced, or the parser future meetings rely on is wrong.
    disagreements = sorted(statements - parsed)
    if disagreements:
        raise SystemExit(
            "range parser disagrees with the published statement dates at "
            f"{disagreements[:5]} -- refusing to write unverified dates"
        )

    df = pd.DataFrame([{
        "ts_utc": d["date"],
        "label": "FOMC rate decision",
        "category": "monetary_policy",
        "importance": "high",
        "source": FOMC_URL,
    } for d in rows]).drop_duplicates("ts_utc").sort_values("ts_utc")

    df.attrs["verified"] = len(statements)
    return df.reset_index(drop=True)


def main() -> int:
    print("Fetching scheduled macro events from primary sources\n")
    try:
        fomc = fetch_fomc()
    except requests.RequestException as e:
        print(f"  FOMC fetch failed: {type(e).__name__}: {e}")
        print("\nRefusing to write a partial calendar. The tool is better with no")
        print("events than with a set nobody can trace back to its issuer.")
        return 1

    now = pd.Timestamp.now(tz="UTC")
    future = fomc[fomc["ts_utc"] > now]

    print(f"  meetings parsed     : {len(fomc)} "
          f"({fomc['ts_utc'].min():%Y-%m-%d} to {fomc['ts_utc'].max():%Y-%m-%d})")
    print(f"  cross-checked       : {fomc.attrs['verified']} against published statement dates")
    print(f"  still ahead         : {len(future)}")
    if len(future):
        nxt = future.iloc[0]["ts_utc"]
        print(f"  next decision       : {nxt:%Y-%m-%d %H:%M} UTC "
              f"({(nxt - now).days}d away)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fomc.to_csv(OUT, index=False)
    print(f"\nwrote {OUT.relative_to(ROOT)}  ({len(fomc)} events)")

    weekend = int((fomc["ts_utc"].dt.dayofweek >= 5).sum())
    print(f"  falling on a weekend: {weekend}")
    print("  Weekend blackout risk is unscheduled risk -- that is the point of the tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
