"""청킹 — 의미 단위 분할(메뉴 항목 보존). 줄 단위 청킹 기본."""
from __future__ import annotations


def chunk(text: str, *, min_len: int = 4) -> list[str]:
    chunks: list[str] = []
    for line in text.splitlines():
        line = line.strip(" -•\t")
        if not line:
            continue
        if len(line) < min_len and chunks:
            chunks[-1] = f"{chunks[-1]} {line}"
        else:
            chunks.append(line)
    return chunks
