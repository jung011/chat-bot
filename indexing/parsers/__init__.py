"""문서 파서 (§07 §3.1).

운영에서는 Docling / Upstage Document Parse / PyMuPDF4LLM 등으로 PDF/HWP/이미지를
텍스트+표(마크다운)로 추출한다(메뉴판은 표·가격 구조 보존이 중요). 파일럿 시드는
이미 텍스트이므로 본 파서는 정규화(공백 정리)만 수행하는 pass-through 다.
"""
from __future__ import annotations


def parse_text(raw: str) -> str:
    return "\n".join(line.rstrip() for line in raw.strip().splitlines())
