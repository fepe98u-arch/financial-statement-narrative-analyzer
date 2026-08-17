# Financial Statement Narrative Analyzer — Project Spec

재무제표 관계 기반 이상징후 및 사업맥락 분석 시스템

이 문서는 보스가 작성한 프로젝트 스펙 원문입니다. 개발 중 판단이 필요할 때는
항상 이 문서를 1차 기준으로 삼습니다. 특히 0~2장(보안 원칙), 3~4장(기술 스택),
59~60장(환경설정/Git 주의사항)은 어떤 상황에서도 우선합니다.

---

## 0. 프로젝트의 가장 중요한 원칙

이 프로젝트에서 가장 중요한 것은 보안이다.

향후 프로그램은 아직 외부에 공개되지 않은 재무제표, 회계자료, 감사대상 회사의
내부정보를 처리할 가능성이 있다.

따라서 프로그램을 다음 두 영역으로 명확하게 분리한다.

1. PRIVATE ANALYSIS ZONE
2. PUBLIC DATA COLLECTION ZONE

PRIVATE ANALYSIS ZONE에서는:

- 미공개 재무제표
- 재무수치
- 계정별 증감
- Cross-Account Pattern
- Historical Pattern
- 조사 가설
- Investigation Question
- 내부 분석결과
- 회계사의 Review
- Local AI 분석

을 처리한다.

이 정보는 절대 외부 인터넷 서비스로 전송하지 않는다.

PUBLIC DATA COLLECTION ZONE에서는:

이미 공개되어 있는 정보를 외부에서 가져오는 역할만 수행한다.

예:

- 공개 회사명
- DART corp_code
- 공개된 회사 식별자
- 조회 시작일
- 조회 종료일
- 공개 사업보고서
- 공개 공시
- 공개 뉴스

만 사용할 수 있다.

---

## 1. 핵심 보안 철학

이 프로그램의 원칙은:

"내부정보를 이용해 외부에 질문하지 않는다."

이다.

예를 들어 내부 분석 결과가:

재고자산 -38%
구축물 +82%
기계장치 +51%
장기차입금 +70%

이라고 하더라도 외부 서비스에 다음과 같이 보내면 안 된다.

금지: "A회사의 재고가 감소하고 구축물이 증가했는데 사업을 확장하는 것인가?"
금지: "A회사 시설투자 증가 원인"
금지: "A회사 구축물 증가"
금지: "A회사 차입금 증가 이유"
금지: "A회사 사업확장"

위 검색어가 내부 재무분석 결과에서 직접 도출된 경우에는 외부 검색어로 사용하지 않는다.

대신 외부에는 가능하면: A회사 / 조회기간 / 공개 회사 식별자 정도만 전달한다.
그리고 A회사와 관련된 공개자료를 넓게 가져온다.

그 후: "이 자료가 내부 조사 가설과 관련 있는가?" 라는 판단은
PRIVATE ANALYSIS ZONE에서 Local AI가 수행한다.

---

## 2. 중요한 현실적인 설명

인터넷에서 정보를 자동으로 가져오기 위해서는 외부 서버에 최소한의 요청은 보내야 한다.

따라서: "프로그램에서 외부로 아무 정보도 나가지 않는다" 라고 거짓으로 주장하지 않는다.

대신 외부로 나갈 수 있는 정보는 엄격하게 Allowlist로 제한한다.

허용 가능한 Outbound Data:

- public_company_name
- public_company_identifier
- dart_corp_code
- date_from
- date_to
- page_number
- 공개 문서 receipt number
- 공개 API 요청에 필요한 최소 technical parameter

금지되는 Outbound Data:

- financial_statement
- financial_amount
- account_name derived from private analysis
- account_change_rate
- detected_pattern
- internal_pattern_score
- investigation_question
- internal_hypothesis
- internal_summary
- user_review
- audit_comment
- imported private document content
- local file content
- private document filename
- private company metadata not already public

---

## 3. 프로그램 형태

웹사이트를 만들지 않는다. Streamlit 금지. Flask 금지. Django 금지.
localhost 기반 웹앱도 만들지 않는다.

Windows에서 직접 실행되는 Desktop Application으로 만든다.

GUI: PySide6 를 사용한다.

최종적으로: FinancialStatementAnalyzer.exe 형태의 Windows 실행 프로그램으로
패키징할 수 있게 설계한다.

---

## 4. 기술 스택

사용: Python, PySide6, Polars, PostgreSQL, SQLAlchemy, psycopg(또는 현재 권장
PostgreSQL Driver), numpy, scikit-learn, sentence-transformers, rapidfuzz, pytest.
필요하면: PyArrow, Parquet.

사용하지 않는 것: Streamlit, SQLite, Cloud Database, Cloud Storage, OpenAI API,
Claude API, Gemini API, 외부 Embedding API, 외부 LLM API.

---

## 5. 개발 단계 데이터 보안

현재 개발에는 Claude Code를 사용한다. 하지만 Claude Code 역시 외부 AI 서비스라는
점을 전제로 한다.

따라서 개발 과정에서: 실제 미공개 재무제표 / 실제 감사자료 / 실제 고객자료 /
실제 내부문서 / 실제 감사조서 를 절대 사용하지 않는다.

개발 및 테스트는 Synthetic Data만 사용한다.

가상 회사: ABC Manufacturing, Sample Electronics, 가상제조주식회사 등을 사용한다.

실제 운영 데이터 폴더는 Claude Code가 접근하는 개발 프로젝트 폴더와 분리하는
것을 전제로 한다.

---

## 6. 프로그램의 업무 목적

이 프로그램은 단순히 "매출이 15% 감소했습니다." "재고가 30% 증가했습니다." 라고
알려주는 프로그램이 아니다.

목표는 숙련된 회계사가 재무제표를 보면서 "왜?" 라고 질문하는 사고방식을
시스템화하는 것이다.

예: 매출 ↓ + 매출채권 ↑ → "매출이 감소했는데 매출채권이 증가한 이유는 무엇인가?"

또는: 재고 ↓ + 구축물 ↑ + 기계장치 ↑ + 건설중인자산 ↑ + 장기차입금 ↑ →
"생산시설 확대 또는 사업구조 변화와 관련된 사업적 사건이 존재하는가?"

다만 프로그램은 원인을 확정하지 않는다.

---

## 7. 분석 엔진 구조

1. Financial Data Loader
2. Account Normalizer
3. Financial Metric Engine
4. Relationship Rule Engine
5. Business Narrative Pattern Engine
6. Historical Pattern Engine
7. Investigation Question Engine
8. Public Data Collector
9. Local Public Document Analyzer
10. Local RAG
11. Human Review

---

## 8. Financial Data Loader

지원: Excel, CSV, 필요하면 Parquet.

초기 버전에서는 PDF 재무제표 OCR을 하지 않는다. 구조화된 Excel / CSV를 우선한다.

파일은 Local에서만 읽는다. 외부 서버로 Upload하지 않는다.

---

## 9. Polars

재무데이터 처리는 Polars를 기본으로 한다.

가능하면: read_csv, read_excel compatible method, scan_csv, scan_parquet, select,
with_columns, filter, join, group_by, unique, Lazy API 를 사용한다.

대용량 데이터에서 Python row-by-row loop를 불필요하게 사용하지 않는다.

---

## 10. 계정 표준화

서로 다른 연도의 계정명이 다를 수 있다.
예: 매출채권 / 매출채권및기타채권 / 외상매출금

다음 구조를 사용한다: raw_account_name, canonical_account_name, mapping_method,
mapping_confidence

mapping_method: EXACT, ACCOUNT_DICTIONARY, FUZZY, MANUAL, UNRESOLVED

모호한 경우 자동으로 확정하지 않는다.

---

## 11. Business Dimension

계정을 사업 의미 단위로 분류한다.
예: SALES, RECEIVABLE, INVENTORY, OPERATING_COST, CAPEX, FINANCING,
CASH_GENERATION, R&D, CREDIT_RISK

CAPEX에는 예를 들어: 토지, 건물, 구축물, 기계장치, 건설중인자산, 유형자산 취득
관련 CF 등을 포함할 수 있다.

---

## 12. 기본 재무 분석

계산 가능한 경우: 매출증가율, 영업이익증가율, 매출채권증가율, 재고증가율,
유형자산증가율, 차입금증가율, 영업CF 변화율, 매출채권/매출, 재고/매출,
차입금/총자산, 영업CF/순이익, CAPEX 관련 지표, DSO 관련 지표, 재고회전 관련
지표 등을 계산한다.

계산 불가능한 값은 임의로 추정하지 않는다.

---

## 13. Relationship Rule Engine

비교적 직접적인 관계를 탐지한다.

예: 매출↓+매출채권↑ / 매출↓+재고↑ / 순이익↑+영업CF↓ /
매출↑+매출채권이 훨씬 더 빠르게↑ / 매출↑+재고가 훨씬 더 빠르게↑ /
유형자산↑+감가상각비 변화가 비정상적으로 작음 / 차입금↑+이자비용 변화가 미미함

이 결과를 "오류"라고 부르지 않는다. "Review Pattern" 또는 "Attention Pattern"
이라고 한다.

---

## 14. Business Narrative Pattern Engine

직접적인 회계 관계가 아니더라도 여러 계정의 움직임을 같이 본다.

예: 재고↓, 구축물↑, 기계장치↑, 건설중인자산↑, 장기차입금↑, CAPEX↑

프로그램은 "재고와 구축물은 원래 같이 움직여야 한다" 라고 주장하지 않는다.

대신: "생산 및 투자 관련 자산이 확대되는 가운데 재고자산은 감소했습니다.
이러한 변화가 동일한 사업적 사건이나 사업전략 변화와 관련되어 있는지 추가적인
설명이 필요할 수 있습니다." 라고 표현한다.

---

## 15. Cross-Account Cluster

모든 계정의 모든 가능한 Pair를 무작정 비교하지 않는다.

Business Dimension 기준으로 Cluster Pattern을 만든다.
예: CAPEX/FINANCING, Working Capital, Revenue/Receivable, Profit/Cash Flow,
Inventory/Production, Credit Risk

예: CAPEX/FINANCING Pattern — 구축물 +88%, 기계장치 +54%, 건설중인자산 +143%,
차입금 +72%

---

## 16. Pattern Priority Score

각 Pattern에 Review Priority Score를 계산할 수 있다.

Score는 오류 확률이 아니다. 분식 확률이 아니다. 감사위험 확률이 아니다.

단순히 "얼마나 먼저 살펴볼 만한가?" 를 나타낸다.

가능한 요소: 변동 규모, 관련 계정 수, 재무적 중요성, 과거 패턴 대비 변화,
신규 Pattern 여부, 재무제표 간 일관성, 관련 Ratio 변화

---

## 17. Historical Pattern Engine

당기 Pattern을 과거 3~5년과 비교한다.

분류: NEW_PATTERN, RECURRING_PATTERN, INTENSIFIED_PATTERN, NORMAL_RANGE,
REVERSAL_PATTERN

예: 2022(재고 -7%, 구축물 +15%, 차입금 +10%) → 2026(재고 -38%, 구축물 +88%,
차입금 +72%) 이면, 과거에도 유사 방향이 있었지만 현재 변화 규모가 훨씬 커졌다면
INTENSIFIED_PATTERN 으로 분류할 수 있다.

---

## 18. Pattern Similarity

Current Pattern과 Historical Pattern을 비교한다.

구분: Direction Similarity, Magnitude Similarity

Similarity %를 표시한다면 반드시 실제 계산식으로 생성한다. AI가 임의의 숫자를
생성하면 안 된다.

---

## 19. Investigation Question Engine

내부 재무 Pattern을 기반으로 조사 질문을 생성한다.

예: 재고↓ 구축물↑ 기계장치↑ 차입금↑ → "생산시설 또는 사업 확장이 있었는가?"
"신규 설비투자가 있었는가?" "대규모 CAPEX 계획이 존재하는가?"
"신규 차입이 투자활동과 관련되는가?" "생산능력 변화가 있었는가?"

중요: 이 Investigation Question은 PRIVATE DATA이다.

따라서 이 질문을 그대로 Google, Naver, 뉴스 API, DART API, 외부 LLM 등에
보내지 않는다.

---

## 20. 가장 중요한 공개자료 수집 구조

외부 인터넷 모듈은 내부 Investigation Question을 알아서는 안 된다.

흐름: PRIVATE ZONE(재무제표 → Pattern → Investigation Question) — 여기서 외부로
직접 연결하지 않는다.

별도로: PUBLIC DATA COLLECTION ZONE — public company identifier + date range
만 사용해서 해당 회사와 관련된 공개자료를 넓게 수집한다.

예: A회사 2025-01-01~2026-08-11 → A회사 관련 공개 기사 200건, A회사 관련 DART
공시 50건. 그다음 이 자료를 Local로 가져온다.

---

## 21. Public Data Collector의 입력을 강제 제한

Public Data Collector 함수 또는 Class가 받을 수 있는 Parameter를 명시적으로
제한한다.

예: PublicCollectionRequest fields: public_company_name,
public_company_identifier, dart_corp_code, date_from, date_to, page, page_size,
topic_keyword

topic_keyword: 2026-08-17 대표 승인으로 추가된 유일한 예외 (섹션 25 참고).
요청 1건당 정확히 1개, 사전 승인된 계정명 목록
(app/analysis/investigation_questions.py의 search_keyword_for())에서만 가져온다.
증감방향, 수치, 조사질문 전체, 패턴명/점수는 절대 포함할 수 없다.

허용하지 않는 fields: financial_data, financial_amount, detected_pattern,
pattern_score, investigation_question, internal_hypothesis, internal_summary,
audit_comment, private_document

가능하면 Python type / dataclass / schema로 이 구조를 강제한다.

---

## 22. Public Data Collector는 내부 객체 접근 금지

Public Data Collector에서 다음 객체를 Import하거나 참조하지 않는다:
FinancialStatement, DetectedPattern, InvestigationQuestion,
PrivateAnalysisResult, HumanReview

Public Data Collector는 내부 분석 엔진과 최대한 독립적인 Module로 만든다.

---

## 23. Public Data Collector

외부 공개자료 수집 기능은 한 곳에서만 구현한다.

예: public_data_collector/ { base.py, dart_provider.py, news_provider.py,
schemas.py, network_guard.py }

다른 Module이 requests.get, httpx.get, urllib, aiohttp 등을 직접 호출하지 않는다.

---

## 24. DART 자료 수집

OpenDART API를 이용할 경우: 공개 회사명, corp_code, receipt number, date range
등 공개정보만 사용한다.

내부 재무 Pattern이나 Investigation Question은 DART 요청에 절대 포함하지 않는다.

DART_API_KEY는 환경변수로 관리한다.

---

## 25. 뉴스 자료 수집

뉴스 Provider도 동일한 원칙을 적용한다.

기본: public_company_name, date range 만으로 회사 관련 기사를 넓게 가져온다.

**2026-08-17 대표 승인 예외**: 네이버 뉴스 검색 API는 날짜 범위 지정 기능이
없고 최대 1,000건까지만 조회 가능해서, 뉴스가 많이 나오는 회사는 회사명만으로
검색하면 최근 며칠치만으로 1,000건이 다 차버려 기말감사 대상 기간(1/1~12/31)
전체를 커버하지 못하는 문제가 실측으로 확인됐다 (예: LG에너지솔루션 — 회사명만
검색 시 296건이 전부 최근 3~4일치, 계정명 키워드 1개를 추가하자 같은 검색이
2026년 1월 이전까지 도달함).

이 문제를 해결하기 위해, Attention Pattern별로 미리 정의해 둔 소수의 계정명
키워드 목록(app/analysis/investigation_questions.py의 *_SEARCH_KEYWORD,
search_keyword_for()) 중 **정확히 1개**를 public_company_name과 함께 검색어에
추가할 수 있다. 이 키워드는:

- 반드시 사전에 정의된 목록에서만 골라야 한다 (사람이 즉석에서 입력하거나
  다른 방식으로 고른 텍스트는 금지).
- 계정명 수준의 단어만 허용한다 (예: "이자비용", "지분법손익", "매출채권").
- 증감방향("증가"/"감소"/"급증"/"급감" 등), 수치, 조사질문 전체, 패턴명/점수는
  절대 포함할 수 없다 — 이 제약은
  tests/test_investigation_questions.py의
  test_search_keywords_contain_no_directional_or_judgment_words로
  자동 검증된다.

그 외의 원칙은 그대로 유지된다: 검색어에 그 이상의 어떤 내부 분석 결과도
자동 추가하지 않는다.

---

## 26. Public Data Intake

수집된 공개자료는 Local PC로 가져온다.

최소 저장: source, title, published_at, url, public_document_id,
public_company, content if legally/API-supported, snippet if
legally/API-supported

저작권 및 Provider 정책을 준수한다. 기사 전체 본문을 무단 Scraping하지 않는다.
Provider가 제공하는 허용된 범위만 사용한다.

---

## 27. Local Relevance Matching

여기서부터 다시 PRIVATE ZONE이다.

입력: 내부 Investigation Question + 가져온 공개기사/공개공시

예: 내부 질문 "생산시설 또는 사업 확장이 있었는가?" + 공개기사 200건

Local AI가 Semantic Similarity, Keyword Relevance, Date Relevance, Document
Type 등을 이용해 관련자료를 Ranking한다.

이 과정은 100% Local에서 수행한다.

---

## 28. Local Embedding

sentence-transformers 기반 Local Embedding을 사용할 수 있다.

모델은 Local Path에서 불러온다. 예: models/embedding/

외부 Embedding API를 사용하지 않는다.

Private Investigation Question 및 Public Document 를 모두 Local에서
Embedding한다.

---

## 29. Local Reranking

필요한 경우 Local Cross Encoder 또는 Local Reranker를 사용한다.

구조: 공개자료 200건 → Embedding Top 20 → Local Reranker → Top 5

전부 Local에서 수행한다.

---

## 30. Local RAG

가져온 DART 사업보고서, 공시자료, 공개기사를 Local에서 분석한다.

Document → Parsing → Chunking → Local Embedding → Local Vector Search →
Relevant Evidence

외부 LLM API를 호출하지 않는다.

---

## 31. Evidence Classification

찾은 공개자료는 다음처럼 분류할 수 있다: SUPPORTED, POSSIBLE,
NO_EVIDENCE_FOUND, CONFLICTING_EVIDENCE

SUPPORTED: 공개자료가 해당 사업적 사건을 직접적으로 설명하는 경우

POSSIBLE: 관련 내용은 있지만 재무제표 변화의 직접적인 원인이라고 확정할 수
없는 경우

예: 내부 Pattern(재고↓ 구축물↑ 차입금↑) + 공개 기사("A사, 신규 생산라인 증설")
→ 결과: POSSIBLE

단순히 기사 하나가 있다고 해서 "차입금 증가 원인은 생산라인 증설이다" 라고
확정하지 않는다.

---

## 32. 내부 정보와 공개자료의 화면 표시

UI에서는 두 영역을 명확히 구분한다.

예: PRIVATE FINANCIAL ANALYSIS (재고자산 -38%, 구축물 +82%, 차입금 +70%,
Investigation Question: "생산시설 확대가 있었는가?")

아래: PUBLIC EVIDENCE (수집된 공개자료: 143건, 관련도 높은 자료 1~3 목록)

반드시 "공개자료" 와 "프로그램의 추론" 을 구분해서 표시한다.

---

## 33. 사용자에게 Network 상태 표시

프로그램 상단에 Network 상태를 명확하게 표시한다.

예: 🔒 PRIVATE ANALYSIS: LOCAL ONLY / 🌐 PUBLIC DATA COLLECTION: OFF

사용자가 공개자료 수집을 시작하면: 🌐 PUBLIC DATA COLLECTION: ACTIVE

수집 종료 후: 🌐 PUBLIC DATA COLLECTION: IDLE

---

## 34. 공개자료 수집은 사용자 요청 시에만

프로그램 실행 직후 자동으로 인터넷에 접속하지 않는다.

사용자가 [공개자료 가져오기] 를 눌렀을 때만 Public Data Collector가 실행된다.

---

## 35. 공개자료 수집 전 확인창

처음 실행할 경우 다음과 유사한 설명을 보여준다.

"공개자료 수집 기능은 인터넷을 사용합니다. 외부 서비스에는 공개 회사
식별정보와 조회기간 등 최소한의 정보만 전달합니다. 미공개 재무제표,
재무수치, 내부 분석결과, Investigation Question은 외부로 전송되지 않습니다."

사용자 확인 후 실행한다.

---

## 36. Network Guard

모든 외부 요청 전에 Request Object를 검사한다.

허용 Field만 Outbound Request에 포함할 수 있게 한다. Allowlist 방식으로
구현한다.

가능하면: OutboundRequestValidator 를 만든다.

허용된 key 이외의 값이 포함되면: SecurityException 을 발생시키고 요청을
차단한다.

---

## 37. Numeric Leakage Guard

외부 요청 Query 또는 Payload에 내부 재무숫자가 섞이는 것을 방지하는 추가
Guard를 구현한다.

단: 날짜, page number, corp_code 등 정상적인 숫자까지 무조건 차단하면 안 된다.

따라서 단순 Regex 하나로 "숫자가 있으면 금지" 같은 방식은 사용하지 않는다.

Outbound Request는 처음부터 정의된 Schema에서 생성되게 한다.

---

## 38. Secret Leakage Guard

외부 요청과 로그에서: DATABASE_URL, DB Password, DART_API_KEY, 기타 API Key
가 노출되지 않게 한다.

---

## 39. PostgreSQL

SQLite를 사용하지 않는다. PostgreSQL 사용.

기본: Local PostgreSQL (Desktop App → 127.0.0.1 → PostgreSQL)

Cloud PostgreSQL 사용 금지.

---

## 40. PostgreSQL Table

합리적인 범위에서: companies, financial_facts, account_mappings,
business_dimensions, analysis_runs, relationship_rules, detected_patterns,
pattern_accounts, historical_patterns, pattern_similarities,
investigation_questions, human_reviews, public_documents, document_chunks,
retrieval_hits, public_collection_runs, security_events, model_configs 등을
고려한다.

---

## 41. Local AI가 없을 때

AI Model이 없어도 프로그램의 핵심 기능은 작동해야 한다.

AI 없이 가능한 기능: 재무제표 로딩, 증감률, 재무비율, Relationship Rule,
Narrative Pattern, Historical Pattern, Priority Score, Template Question,
Excel Export

Local AI가 필요한: Semantic Search, Embedding Ranking, Local RAG 등만
비활성화한다.

---

## 42. Model Download

프로그램이 Local AI Model을 자동 다운로드하지 않는다.

모델이 없으면: "Local AI model is not installed." 를 표시한다.

사용자가 직접 준비한 Local Model을 선택할 수 있게 한다.

---

## 43. 로그 보안

로그에 다음을 기록하지 않는다: 전체 재무제표, 전체 재무수치, 내부
Investigation Question 전체, 감사인의 Review 전체, API Key, DB Password,
Private Document Body

로그에는 필요한 최소한: timestamp, event_type, success/failure, provider,
error_code, records_count 정도만 사용한다.

---

## 44. Cloud Sync Warning

실제 데이터 폴더가 OneDrive, Dropbox, Google Drive, iCloud 등의 동기화
폴더일 가능성이 있으면 Warning을 표시한다. 자동 이동하지 않는다.

> 참고: 현재 개발 폴더 자체가 OneDrive 경로("바탕 화면\...") 아래에 있다.
> 개발/스펙 문서는 Synthetic Data만 다루므로 문제 없지만, Phase 4 이후 실제
> DB나 실 데이터 폴더를 지정할 때는 이 경고 로직이 반드시 작동해야 한다.

---

## 45. Desktop UI

PySide6로 구현한다.

좌측 Sidebar 예: Dashboard, 재무제표 불러오기, Account Mapping, Financial
Trend, Attention Patterns, Historical Analysis, Investigation Questions,
Public Data, Evidence Analysis, Human Review, Database, Security

---

## 46. Dashboard 예시

상단: Financial Statement Narrative Analyzer / 🔒 PRIVATE ANALYSIS: LOCAL
ONLY / 🌐 PUBLIC DATA COLLECTION: OFF

중앙: 회사 / 분석기간 / 연결·별도

주요 변화: 매출, 매출채권, 재고, 구축물, 기계장치, 차입금, 영업CF

주목 Pattern: CAPEX/FINANCING, WORKING CAPITAL, CASH FLOW

---

## 47. Pattern Detail 화면

예: PATTERN 01 — 재고자산 -38%, 구축물 +82%, 기계장치 +51%, 건설중인자산
+114%, 장기차입금 +70%

Historical: 2022 Similar Pattern / 2026 Intensified Pattern

Investigation Questions: "생산시설 확대가 있었는가?" "신규 CAPEX 계획이
존재하는가?" "차입금 증가와 투자활동이 관련되는가?"

버튼: [공개자료 가져오기]

중요: 이 버튼이 Investigation Question을 외부 검색어로 보내면 안 된다.

---

## 48. 공개자료 가져오기 동작

[공개자료 가져오기] 클릭 → Public Data Collector

전달: public_company_name, public identifier, date range
전달하지 않음: Pattern, Question, Financial Data

→ 기사/DART 자료 수집 → Local DB 저장 → PRIVATE ZONE으로 전달 →
Local AI Ranking

---

## 49. Human-in-the-Loop

Pattern마다 사용자가: 유의미함 / 유의미하지 않음 / 추가조사 필요 /
설명 확인 완료 / 보류 를 선택할 수 있게 한다.

Public Evidence마다: 관련 있음 / 관련 없음 / 가능한 설명 / 직접적 근거 를
선택할 수 있게 한다.

---

## 50. 프로그램이 하지 않는 것

다음 표현을 자동 확정하지 않는다: "분식" "오류" "부정" "이것이 원인"
"감사위험 확정" "반드시 수정 필요"

대신: "주목할 Pattern" "추가 확인 필요" "가능한 설명 후보" "관련 공개자료
발견" 등을 사용한다.

---

## 51. Synthetic Test Data

실제 회사자료를 사용하지 않는다.

ABC Manufacturing 5개년 데이터를 만든다.

2026: 재고 크게 감소, 구축물 크게 증가, 기계장치 증가, 건설중인자산 증가,
장기차입금 증가, CAPEX 증가

별도 Pattern: 매출 감소, 매출채권 증가, 영업CF 감소, 대손충당금 증가

---

## 52. Synthetic Public News

외부 뉴스 기능이 완성되기 전에는 Fake Public News Dataset을 만든다.

예: 기사1 "ABC Manufacturing, 신규 생산라인 증설" / 기사2 "ABC Manufacturing,
신규 공장 착공" / 기사3 "ABC Manufacturing, 배당정책 변경" / 기사4
"ABC Manufacturing, 대표이사 선임"

Local AI가 Investigation Question("생산시설 확대가 있었는가?")과 기사1/기사2를
높은 관련도로 찾아내는지 테스트한다.

---

## 53. Security Test

pytest로 최소 다음을 테스트한다.

1. 프로그램 시작 시 Private Analysis는 Local Only
2. 프로그램 시작 시 Public Collection 자동 실행 안 됨
3. 재무제표 내용이 Outbound Request에 포함되지 않음
4. Detected Pattern이 Outbound Request에 포함되지 않음
5. Investigation Question이 Outbound Request에 포함되지 않음
6. Internal Hypothesis가 Outbound Request에 포함되지 않음
7. Public Data Collector가 허용 Schema 외 필드를 받지 못함
8. 다른 Module에서 직접 HTTP 요청을 하지 않음
9. External Request는 Public Data Collector에서만 발생
10. API Key가 로그에 기록되지 않음
11. Private Financial Amount가 로그에 기록되지 않음
12. Local Embedding이 외부 API를 호출하지 않음
13. Local RAG가 외부 API를 호출하지 않음
14. PostgreSQL이 localhost를 사용
15. Synthetic Pattern Detection 정상
16. Historical Pattern 정상
17. Public Article Ranking 정상

---

## 54. Source Code Network Audit

개발 완료 후 전체 프로젝트에서: requests, httpx, urllib, aiohttp, socket,
websocket 등을 검색한다.

의도하지 않은 Network Code가 있는지 확인한다.

Public Data Collector 이외의 인터넷 요청 코드는 제거한다.

---

## 55. 보안 문서

README_SECURITY.md를 만든다 (Phase 10).

비개발자도 이해할 수 있게: Private Zone / Public Zone / 외부로 나가는 정보 /
외부로 절대 나가지 않는 정보 / 회사명은 외부 API에 전달될 수 있다는 점 /
Investigation Question은 Local에만 존재한다는 점 / 재무수치는 외부로 전송되지
않는다는 점 / Public Data Collector 구조 / Allowlist 방식 / Local AI 구조 /
Local RAG 구조 / PostgreSQL 구조 / Claude Code 개발 시 실제 고객자료 사용 금지 /
현재 보안 구조의 한계 / 실제 기업에서 사용하려면 회사 정보보안팀의 검토와
승인이 필요하다는 점 을 설명한다.

---

## 56. TECHNICAL_SUMMARY.md

면접 설명용 문서 (Phase 10). 왜 웹앱 대신 Desktop App인가, 왜 PySide6인가,
왜 Polars인가, PostgreSQL은 어디에 쓰는가, 미공개 재무정보 보호 방법, 왜 외부
LLM API를 안 쓰는가, Local AI/Local RAG란 무엇인가, 뉴스 검색은 인터넷을 쓰는데
왜 내부 재무정보는 안 나가는가, Public Data Collector는 무엇만 내보내는가,
왜 내부 Investigation Question을 외부 검색어로 안 쓰는가, 관련기사는 어떻게
찾는가, Cross-Account/Historical Pattern은 어떻게 찾는가, 프로그램의 한계는
무엇인가 — 등을 비개발자도 이해할 수 있게 답한다.

---

## 57. 개발 순서

전체를 한 번에 만들지 않는다.

- **Phase 1** — PySide6 Desktop Shell, Security Status UI, Synthetic 5-year
  Data, Polars Loader, Dashboard
- **Phase 2** — Account Mapping, Financial Metrics, Relationship Rule Engine,
  Business Narrative Pattern Engine
- **Phase 3** — Historical Pattern Engine, Pattern Similarity, Investigation
  Question Engine
- **Phase 4** — Local PostgreSQL, Analysis 저장, Human Review
- **Phase 5** — Synthetic Public Document Dataset, Local Document Parsing,
  Chunking
- **Phase 6** — Local Embedding, Local Relevance Matching, Local RAG
- **Phase 7** — Public Data Collector Interface, Allowlist Schema, Network
  Guard (아직 실제 인터넷 연결 안 함, Fake Provider로 테스트)
- **Phase 8** — OpenDART Provider
- **Phase 9** — News Provider
- **Phase 10** — Security Test, Network Audit, README, Windows Packaging

---

## 58. 지금 당장 하지 않을 것

지금은: PostgreSQL 자동 설치, AI Model 자동 다운로드, DART 실제 연결, 뉴스 API
실제 연결, Windows Packaging 을 하지 않는다.

먼저 Phase 1만 구현한다.

---

## 59. 환경설정 주의

나는 코딩 초보자다.

- Python을 자동 설치하지 마라.
- Python을 재설치하지 마라.
- 가상환경을 반복 생성하지 마라.
- PostgreSQL을 자동 설치하지 마라.
- Local AI Model을 자동 다운로드하지 마라.
- 시스템 설정을 자동 변경하지 마라.
- Firewall을 자동 변경하지 마라.
- 명령이 멈추면 같은 명령을 반복하지 마라.
- Background process를 무작정 실행하지 마라.

무언가 설치가 필요하면: 무엇을 설치해야 하는지 / 왜 필요한지 / 내가 직접 어떤
명령을 실행해야 하는지 먼저 설명한다.

---

## 60. Git

Git 또는 GitHub 작업은 내가 명시적으로 요청하기 전에는 하지 않는다.

---

## 61. Phase 1 실행 지시 (완료 기준)

1. 현재 프로젝트 폴더를 확인한다.
2. 10줄 이내로 Phase 1 구현 계획을 설명한다.
3. PySide6 기반 Desktop Application Shell을 만든다.
4. 상단에 🔒 PRIVATE ANALYSIS: LOCAL ONLY / 🌐 PUBLIC DATA COLLECTION: OFF 를
   표시한다.
5. ABC Manufacturing의 Synthetic 5-year financial data를 만든다.
6. Polars를 이용해 Synthetic Data를 읽는다.
7. Dashboard에 매출/재고/매출채권/구축물/기계장치/차입금/영업CF 등을 표시한다.
8. 아직 Network Code를 작성하지 않는다.
9. Phase 1에 requests/httpx/aiohttp 등을 사용하지 않는다.
10. 실제로 실행되는지 확인한다.
11. 실행하지 못한 부분이 있다면 성공했다고 말하지 말고 정확한 원인을
    설명한다.

---

## 62. 최종 개발 원칙

이 프로젝트의 가장 중요한 구조는:

PRIVATE DATA → Local Analysis → Local Investigation Question

과

PUBLIC INTERNET → Broad Public Data Collection

을 분리하는 것이다.

두 영역은 외부에서 연결하지 않는다.

공개자료를 Local PC로 가져온 후에야 Private Investigation Question + Public
Documents 를 결합한다.

그리고 이 결합 및 관련성 판단은 항상 Local에서 수행한다.

최종 Architecture:

```
PRIVATE FINANCIAL DATA
        ↓
LOCAL CROSS-ACCOUNT ANALYSIS
        ↓
LOCAL HISTORICAL ANALYSIS
        ↓
LOCAL INVESTIGATION QUESTION
        │
        │ NEVER SEND OUT
        │
        └──────────────────────────┐
                                    │
PUBLIC COMPANY IDENTIFIER          │
        ↓                          │
PUBLIC DATA COLLECTOR              │
        ↓                          │
NEWS / DART                        │
        ↓                          │
PUBLIC DOCUMENTS                   │
        ↓                          │
LOCAL PC                           │
        └──────────────────────────┘
                   ↓
           LOCAL EMBEDDING
                   ↓
           LOCAL RAG / RANKING
                   ↓
            EVIDENCE CANDIDATE
                   ↓
              HUMAN REVIEW
```

이 Architecture를 코드 구조에서도 명확하게 유지한다.
