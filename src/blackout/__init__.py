"""Blackout Desk — closure-window risk for tokenized US stocks.

The package is named for what it measures: the hours when every reference venue
is shut and an rToken is the only thing quoting the underlying. It began as a
strategy to trade the premium that opens in those windows; that premium turned
out to be an information lead rather than something tradeable, and the finding
is what the product now reports. See docs/FINDINGS.md.
"""

from .clock import ClosureClock, Regime

__all__ = ["ClosureClock", "Regime"]
