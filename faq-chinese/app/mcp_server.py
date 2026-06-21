"""FastMCP 서버 정의 — match_faq 도구."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app import ingest, matcher
from app.config import settings

mcp = FastMCP(f"faq-{settings.company_id}")


@mcp.tool()
async def match_faq(question: str) -> dict:
    """질문을 업체 FAQ 와 시맨틱 매칭한다. 임계값 이상이면 즉답을 반환."""
    return await matcher.match(question)


@mcp.tool()
async def search_faq(question: str, top_k: int = 5) -> dict:
    """질문과 관련된 FAQ 후보 top-K 를 반환(임계값 없음, 생성 컨텍스트용). 복합 질문 대응."""
    return {"results": await matcher.search_faq(question, top_k)}


@mcp.tool()
async def upsert_faq(company_id: str, items: list[dict]) -> dict:
    """업체 FAQ 를 적재(임베딩→자기 faq 컬렉션). items: [{question, answer, category?}].
    company_id 는 호출 일관성용 — 이 서버는 자기 설정(company_id)으로 적재한다."""
    return await ingest.upsert_faq(items)
