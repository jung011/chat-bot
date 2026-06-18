"""Tool RAG / 검색 노드 (§01 §4.4, §06 §4.3, §9).

세 경로의 처리부:
- retrieve_documents: rag 경로. documents 컬렉션 Hybrid+Rerank → 컨텍스트 조립.
- agent: agent 경로. Tool RAG 로 후보 도구를 추려 LLM 도구호출 루프 실행(max_iters).
- prep_chitchat: chitchat 경로. 검색 없이 생성 단계로.

답변 실패(§06 §10)는 mode="fail" 로 표기한다(A: 도구없음, C: 근거없음 — chat_service 가 폴백 처리).
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.memory import short_term
from app.orchestration import prompts
from app.orchestration.state import RAGState, add_usage
from app.mcp import domain_client, faq_client
from app.retrieval import hybrid, reranker, tool_retriever

DOCUMENTS_COLLECTION = "documents"
FAQ_SCORE_FLOOR = 0.15   # 이 미만의 무관 FAQ 는 컨텍스트에서 제외(노이즈 방지)


def _format_context(hits) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        title = h.payload.get("title", "")
        text = h.payload.get("text", "")
        lines.append(f"[{i}] {title}: {text}".strip())
    return "\n".join(lines)


async def retrieve_documents(state: RAGState) -> dict:
    """rag 경로: 문서 검색 + FAQ top-K 를 함께 컨텍스트로 수집(복합 질문 대응).

    문서(documents)와 FAQ(업체 서버 search_faq)를 모두 검색해 병합한다. 둘 다 비면 fail.
    FAQ 를 검색 소스로 함께 써서, FAQ-전용 정보(주차·포장 등)도 복합 질문에서 답할 수 있다.
    """
    question = state.get("rewritten") or state["question"]

    # 1) 문서 검색 (Hybrid + Rerank)
    hits = await hybrid.search(
        DOCUMENTS_COLLECTION, question, company_id=state["company_id"],
        top_k=state.get("doc_top_k", settings.doc_top_k), alpha=0.5, text_field="text",
    )
    ranked = reranker.rerank(
        question, hits, top_n=state.get("doc_top_n", settings.doc_top_n), text_field="text"
    )

    # 2) FAQ 검색 (업체 FAQ 서버 search_faq, 점수 floor 로 무관 항목 제외)
    faq_items = [
        f for f in await faq_client.search_faq(
            server_url=state.get("faq_server_url", ""), question=question, top_k=5
        )
        if f.get("score", 0) >= FAQ_SCORE_FLOOR and f.get("answer")
    ]

    parts, sources = [], []
    if ranked:
        parts.append(_format_context(ranked))
        sources += [
            {"type": "document", "title": h.payload.get("title", "문서"), "score": round(h.score, 3)}
            for h in ranked
        ]
    if faq_items:
        parts.append(
            "\n".join(f"[FAQ] Q: {f['question']} / A: {f['answer']}" for f in faq_items)
        )
        sources += [
            {"type": "faq", "title": f["question"], "score": round(f["score"], 3)} for f in faq_items
        ]

    if not parts:
        return {"mode": "fail"}  # C: 근거 없음
    return {"mode": "generate", "retrieved_context": "\n".join(parts), "sources": sources}


async def prep_chitchat(state: RAGState) -> dict:
    """chitchat 경로: 검색 없이 생성으로."""
    return {"mode": "generate", "retrieved_context": ""}


def _anthropic_tools(candidates: list[dict]) -> list[dict]:
    return [
        {
            "name": c["name"],
            "description": c["description"],
            "input_schema": c.get("params_schema")
            or {"type": "object", "properties": {}},
        }
        for c in candidates
    ]


async def agent(state: RAGState) -> dict:
    """agent 경로: Tool RAG → LLM 도구호출 루프(§06 §9). max_iters 로 무한루프 방지."""
    question = state.get("rewritten") or state["question"]
    company_id = state["company_id"]
    llm = get_llm()

    candidates = await tool_retriever.retrieve_tools(
        question, company_id=company_id, top_k=state.get("tool_top_k", settings.tool_top_k)
    )
    if not candidates:
        return {"mode": "fail"}  # A: 적합한 도구 없음

    # LLM 미설정 → 도구호출 불가. 문서 검색으로 degrade.
    if not llm.available:
        return await retrieve_documents(state)

    system = prompts.AGENT_SYSTEM.format(
        persona=state["persona"], company_id=company_id, business_info=state["business_info"]
    )
    history = short_term.history_text(state.get("history", []))
    user = (f"[대화 히스토리]\n{history}\n[질문]\n{question}" if history else question)
    messages: list[dict] = [{"role": "user", "content": user}]
    tools = _anthropic_tools(candidates)

    usage = dict(state.get("usage", {"input_tokens": 0, "output_tokens": 0}))
    sources: list[dict] = []
    trace: list[dict] = []

    max_iters = settings.max_tool_iters
    answer = ""
    try:
        for _ in range(max_iters):
            comp = await llm.complete(
                system=system, messages=messages, model=model_for(Stage.TOOL_SELECT),
                max_tokens=1024, tools=tools,
            )
            usage["input_tokens"] += comp.input_tokens
            usage["output_tokens"] += comp.output_tokens

            if not comp.tool_calls:
                answer = comp.text.strip()
                break

            # 어시스턴트 turn(텍스트+tool_use 블록) 재구성 후 도구 결과 회신
            assistant_blocks: list[dict] = []
            if comp.text:
                assistant_blocks.append({"type": "text", "text": comp.text})
            for tc in comp.tool_calls:
                assistant_blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
                )
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_results = []
            general_url = state.get("general_server_url", "")
            for tc in comp.tool_calls:
                args = {k: v for k, v in tc.input.items() if k != "company_id"}
                result = await domain_client.call(general_url, tc.name, company_id, **args)
                trace.append({"tool": tc.name, "args": args, "result": result})
                if result.get("success"):
                    sources.append({"type": "tool", "title": tc.name})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
    except AppError:
        raise  # 타임아웃/업스트림 오류는 서비스에서 처리

    if not answer:
        return {"mode": "fail", "usage": usage, "tool_trace": trace}  # A: 도구 호출했으나 답 없음
    return {
        "mode": "answer_ready",
        "answer": answer,
        "sources": sources,
        "tool_trace": trace,
        "usage": usage,
    }
