"""Tool RAG 인덱싱 — 외부 일반 서버에서 도구를 디스커버리해 `tools` 컬렉션에 적재.

도구의 단일 출처는 **외부 general-* 서버**다. 오케스트레이터는 각 서버의 MCP
`list_tools` 로 도구(이름·설명·입력스키마)를 발견해 임베딩·적재한다(하드코딩 카탈로그 없음).

전제: general 서버들이 떠 있어야 한다(python scripts/run_external_servers.py).
실행: python scripts/index_tools.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402

from app.retrieval import vector_store  # noqa: E402
from app.tenancy.registry import get_registry  # noqa: E402
from indexing import pipeline  # noqa: E402

# Tool RAG 후보에서 제외할 적재/관리 도구(고객 질의용 아님)
_EXCLUDE = {"ingest_documents", "upsert_faq"}


async def discover(server_url: str) -> list[dict]:
    """외부 일반 서버의 list_tools → 카탈로그 항목(적재/관리 도구 제외)."""
    async with streamablehttp_client(server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
            return [
                {
                    "server": "general",
                    "name": t.name,
                    "description": t.description or "",
                    "params_schema": t.inputSchema or {},
                }
                for t in res.tools
                if t.name not in _EXCLUDE
            ]


async def main() -> None:
    # 인자로 업체를 주면 **증분**(그 업체 도구만 upsert, 컬렉션 drop 안 함) → 무중단.
    #   예: python scripts/index_tools.py bunsik   (기존 업체 도구 검색 영향 0)
    # 인자가 없으면 전체 재색인(컬렉션 drop & recreate — 오프라인/초기 구축용).
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    full_rebuild = not targets

    client = vector_store.get_client()
    if full_rebuild:
        if await client.collection_exists("tools"):
            await client.delete_collection("tools")  # 전체 재색인 시에만 정리
        tenants = get_registry().all()
    else:
        # 증분: 컬렉션은 보존(없으면 pipeline.index_tools 가 생성). 대상 업체만.
        tenants = [t for t in get_registry().all() if t.company_id in targets]
        if not tenants:
            print(f"[error] 대상 업체 없음(tenants.yaml 미등록?): {targets}")
            await vector_store.close_client()
            return
        print(f"[incremental] 대상 업체만 색인(기존 컬렉션 보존): {[t.company_id for t in tenants]}")

    total = 0
    for tenant in tenants:
        url = tenant.general_server_url
        if not url:
            print(f"[skip] {tenant.company_id}: general_server_url 없음")
            continue
        try:
            catalog = await discover(url)
        except Exception as e:
            print(f"[error] {tenant.company_id} ({url}) list_tools 실패: {e}")
            print("        general 서버를 먼저 기동하세요: python scripts/run_external_servers.py")
            continue
        n = await pipeline.index_tools(catalog, tenant.company_id)
        total += n
        print(f"[{tenant.company_id}] 도구 {n}개 발견·적재: {[c['name'] for c in catalog]}")

    print(f"tools 적재 완료: {total} 포인트({'전체 재색인' if full_rebuild else '증분'})")
    await vector_store.close_client()


if __name__ == "__main__":
    asyncio.run(main())
