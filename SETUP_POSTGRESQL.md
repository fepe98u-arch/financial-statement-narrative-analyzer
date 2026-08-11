# 로컬 PostgreSQL 설치 (Phase 4용)

CLAUDE.md/PROJECT_SPEC.md 규칙상 PostgreSQL 서버 설치는 자동으로 하지 않습니다.
아래 절차를 직접 진행해 주세요. 앱 코드(스키마, 저장 로직, Human Review 화면)는
이미 다 만들어져 있고, 서버만 준비되면 바로 동작합니다.

## 1. 무엇을 설치하나요

**PostgreSQL 서버** (버전 14 이상 권장) — 로컬 PC에서만 돌아가는 데이터베이스
프로그램입니다. 클라우드 DB는 이 프로젝트에서 금지되어 있습니다
(PROJECT_SPEC.md §39).

## 2. 왜 필요한가요

Phase 4부터 분석 결과(Detected Pattern, Historical Pattern, Investigation
Question)와 회계사의 Human Review(유의미함/추가조사필요 등 체크)를 저장하기
위해서입니다. 지금은 DB 없이도 앱은 실행되지만, "저장" 관련 기능만
비활성화됩니다.

## 3. 직접 실행해야 하는 것

1. https://www.postgresql.org/download/windows/ 에서 Windows용 설치 프로그램을
   내려받아 실행합니다. (설치 마법사에서 비밀번호를 설정하게 되는데, 이 비밀번호를
   기억해 두세요.)
2. 설치가 끝나면 시작 메뉴의 **SQL Shell (psql)** 을 엽니다. 계속 Enter를 눌러
   기본값(Server: localhost, Database: postgres, Port: 5432, Username: postgres)을
   선택하고, 설치할 때 정한 비밀번호를 입력합니다.
3. psql 프롬프트에서 아래 명령을 입력해 이 프로젝트 전용 데이터베이스를 만듭니다:
   ```sql
   CREATE DATABASE fsna;
   ```
4. 이 프로젝트 폴더의 `.env` 파일을 열어 아래 줄의 주석(#)을 지우고, 비밀번호를
   설치할 때 정한 값으로 바꿔주세요:
   ```
   DATABASE_URL=postgresql+psycopg://postgres:여기에_비밀번호@127.0.0.1:5432/fsna
   ```
5. 앱을 실행한 뒤 왼쪽 사이드바의 **Human Review** 화면에서 상단에
   "🟢 PostgreSQL 연결됨"이 뜨는지 확인해 주세요. 안 뜨면 "DB 연결 다시 확인"
   버튼을 눌러보시고, 그래도 안 되면 오류 메시지를 그대로 알려주세요.

## 4. 확인 방법 (제가 실행할 것)

서버가 준비되었다고 알려주시면, 제가 `pytest`로 실제 저장/조회가 되는지
테스트해서 결과를 보고하겠습니다. 지금은 DB가 없는 상태이므로 관련 테스트는
자동으로 건너뛰도록(skip) 되어 있습니다.
