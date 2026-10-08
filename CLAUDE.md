# CLAUDE.md

이 문서는 이 저장소에서 작업하는 Claude Code에 주는 지침입니다.

## 코드 기록은 각 프로젝트의 llm-wiki를 우선합니다

다른 프로젝트의 코드나 동작을 조사할 때, 해당 프로젝트의 `docs/llm-wiki/`를 가장 먼저 참조합니다. 소스를 직접 검색하기 전에 위키에서 관련 페이지를 찾고, 위키가 가리키는 원본 파일(각 페이지 frontmatter의 `sources`)을 확인하는 순서로 진행합니다.

| 프로젝트 | llm-wiki 위치 |
| --- | --- |
| cefpython | `/home/jiho/cef_framework/cefpython/docs/llm-wiki/` |
| java-cef | `/home/jiho/cef_framework/java-cef/docs/llm-wiki/` |
| CEF (cef_origin) | `/home/jiho/cef_framework/cef_origin/docs/llm-wiki/` |

참조 방법은 다음과 같습니다.

1. 위키의 `index.md`에서 관련 페이지를 찾습니다. 위키의 구조와 규칙은 `SCHEMA.md`, 안내는 `README.md`에 있습니다.
2. 페이지의 `sources`에 적힌 원본 파일을 확인해서 위키 내용이 현재 소스와 맞는지 검증합니다.
3. 위키에 없는 내용은 소스에서 직접 확인합니다.
4. 위키와 원본이 다르면 원본을 따르고, 차이를 사용자에게 알립니다. 각 위키의 `README.md`도 같은 원칙을 정하고 있습니다.

이 저장소(cefweaver)에는 아직 llm-wiki가 없습니다.

## 이 저장소의 위키 (`docs/llm-wiki/`)

이 프로젝트 자신의 위키이며 카파시(Andrej Karpathy)의 llm-wiki 패턴을 따릅니다. 구조와 작업 절차(ingest, query, lint)는 `docs/llm-wiki/SCHEMA.md`가 정하고, 이 문서와 함께 스키마 층을 이룹니다. 위키는 LLM이 작성하고 유지하며, 사람은 자료를 고르고 질문합니다.

- **질문에 답하거나 코드를 조사할 때** `docs/llm-wiki/index.md`를 먼저 읽고 관련 페이지의 `sources`로 원본을 확인합니다. 위키와 원본이 다르면 원본이 맞고 위키를 고칩니다.
- **코드를 바꾸면 같은 작업 안에서 위키를 맞춥니다.** 바꾼 파일이 `sources`에 적힌 페이지를 찾아 고치고(`grep -rl "바꾼/파일/경로" docs/llm-wiki/pages`), `updated`를 갱신하고, 새 페이지는 `index.md`에 등재하고, `log.md`에 `## [YYYY-MM-DD] ingest | 제목` 항목을 덧붙입니다.
- **가치 있는 답변(비교, 분석, 새로 알게 된 연결)은 `pages/analyses/`에 저장합니다.** 대화 속에 사라지게 두지 않습니다.
- **실행해서 확인한 사실**은 `pages/reference/verified-findings.md`에, 확인하지 못한 것과 문서의 불일치는 `pages/reference/known-constraints.md`에 기록합니다. 추측은 쓰지 않습니다.
- **점검**: `python docs/llm-wiki/lint.py`(링크, `sources`, 색인 등재, 고아 페이지, 형식). 시험(`tests/test_wiki.py`)에도 포함되어 있습니다.

## 빌드와 시험

```sh
python tools/prepare.py          # CEF 확보, 네이티브 빌드, 런타임 스테이징 (Linux)
uv build --wheel                 # Cython 확장 빌드 (인자 없는 `uv build`는 sdist 단계에서 실패)
env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v
```

- 시험은 설치된 wheel을 대상으로 하며, 가상 X 서버에서 실행해야 합니다. `-P`는 필수입니다: 저장소 루트에서 `-P` 없이 실행하면 소스 트리의 `cefweaver/`가 설치된 wheel을 가려서 CEF 시험(40개)이 조용히 건너뛰어지고도 `OK`로 끝납니다. Wayland 환경에서는 Chromium이 실제 화면에 창을 열 수 있습니다.
- 지원 플랫폼은 Linux x86_64입니다. Windows는 미검증이고 macOS는 지원하지 않습니다.

## 바인딩 생성기 (`tools/gen/`)

CEF API 전체를 손으로 중계하지 않고, CEF 헤더에서 Python 바인딩을 **생성**합니다. 파서는 CEF의 공식 헤더 파서(`tools/gen/vendor/`, 출처와 라이선스는 그 안의 `README.txt`)이고, 입력은 사용 중인 배포본의 헤더(`build/native/cef/include`)입니다.

```sh
python tools/gen/generate.py            # 생성 파일 갱신
python tools/gen/generate.py --check    # 생성 파일이 최신인지 확인 (시험에도 포함)
python tools/gen/generate.py --report   # 커버리지 보고서 출력 (같은 내용이 위키의 pages/reference/coverage-report.md로 생성됨)
```

생성되는 파일은 모두 저장소에 커밋하며 **직접 고치지 않습니다**: `native/cefwrapper/generated/cefweaver_proxies.h`(핸들러를 Python 객체로 위임하는 C++ 프록시), `cefweaver/cef_api.pxd`, `cefweaver/cef_api.pxi`(Cython), `cefweaver/_cefweaver.pyi`(타입 스텁, `tools/gen/handwritten.pyi`의 `CefApp` 부분 포함), 위키의 `docs/llm-wiki/pages/reference/coverage-report.md`(커버리지 보고서). CEF 버전을 바꾸면 `prepare.py` 다음에 `generate.py`를 실행합니다.

- **범위**: `tools/gen/scope.py`의 클래스와 함수 목록입니다. 클래스를 추가하면 그 클래스를 인자나 반환으로 쓰던 메서드(보고서의 "class ... is not generated yet")도 함께 열립니다.
- **타입**: `tools/gen/typesys.py`가 모든 C++ 타입을 분류합니다. 지원하지 못하는 타입은 건너뛰지 않고 **이유와 함께** 보고서에 남습니다. 새 타입을 지원하려면 `typesys.py`에 종류를 추가하고 세 방출기(`emit_cpp.py`, `emit_cython.py`, `emit_pyi.py`)에 변환을 추가합니다. 현재 보고서 기준으로 남은 장애물은 값 타입 구조체, 벡터, 소유 포인터, 맵 순입니다.
- **이름 규칙(PEP 8)**: `Cef` 접두사를 뗍니다(`CefResourceHandler` → `ResourceHandler`). 메서드와 인자는 snake_case이고(`GetURL` → `get_url`), 예약어는 밑줄을 붙입니다(`Continue` → `continue_`).
- **시그니처 규칙**: 핸들러(CEF가 호출하는 쪽) 메서드는 출력 인자를 **반환값으로** 돌려줍니다. 반환값이 있으면 그것이 먼저이고, 값이 하나면 그대로, 둘 이상이면 튜플입니다(`open` → `(handled, handle_request)`). `void* + 크기` 쌍은 쓰기 가능한 `memoryview` 하나입니다(호출이 끝나면 무효화됩니다). `None`은 헤더가 `optional_param`으로 표시한 곳에만 허용됩니다.
- **핸들러**: Python 기반 클래스를 상속하며, 재정의하지 않은 메서드는 C++ 기반 클래스의 기본 동작을 따릅니다. 예외는 `sys.excepthook`으로 보고되고 CEF로 전파되지 않습니다.
- **GIL**: CEF를 부르는 호출은 `with nogil`, CEF가 부르는 콜백은 `with gil`입니다.
- **초기화 전**: `libcef`는 API 버전이 설정되기 전에 라이브러리 객체를 쓰면 프로세스를 중단시킵니다. 생성된 모듈이 불러올 때 `cef_api_hash()`를 호출해서 `Request.create()` 같은 호출이 초기화 전에도 안전합니다.

## 시험 작성 원칙

java-cef의 시험(`java/tests/junittests/`, 위키의 `run-and-test.md`)을 참고해서 정한 원칙입니다.

- **조건을 기다립니다.** 고정 시간만큼 기다리지 않고, 기다리는 사건을 `wait_until(app, 조건, "설명")`으로 지정합니다. 시간 제한은 상한일 뿐이며, 초과하면 무엇을 기다렸는지 밝히는 `TimeoutError`로 실패합니다. java-cef의 `awaitCompletion()`(`CountDownLatch`)에 해당합니다.
- **CEF를 띄우는 시험은 프로세스를 분리합니다.** CEF는 프로세스당 한 번만 초기화할 수 있습니다. java-cef는 `TestSetupExtension`으로 JVM 하나에서 CEF를 공유하지만, 우리는 한 시험의 크래시가 다른 시험을 막지 않도록 시험마다 새 프로세스에서 실행합니다. 시험이 많아져 비용이 커지면 공유 방식을 검토합니다.
- **외부 네트워크를 쓰지 않습니다.** 가짜 URL의 응답은 `app.add_resource()`로 주고(java-cef의 `addResource`에 해당), 핸들러의 세부 동작은 생성된 `ResourceHandler`와 `SchemeHandlerFactory`를 직접 구현해서 시험합니다. 간단한 페이지는 `data:` URL도 씁니다.
- **정상 종료까지 확인합니다.** 종료 코드가 0이고 stderr에 `stack smashing`이 없어야 합니다(서브프로세스 종료 결함의 회귀 방지).
