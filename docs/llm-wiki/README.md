# cefweaver llm-wiki

이 디렉터리는 cefweaver 저장소를 조사하여 LLM이 작성하고 유지하는 위키입니다. 안드레이 카파시(Andrej Karpathy)가 2026-04-04에 공개한 gist "LLM Wiki"의 패턴을 따릅니다. 패턴의 요약은 [llm-wiki 패턴 요약](pages/summaries/karpathy-llm-wiki.md)에 있습니다.

## 목적

cefweaver는 Chromium Embedded Framework(CEF)의 Python 바인딩입니다. 저장소에는 C++ 래퍼, Cython 확장, CEF를 확보하고 빌드하는 도구, CEF 헤더에서 바인딩을 생성하는 도구, 시험이 섞여 있습니다. 이 위키는 그 내용을 주제별로 정리해서 처음 접하는 사람과 LLM이 구조와 결정의 이유를 빠르게 파악하도록 돕습니다.

질문마다 원본에서 지식을 다시 찾아 조합하는 대신, 한 번 정리한 지식을 위키에 쌓아 두고 새 자료와 새 질문이 생길 때마다 갱신합니다. 교차 참조와 모순 표시가 이미 위키 안에 있으므로 위키는 쓸수록 풍부해집니다.

## 세 층

| 층 | 위치 | 설명 |
| --- | --- | --- |
| 원본 자료 | 저장소 전체 | 위키가 읽기만 하는 코드와 문서입니다. 다른 프로젝트의 위키와 소스도 참고 자료입니다. |
| 위키 | `docs/llm-wiki/` | LLM이 쓰고 유지하는 마크다운 페이지입니다. |
| 스키마 | [SCHEMA.md](SCHEMA.md), 저장소 루트의 `CLAUDE.md` | 구조, 형식, 작업 절차 규칙입니다. |

## 사람을 위한 사용법

1. [index.md](index.md)에서 분류별 페이지 목록을 봅니다.
2. 전체 구조가 궁금하면 [아키텍처 개요](pages/concepts/architecture-overview.md)부터 읽습니다.
3. 빌드하려면 [빌드와 설치](pages/procedures/build-and-install.md)를 읽습니다.
4. 용어가 낯설면 [용어집](pages/reference/glossary.md)을 봅니다.
5. 지금 무엇이 확인되지 않았는지는 [알려진 제약과 미검증 항목](pages/reference/known-constraints.md)에 있습니다.
6. 위키 내용과 원본이 다르면 원본이 맞습니다. 차이를 발견하면 해당 페이지를 갱신하도록 요청합니다.

Obsidian으로 이 디렉터리를 열면 링크를 따라가며 읽고 그래프 보기로 구조를 볼 수 있습니다. 위키는 git 저장소의 마크다운 파일이므로 변경 이력도 그대로 남습니다.

## LLM을 위한 사용법

1. 작업을 시작하기 전에 [SCHEMA.md](SCHEMA.md)를 읽고 구조, 형식, 절차를 따릅니다.
2. 질문에 답할 때는 [index.md](index.md)로 관련 페이지를 찾고, 필요하면 `sources`에 적힌 원본을 다시 읽어 확인합니다.
3. 새 자료를 반영하거나 오류를 고친 뒤에는 [log.md](log.md)에 기록을 덧붙이고 index.md를 갱신합니다.
4. 코드를 바꿨다면 `sources`에 그 파일이 적힌 페이지를 찾아 같은 작업 안에서 고칩니다.
5. 점검은 `python docs/llm-wiki/lint.py`로 시작합니다.
6. 추측은 쓰지 않습니다. 원본을 끝까지 추적해서 사실을 확정하고, 근거를 얻을 수 없는 항목만 이유와 확인 방법을 함께 적습니다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| [README.md](README.md) | 위키 안내 |
| [SCHEMA.md](SCHEMA.md) | 구조, 형식, 작업 절차 규칙 |
| [index.md](index.md) | 모든 페이지의 분류별 목록 |
| [log.md](log.md) | 시간순 작업 기록 |
| `lint.py` | 점검 도구 |
| `pages/concepts/` | 개념: 구조와 동작 원리 |
| `pages/components/` | 구성요소: 파일과 모듈 단위 설명 |
| `pages/procedures/` | 절차: 빌드, 시험, 갱신 방법 |
| `pages/reference/` | 참조: API, 제약, 실험 기록, 결정 기록, 용어집 |
| `pages/summaries/` | 원본 문서의 요약 |
| `pages/analyses/` | 질문에 답하며 만든 분석과 비교 |
