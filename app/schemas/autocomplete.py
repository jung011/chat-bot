"""자동완성 요청·응답 모델 (§03 §3.3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Suggestion(BaseModel):
    text: str
    source: Literal["faq", "document", "log"]


class AutocompleteData(BaseModel):
    query: str
    suggestions: list[Suggestion] = []
