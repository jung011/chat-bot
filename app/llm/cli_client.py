"""로컬 Claude Code CLI 백엔드 (`claude -p`) — API 키 불필요.

LLMClient 와 동일 인터페이스(complete/complete_json/stream)를 제공해, 오케스트레이션
코드 변경 없이 LLM 호출을 로컬 CLI 로 대체한다(LLM_PROVIDER=claude_cli).

설계 메모:
- 프롬프트는 **stdin** 으로 전달(Windows argv 한글 인코딩 회피). `--output-format json`
  의 `.result`(텍스트)·`.usage` 를 파싱.
- Windows 에서 메인 루프는 SelectorEventLoop(psycopg 용)인데 asyncio subprocess 는
  ProactorEventLoop 가 필요하다. 충돌을 피하려 **동기 subprocess.run 을 asyncio.to_thread**
  로 오프로드한다.
- CLI 는 네이티브 tool_use 가 없으므로, 도구 호출은 **JSON 프로토콜**로 흉내낸다:
  모델이 {"tool_calls":[...]} 또는 {"answer":"..."} 를 출력 → Completion 으로 변환.
  덕분에 agent 노드의 도구 루프(tool_select.py)는 그대로 동작한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess

from app.core.config import settings
from app.core.exceptions import LLMTimeout, UpstreamUnavailable
from app.llm.client import Completion, ToolCall

logger = logging.getLogger("app.llm.cli")


def _alias(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "opus" in m:
        return "opus"
    return "sonnet"


def _render_messages(messages: list[dict]) -> str:
    label = {"user": "사용자", "assistant": "상담원"}
    lines: list[str] = []
    for msg in messages:
        role = label.get(msg["role"], msg["role"])
        content = msg["content"]
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
            continue
        for block in content:
            t = block.get("type")
            if t == "text":
                lines.append(f"{role}: {block['text']}")
            elif t == "tool_use":
                args = json.dumps(block.get("input", {}), ensure_ascii=False)
                lines.append(f"{role} [도구호출] {block['name']}({args})")
            elif t == "tool_result":
                lines.append(f"[도구결과] {block.get('content')}")
    return "\n".join(lines)


def _tool_block(tools: list[dict]) -> str:
    lines = ["[사용 가능한 도구]"]
    for t in tools:
        lines.append(f"- {t['name']}: {t.get('description', '')}")
    lines.append(
        '\n[응답 형식] 도구가 필요하면 아래 JSON만 출력(다른 텍스트 금지):\n'
        '{"tool_calls":[{"name":"도구명","input":{"company_id":"<업체id>", ...}}]}\n'
        '도구 결과로 최종 답변이 가능하면 아래 JSON만 출력:\n'
        '{"answer":"사용자에게 보여줄 답변"}'
    )
    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


class ClaudeCLIClient:
    def __init__(self) -> None:
        # npm 전역 설치는 Windows 에서 claude.cmd 셰임 → PATHEXT 해석 필요.
        # shutil.which 로 실제 경로를 찾고, shell 로 실행한다(프롬프트는 stdin 이라 안전).
        self._cli = shutil.which(settings.claude_cli_path) or settings.claude_cli_path
        self._timeout = settings.llm_timeout_seconds

    @property
    def available(self) -> bool:
        return True

    def _run(self, prompt: str, model_alias: str) -> dict:
        """동기 CLI 호출 (to_thread 로 호출됨). 프롬프트는 stdin 으로 전달."""
        cmd = f'"{self._cli}" -p --model {model_alias} --output-format json'
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
                shell=True,
            )
        except subprocess.TimeoutExpired as e:
            raise LLMTimeout("로컬 Claude CLI 응답이 제한 시간을 초과했습니다.") from e
        if proc.returncode != 0:
            raise UpstreamUnavailable(f"claude CLI 오류: {(proc.stderr or '')[:300]}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise UpstreamUnavailable("claude CLI 출력 파싱 실패") from e

    async def _call(self, prompt: str, model: str) -> tuple[str, int, int]:
        data = await asyncio.to_thread(self._run, prompt, _alias(model))
        usage = data.get("usage", {}) or {}
        return (
            str(data.get("result", "")),
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        )

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> Completion:
        parts = [system]
        if tools:
            parts.append(_tool_block(tools))
        parts.append("[대화]\n" + _render_messages(messages))
        text, in_tok, out_tok = await self._call("\n\n".join(parts), model)

        out = Completion(input_tokens=in_tok, output_tokens=out_tok, stop_reason="end_turn")
        if tools:
            data = _extract_json(text)
            if data and isinstance(data.get("tool_calls"), list):
                for i, tc in enumerate(data["tool_calls"]):
                    out.tool_calls.append(
                        ToolCall(id=f"call_{i}", name=tc.get("name", ""), input=tc.get("input", {}) or {})
                    )
                return out
            if data and "answer" in data:
                out.text = str(data["answer"])
                return out
        out.text = text.strip()
        return out

    async def complete_json(
        self, *, system: str, user: str, model: str, max_tokens: int = 512
    ) -> dict | None:
        text, _, _ = await self._call(f"{system}\n반드시 JSON 객체만 출력한다.\n\n{user}", model)
        return _extract_json(text)

    async def stream(
        self, *, system: str, messages: list[dict], model: str, max_tokens: int = 1024
    ):
        """CLI 는 스트리밍 미지원 → 전체 응답을 받아 청크로 흘려보낸다."""
        comp = await self.complete(system=system, messages=messages, model=model, max_tokens=max_tokens)
        text = comp.text or ""
        for i in range(0, len(text), 24):
            yield text[i : i + 24]
