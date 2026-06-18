"""테넌트 레지스트리 (§01 §4.2, §02 §6).

`configs/tenants.yaml` 를 단일 소스로 로드한다. 업체별 persona/business_info/
FAQ 설정을 조회하는 진입점이며, 결정적 라우팅(router.py)의 데이터 소스다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from app.core.config import settings


@dataclass(frozen=True)
class FaqConfig:
    # collection 은 seed 데이터 적재용(orchestrator가 데이터 로더). 매칭 임계값(threshold)은
    # faq 서버가 소유하므로 여기 두지 않는다(중복 제거).
    collection: str
    vector_db: str
    server_url: str = ""   # 업체별 FAQ MCP 서버 URL(A안)


@dataclass(frozen=True)
class RetrievalConfig:
    doc_top_k: int
    doc_top_n: int
    tool_top_k: int


@dataclass(frozen=True)
class Tenant:
    company_id: str
    name: str
    status: str
    persona: str
    business_info: dict
    faq: FaqConfig
    retrieval: RetrievalConfig = field(repr=False)
    general_server_url: str = ""   # 업체별 일반(도메인) MCP 서버 URL(A안). 비면 인프로세스.

    @property
    def active(self) -> bool:
        return self.status == "active"

    def business_info_text(self) -> str:
        """LLM 프롬프트 주입용 영업정보 문자열(§06 §4.4 {business_info})."""
        bi = self.business_info
        lines = [f"- 상호: {self.name}"]
        labels = {
            "phone": "전화",
            "address": "주소",
            "hours": "영업시간",
            "delivery": "배달",
        }
        for key, label in labels.items():
            if bi.get(key):
                lines.append(f"- {label}: {bi[key]}")
        return "\n".join(lines)


class TenantRegistry:
    def __init__(self, tenants: dict[str, Tenant]):
        self._tenants = tenants

    def get(self, company_id: str) -> Tenant | None:
        return self._tenants.get(company_id)

    def exists(self, company_id: str) -> bool:
        t = self._tenants.get(company_id)
        return t is not None and t.active

    def all(self) -> list[Tenant]:
        return list(self._tenants.values())


def _build_registry() -> TenantRegistry:
    with open(settings.tenants_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    defaults = raw.get("defaults", {})
    d_ret = defaults.get("retrieval", {})

    tenants: dict[str, Tenant] = {}
    for cid, c in (raw.get("companies") or {}).items():
        faq = c.get("faq", {})
        tenants[cid] = Tenant(
            company_id=cid,
            name=c.get("name", cid),
            status=c.get("status", "active"),
            persona=c.get("persona", ""),
            business_info=c.get("business_info", {}) or {},
            faq=FaqConfig(
                collection=faq.get("collection", f"faq_{cid}"),
                vector_db=faq.get("vector_db", "localhost:6333"),
                server_url=faq.get("server_url", ""),
            ),
            retrieval=RetrievalConfig(
                doc_top_k=int(d_ret.get("doc_top_k", 20)),
                doc_top_n=int(d_ret.get("doc_top_n", 5)),
                tool_top_k=int(d_ret.get("tool_top_k", 5)),
            ),
            general_server_url=c.get("general_server_url", ""),
        )
    return TenantRegistry(tenants)


@lru_cache
def get_registry() -> TenantRegistry:
    return _build_registry()
