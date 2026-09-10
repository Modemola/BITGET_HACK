"""Retrieve past closure windows that resemble the one ahead.

The desk's fourth question, and the heart of the Decision Stress Testing
sub-theme: rather than asserting a forecast, show the trader what happened the
last k times conditions looked like this, and let them read the spread.

Similarity is deliberately over a small, interpretable feature set — realised
volatility going in, the premium at the close, window length, and whether a
scheduled macro event falls inside. A trader must be able to see *why* a
weekend was retrieved, or the retrieval is not evidence.
"""

from __future__ import annotations

import pandas as pd

FEATURES = ("realised_vol_5d", "premium_at_close", "window_hours", "has_macro_event")


def build_feature_table(paths: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """One row per historical window, carrying FEATURES plus its outcome."""
    raise NotImplementedError("Phase 1 — see docs/ARCHITECTURE.md §6")


def find_analogues(features: pd.DataFrame, query: dict, k: int = 5) -> pd.DataFrame:
    """The k most similar past windows, with distance and outcome attached."""
    raise NotImplementedError("Phase 1 — see docs/ARCHITECTURE.md §6")
