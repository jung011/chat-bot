"""모델 티어 (§06 §1).

단계별로 모델을 분리해 속도·비용·품질을 균형 맞춘다.
모델 ID 는 여기서 상수로 관리하고, 단계→모델 매핑을 설정으로 둔다.
"""
from __future__ import annotations

from enum import Enum

from app.core.config import settings

# 모델 ID (§환경 — config 의 llm_model_* 로 외부화)
LIGHT = settings.llm_model_light  # Claude Haiku 4.5 — 재작성/라우팅/평가
MAIN = settings.llm_model_main    # Claude Sonnet 4.6 — 최종 답변 생성(기본)
HEAVY = settings.llm_model_heavy  # Claude Opus 4.8 — 복잡한 다단계 추론


class Stage(str, Enum):
    REWRITE = "rewrite"
    ROUTE = "route"
    TOOL_SELECT = "tool_select"
    GENERATE = "generate"
    VERIFY = "verify"


# 단계 → 모델 매핑 (§06 §1, §4)
STAGE_MODEL: dict[Stage, str] = {
    Stage.REWRITE: LIGHT,
    Stage.ROUTE: LIGHT,
    Stage.TOOL_SELECT: MAIN,
    Stage.GENERATE: MAIN,
    Stage.VERIFY: LIGHT,
}


def model_for(stage: Stage) -> str:
    return STAGE_MODEL.get(stage, MAIN)
