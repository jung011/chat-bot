"""Tool RAG — 질문에 관련된 도구 후보를 검색한다(§01 §4.4, §08 §4).

`tools` 컬렉션(도구 description 임베딩, 공용)에서 Hybrid+Rerank 로 Top-K 도구를
추린다. description 품질이 검색 정확도를 좌우한다(§08 §7).
"""
from __future__ import annotations

from app.core.config import settings
from app.retrieval import hybrid, reranker

TOOLS_COLLECTION = "tools"


async def retrieve_tools(query: str, *, top_k: int | None = None) -> list[dict]:
    """관련 도구 후보 목록. 각 원소: {server, name, description, params_schema}."""
    k = top_k or settings.tool_top_k
    hits = await hybrid.search(
        TOOLS_COLLECTION,
        query,
        company_id=None,  # 도구는 테넌트 무관 공용(§04 §2)
        top_k=k * 2,
        alpha=0.5,
        text_field="description",
    )
    ranked = reranker.rerank(query, hits, top_n=k, text_field="description")
    tools: list[dict] = []
    for h in ranked:
        p = h.payload
        tools.append(
            {
                "server": p.get("server"),
                "name": p.get("name"),
                "description": p.get("description"),
                "params_schema": p.get("params_schema", {}),
                "score": h.score,
            }
        )
    return tools
