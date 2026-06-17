"""documents 서버 도구 (§08 §4.1, §5.4).

메뉴/정책 등 비정형 문서를 Qdrant `documents` 컬렉션에서 Hybrid+Rerank 로 검색한다.
company_id 필터 필수(§04 §2).

⚠️ 파일럿 단순화: 본 도구는 메인 앱의 검색 인프라(app.retrieval)를 인프로세스로
재사용한다. 운영에서 documents 서버를 독립 배포할 경우, 동일 검색 로직을 서버에
번들링한다(§02 §5: MCP 서버는 LLM 없는 도구 제공자).
"""
from __future__ import annotations

from app.core.config import settings
from app.retrieval import hybrid, reranker
from mcp_servers._shared.responses import fail, ok
from mcp_servers._shared.tooling import ToolSpec

DOCUMENTS_COLLECTION = "documents"

_PARAMS = {
    "type": "object",
    "properties": {"company_id": {"type": "string"}, "query": {"type": "string"}},
    "required": ["company_id", "query"],
}


async def _search(company_id: str, query: str, category: str | None):
    hits = await hybrid.search(
        DOCUMENTS_COLLECTION,
        query,
        company_id=company_id,
        top_k=settings.doc_top_k,
        alpha=0.5,
        text_field="text",
    )
    ranked = reranker.rerank(query, hits, top_n=settings.doc_top_n, text_field="text")
    if category:
        ranked = [h for h in ranked if h.payload.get("category") == category] or ranked
    return ranked


async def search_menu(company_id: str, query: str) -> dict:
    """메뉴 이름·가격·옵션·세트 구성을 검색한다. 메뉴/가격/구성 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    ranked = await _search(company_id, query, category="menu")
    if not ranked:
        return fail("관련 메뉴를 찾지 못했습니다.")
    items = [
        {"text": h.payload.get("text"), "title": h.payload.get("title"), "score": round(h.score, 3)}
        for h in ranked
    ]
    return ok(items=items, count=len(items))


async def search_policy(company_id: str, query: str) -> dict:
    """배달지역·배달비·최소주문금액·환불 등 정책을 검색한다. 정책 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    ranked = await _search(company_id, query, category="policy")
    if not ranked:
        return fail("관련 정책 정보를 찾지 못했습니다.")
    snippets = [
        {"title": h.payload.get("title"), "text": h.payload.get("text"), "source": h.payload.get("source_uri")}
        for h in ranked
    ]
    return ok(snippets=snippets, count=len(snippets))


TOOLS: list[ToolSpec] = [
    ToolSpec(
        server="documents",
        name="search_menu",
        description="메뉴 이름·가격·옵션·세트 구성을 검색한다. 메뉴·가격·메뉴구성·추천 문의에 사용.",
        params_schema=_PARAMS,
        handler=search_menu,
    ),
    ToolSpec(
        server="documents",
        name="search_policy",
        description="배달지역·배달비·최소주문금액·환불 등 정책을 검색한다. 정책·규정 문의에 사용.",
        params_schema=_PARAMS,
        handler=search_policy,
    ),
]
