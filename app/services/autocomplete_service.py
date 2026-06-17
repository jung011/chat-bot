"""자동완성 서비스 (§03 §3.3)."""
from __future__ import annotations

from app.autocomplete import suggester
from app.schemas.autocomplete import AutocompleteData, Suggestion


async def autocomplete(company_id: str, q: str, limit: int = 8) -> AutocompleteData:
    limit = max(1, min(limit, 20))  # §03 기본 8, 최대 20
    items = await suggester.suggest(company_id, q, limit=limit)
    return AutocompleteData(
        query=q, suggestions=[Suggestion(text=i["text"], source=i.get("source", "document")) for i in items]
    )
