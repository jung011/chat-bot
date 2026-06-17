"""청킹 (§07 §3.2).

의미 단위 분할. 메뉴는 **항목 단위**로 끊어 "메뉴명+가격+옵션"이 한 청크에 들어가게
한다(수치-항목 분리 방지, §07 §6). 파일럿은 줄 단위(항목형) 청킹을 기본으로 한다.
"""
from __future__ import annotations


def chunk(text: str, *, min_len: int = 4) -> list[str]:
    """비어있지 않은 각 줄을 한 청크로. 너무 짧은 줄은 직전 청크에 병합."""
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
