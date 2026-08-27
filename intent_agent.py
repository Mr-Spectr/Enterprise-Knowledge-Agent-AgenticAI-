"""
intent_agent.py

Intent agent for CSV-only query routing.
It combines the normal classifier with students_500.csv so intent and entity
are corrected before retrieval.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, Tuple

from csv_db import enrich_classification


ClassifierFn = Callable[[str], Awaitable[Dict[str, str]]]


DEFAULT_CLASSIFICATION = {
    "query_type": "general_query",
    "intent": "general",
    "entity": "general",
}


async def run_intent_agent(
    query: str,
    classify_query: ClassifierFn,
    user_id: str = "",
) -> Tuple[Dict[str, str], str]:
    """
    Run the intent agent.

    The LLM/heuristic classifier gets the first pass. The CSV DB reader then
    checks real student rows and upgrades weak/general classifications.
    """
    try:
        base = await classify_query(query)
    except Exception:
        base = dict(DEFAULT_CLASSIFICATION)

    enriched = enrich_classification(query, base, user_id=user_id)

    if enriched == base:
        detail = (
            f"Intent kept as {enriched.get('intent')}, "
            f"entity={enriched.get('entity')}."
        )
    else:
        detail = (
            f"Intent adjusted from {base.get('intent')} to {enriched.get('intent')}; "
            f"entity={enriched.get('entity')}."
        )
    return enriched, detail
