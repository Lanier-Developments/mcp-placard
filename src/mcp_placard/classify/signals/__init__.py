"""Signal extractors, one module per signal class.

Each module returns candidate tiers carrying the evidence that produced them, and
the kinds that evidence establishes (Amendment 2 §3).
Extractors do not know about each other and do not combine — combination is
`classify.combine`'s job alone (Rule F: monotonic maximum, never a weighted score).
"""

from __future__ import annotations
