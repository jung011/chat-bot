"""Claude 클라이언트 래퍼 (§06, §03 §1.5.1).

- 단일 LLM 호출에 60초 타임아웃을 적용하고 초과 시 LLMTimeout(504) 으로 변환.
- complete(): 텍스트/도구호출, complete_json(): 구조화 판단, stream(): 토큰 스트리밍.
- ANTHROPIC_API_KEY 가 없으면 available=False 로, 호출부가 폴백하도록 한다
  (FAQ 인터셉트/검색은 키 없이도 동작 — 키는 최종 생성/판단에만 필요).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.exceptions import LLMTimeout, UpstreamUnavailable


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class Completion:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    def __init__(self) -> None:
        self._timeout = settings.llm_timeout_seconds
        self._client: AsyncAnthropic | None = None
        if settings.anthropic_api_key:
            self._client = AsyncAnthropic(
                api_key=settings.anthropic_api_key, timeout=float(self._timeout)
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    def _require(self) -> AsyncAnthropic:
        if self._client is None:
            raise UpstreamUnavailable("LLM 이 설정되지 않았습니다(ANTHROPIC_API_KEY).")
        return self._client

    async def _await(self, coro):
        """60초 타임아웃 적용 → 초과 시 LLMTimeout."""
        try:
            return await asyncio.wait_for(coro, timeout=self._timeout)
        except asyncio.TimeoutError as e:
            raise LLMTimeout("LLM 응답이 제한 시간을 초과했습니다.") from e

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> Completion:
        client = self._require()
        kwargs: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, system=system, messages=messages
        )
        if tools:
            kwargs["tools"] = tools
        msg = await self._await(client.messages.create(**kwargs))

        out = Completion(stop_reason=msg.stop_reason)
        out.input_tokens = msg.usage.input_tokens
        out.output_tokens = msg.usage.output_tokens
        for block in msg.content:
            if block.type == "text":
                out.text += block.text
            elif block.type == "tool_use":
                out.tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=dict(block.input))
                )
        return out

    async def complete_json(
        self, *, system: str, user: str, model: str, max_tokens: int = 512
    ) -> dict | None:
        """구조화 판단(라우팅/검증 등). 파싱 실패 시 None (호출부 폴백)."""
        comp = await self.complete(
            system=system + "\n반드시 JSON 객체만 출력한다.",
            messages=[{"role": "user", "content": user}],
            model=model,
            max_tokens=max_tokens,
        )
        text = comp.text.strip()
        # 코드펜스/잡텍스트 방어: 첫 '{' ~ 마지막 '}' 추출
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    async def stream(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """최종 답변 토큰 스트리밍(§06 §6). 타임아웃은 스트림 시작까지 적용."""
        client = self._require()
        try:
            stream_cm = client.messages.stream(
                model=model, max_tokens=max_tokens, system=system, messages=messages
            )
            async with stream_cm as stream:
                async for text in stream.text_stream:
                    yield text
        except asyncio.TimeoutError as e:
            raise LLMTimeout("LLM 응답이 제한 시간을 초과했습니다.") from e


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
