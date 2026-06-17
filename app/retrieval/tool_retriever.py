"""Tool RAG — 질문에 관련된 도구 후보를 검색한다(§01 §4.4, §08 §4).

`tools` 컬렉션(도구 description 임베딩, 공용)에서 Hybrid+Rerank 로 Top-K 도구를
추린다. description 품질이 검색 정확도를 좌우한다(§08 §7).
"""
from __future__ import annotations

from app.core.config import settings
from app.retrieval import hybrid, reranker

TOOLS_COLLECTION = "tools"


async def retrieve_tools(
    query: str, *, company_id: str | None = None, top_k: int | None = None
) -> list[dict]:
    """관련 도구 후보 목록. 각 원소: {server, name, description, params_schema}.

    company_id 가 주어지면 그 업체가 보유한 도구로만 검색을 한정한다(업체별 일반
    MCP 서버 분리에 대응 — 그 업체에 없는 도구를 후보로 주지 않음). None 이면
    전체 도구에서 검색(공용 호환).
    """
    k = top_k or settings.tool_top_k
    hits = await hybrid.search(
        TOOLS_COLLECTION,
        query,
        company_id=company_id,
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
