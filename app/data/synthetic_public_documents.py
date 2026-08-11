"""Fake public document dataset (PROJECT_SPEC.md section 52).

Stands in for what a real news/DART provider would eventually fetch, so the
parsing/chunking/embedding/ranking pipeline can be built and tested before
Phase 7-9 add any actual network code. None of this touches the internet —
it's a static local fixture, same spirit as the synthetic financial data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicDocument:
    public_document_id: str
    source: str
    title: str
    published_at: str  # ISO date
    url: str
    public_company: str
    content: str

    @property
    def snippet(self) -> str:
        return self.content[:80] + ("..." if len(self.content) > 80 else "")


SYNTHETIC_PUBLIC_DOCUMENTS: list[PublicDocument] = [
    PublicDocument(
        "DOC-001",
        "synthetic-news",
        "ABC Manufacturing, 신규 생산라인 증설",
        "2026-02-14",
        "https://example.invalid/news/doc-001",
        "ABC Manufacturing",
        "ABC Manufacturing이 국내 공장에 신규 생산라인을 증설한다고 밝혔다. "
        "회사 측은 이번 증설로 생산능력이 확대될 것이라고 설명했다. 구체적인 "
        "투자 규모와 완공 시점은 추후 공시를 통해 공개할 예정이다.",
    ),
    PublicDocument(
        "DOC-002",
        "synthetic-news",
        "ABC Manufacturing, 신규 공장 착공",
        "2026-03-02",
        "https://example.invalid/news/doc-002",
        "ABC Manufacturing",
        "ABC Manufacturing이 제2공장 착공식을 진행했다고 밝혔다. 신공장은 기존 "
        "설비 대비 자동화 수준을 높여 생산능력을 확대하는 것을 목표로 한다. "
        "회사는 이를 위한 시설자금 조달 계획도 함께 검토 중이라고 전했다.",
    ),
    PublicDocument(
        "DOC-003",
        "synthetic-news",
        "ABC Manufacturing, 배당정책 변경",
        "2026-01-20",
        "https://example.invalid/news/doc-003",
        "ABC Manufacturing",
        "ABC Manufacturing 이사회가 배당성향을 조정하는 배당정책 변경안을 "
        "의결했다고 공시했다. 주주환원 정책의 일환이라고 회사는 설명했다.",
    ),
    PublicDocument(
        "DOC-004",
        "synthetic-news",
        "ABC Manufacturing, 대표이사 선임",
        "2025-12-05",
        "https://example.invalid/news/doc-004",
        "ABC Manufacturing",
        "ABC Manufacturing이 임시주주총회를 통해 신임 대표이사를 선임했다고 "
        "밝혔다. 신임 대표는 기존 경영전략을 유지하겠다고 밝혔다.",
    ),
    PublicDocument(
        "DOC-005",
        "synthetic-dart",
        "ABC Manufacturing, 유형자산 취득 결정 공시",
        "2026-02-20",
        "https://example.invalid/dart/doc-005",
        "ABC Manufacturing",
        "ABC Manufacturing은 생산설비 확충을 위해 기계장치 및 구축물을 "
        "취득하기로 결정했다고 공시했다. 취득 자금은 자체자금과 차입금으로 "
        "조달할 예정이라고 밝혔다.",
    ),
    PublicDocument(
        "DOC-006",
        "synthetic-news",
        "Sample Electronics, 주요 고객사向 매출 비중 관련 우려 보도",
        "2026-01-10",
        "https://example.invalid/news/doc-006",
        "Sample Electronics",
        "업계에서는 Sample Electronics의 매출이 소수 고객사에 집중되어 있어 "
        "해당 고객사의 발주 감소가 실적에 영향을 줄 수 있다는 분석이 나왔다.",
    ),
    PublicDocument(
        "DOC-007",
        "synthetic-news",
        "Sample Electronics, 매출채권 관리 강화 방침 발표",
        "2026-03-15",
        "https://example.invalid/news/doc-007",
        "Sample Electronics",
        "Sample Electronics가 매출채권 회수 절차를 강화하는 내부 방침을 "
        "마련했다고 밝혔다. 최근 일부 거래처의 결제 지연이 있었던 것으로 "
        "알려졌다.",
    ),
    PublicDocument(
        "DOC-008",
        "synthetic-news",
        "Sample Electronics, 신제품 출시 지연",
        "2025-11-22",
        "https://example.invalid/news/doc-008",
        "Sample Electronics",
        "Sample Electronics가 계획했던 신제품 출시가 일정보다 지연되고 있다고 "
        "밝혔다. 회사는 품질 검증 절차를 이유로 들었다.",
    ),
]


def documents_for_company(public_company: str) -> list[PublicDocument]:
    return [doc for doc in SYNTHETIC_PUBLIC_DOCUMENTS if doc.public_company == public_company]
