"""채팅/세션/피드백 요청·응답 모델 (§03 §3.1~3.5)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── 채팅 ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    company_id: str = Field(..., description="업체 식별자 (pizza/chinese/chicken)")
    session_id: str | None = Field(None, description="없으면 서버가 새로 생성")
    message: str = Field(..., min_length=1, max_length=4000, description="사용자 질문")
    stream: bool = Field(True, description="스트리밍 여부 (기본 true)")


class Source(BaseModel):
    type: Literal["faq", "document", "tool"]
    title: str
    score: float | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


# route: 계단형 필터 어디서 처리됐는지 (§03 §3.1 meta.route)
Route = Literal["faq_intercept", "rag", "agent", "chitchat"]


class ChatSyncData(BaseModel):
    session_id: str
    message_id: str
    route: Route
    answer: str
    sources: list[Source] = []
    usage: Usage = Usage()


# ── 세션 ──────────────────────────────────────────────────────────────
class SessionCreateRequest(BaseModel):
    company_id: str
    title: str | None = None


class SessionCreateData(BaseModel):
    session_id: str
    created_at: str


class SessionSummary(BaseModel):
    session_id: str
    title: str | None = None
    updated_at: str


class MessageItem(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    route: Route | None = None
    created_at: str


# ── 피드백 ────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    company_id: str
    rating: Literal["up", "down"]
    reason: str | None = None
