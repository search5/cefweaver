# 작업 기록

시간순으로 덧붙이는 기록입니다. 형식은 [SCHEMA.md](SCHEMA.md)를 따릅니다. 기존 항목은 고치지 않습니다.

## [2026-10-08] ingest | 초기 위키 작성

- 카파시의 gist "LLM Wiki"(2026-04-04) 원문을 내려받아 전문을 읽고, 그 패턴(원본, 위키, 스키마의 세 층과 ingest, query, lint 작업, index.md와 log.md)을 이 저장소에 맞게 구성했습니다. 구체적인 구조와 형식은 이미 있는 cefpython과 java-cef의 위키 관례를 따랐습니다.
- 저장소 전체를 조사하여 페이지를 처음 작성했습니다. 조사한 원본: `CMakeLists.txt`, `cmake/`, `native/`, `cefweaver/`, `tools/`(`prepare.py`, `build_cef.py`, `gen/`), `tests/`, `pyproject.toml`, `MANIFEST.in`, `README.rst`, `CLAUDE.md`, `tools/gen/STATUS.md`, `docs/`, git 이력.
- 조사하면서 원본에서 고친 오류: `README.rst`의 `cefsubprocess/` 디렉터리 설명(실행 파일), `_cefweaver.pyx`의 `load_url` docstring(브라우저는 `initialize()` 안에서 만들어짐), `CLAUDE.md`와 `tests/test_smoke.py`의 시험 명령에 `-P` 누락(저장소 루트에서 CEF 시험 11개가 조용히 건너뛰어짐).
- 만든 페이지: concepts 10, components 13, procedures 7, reference 8, summaries 3, analyses 4(총 45개). 목록은 [index.md](index.md)에 있습니다.
- 대화에서 조사한 내용을 `analyses/`로 환원했습니다: java-cef 시험 비교, API 중계 규모, cefpython 패치, Chromium의 Wayland와 X11 동작.
- 실행으로 확인한 사실은 [verified-findings](pages/reference/verified-findings.md)에, 확인하지 못한 항목과 문서의 불일치는 [known-constraints](pages/reference/known-constraints.md)에 모았습니다.
- 확인된 특이사항: `pyproject.toml`의 `numpy` 의존성은 코드에서 쓰이지 않고, `README.rst`는 저장소에 없는 GUI 툴킷 예제를 언급하며, `native/`에 호출되지 않는 코드(`zen://` 핸들러 등)가 남아 있습니다.
- 점검 도구 `lint.py`를 추가했습니다.

## [2026-10-08] ingest | tools/gen의 문서 파일을 위키로 병합

- `tools/gen/STATUS.md`(생성기의 한계와 다음 단계)의 내용을 [생성 범위와 커버리지](pages/reference/generated-api-coverage.md)의 "생성기의 한계와 다음 단계" 절로 옮기고 파일을 삭제했습니다. 내용은 이미 [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [설계 결정 기록](pages/reference/design-decisions.md)에 나뉘어 들어 있어서 겹치는 서술을 확인하고 한 곳으로 모았습니다.
- `tools/gen/COVERAGE.txt`(생성기가 만드는 보고서)를 위키 페이지 [커버리지 보고서](pages/reference/coverage-report.md)로 옮겼습니다. `tools/gen/generate.py`가 이 페이지를 직접 쓰며, 내용이 같으면 `updated`를 유지해서 `--check`와 시험(`test_generated_files_are_up_to_date`)이 날짜 때문에 흔들리지 않습니다.
- 요약 페이지 `summaries/readme-claude-status.md`를 `readme-and-claude-md.md`로 바꾸고(STATUS.md 절 삭제) 이 페이지를 가리키던 링크와 색인을 모두 고쳤습니다.
- `tools/gen/vendor/README.txt`와 `vendor/LICENSE.txt`는 옮기지 않았습니다. 복사해 온 CEF 파서의 BSD 라이선스와 출처 표시이므로 코드와 함께 있어야 합니다. 내용의 요약은 [생성기 모듈](pages/components/generator-modules.md)과 [관련 프로젝트](pages/reference/related-projects.md)에 있습니다.
- 변경한 파일: 위키 페이지 19개의 `sources`와 본문, `index.md`, `README.rst`, `CLAUDE.md`, `tools/gen/generate.py`, `docs/llm-wiki/lint.py`.

## [2026-10-08] schema | 생성 페이지를 위한 frontmatter 필드 generated

- 도구가 만드는 페이지를 위해 frontmatter에 선택 필드 `generated: true`를 추가했습니다. 이 페이지는 직접 고치지 않고 200줄 길이 제한에서 제외됩니다([SCHEMA.md](SCHEMA.md)). `lint.py`가 이 필드를 읽습니다.

## [2026-10-08] ingest | CefClient 위임 구조와 로드, 수명 주기, 표시 핸들러

- 사용자가 선택한 다음 단계(1번, TDD)를 구현했습니다. 시험을 먼저 쓰고 실패를 확인한 뒤(생성기 4개, 통합 6개) 구현했고, 변이 시험으로 시험이 구현의 파손을 잡는지 확인했습니다.
- 생성기: `scope.py`에 `CefClient`, `CefLoadHandler`, `CefLifeSpanHandler`, `CefDisplayHandler` 추가, `emit_cpp.py`에 전달 클래스(`Cw<이름>Forward`) 방출. 래퍼: `CefWrapperClientHandler`가 전달 클래스를 상속해 이벤트를 사용자 핸들러로 넘기고, `CefWrapper::SetClient`와 `CefApp.set_client()` 추가.
- 갱신한 페이지: [C++ 핸들러](pages/components/native-handlers.md), [핸들러 프록시 구조](pages/concepts/handler-proxies.md), [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [Python API 참조](pages/reference/python-api.md), [설계 결정 기록](pages/reference/design-decisions.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F15), [시험](pages/components/tests.md), [새 클래스를 생성 범위에 추가하기](pages/procedures/add-class-to-generator.md) 외 개수와 줄 수를 맞춘 페이지.
- 시험은 37개(통합 17, 생성기 19, 위키 1)이고 모두 통과했습니다.

## [2026-10-08] ingest | 값 타입 구조체 지원

- 사용자가 정한 순서(값 타입 구조체, 이어서 `CefBrowserHost`, 둘 다 TDD)의 첫 단계입니다. 시험을 먼저 쓰고(`Struct`를 가져오지 못해 실패) 구현했습니다.
- 헤더에서 필드를 읽는 `Model.structs`, `Struct` 종류, 세 방출기의 변환을 추가했습니다. 전체 지원이 81%에서 85%로, 범위 안의 메서드가 106개에서 109개로 늘었습니다.
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [새 타입 지원 추가하기](pages/procedures/add-type-to-generator.md), [Python API 참조](pages/reference/python-api.md), [설계 결정 기록](pages/reference/design-decisions.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F16), [시험](pages/components/tests.md). 미사용 함수 경고는 `inline`으로 해소해서 알려진 제약에서 뺐습니다.

## [2026-10-08] ingest | CefBrowserHost

- 사용자가 정한 순서의 둘째 단계입니다. 스파이크 빌드로 CEF의 실제 동작을 먼저 확인하고(줌, 마우스, 자동 크기 조정, 닫기), 그 결과로 시험을 쓴 뒤 이전 wheel에서 실패하는 것을 확인하고 통과시켰습니다.
- `scope.py`에 `CefBrowserHost`를 추가해 53개 메서드가 열렸습니다. 범위 안의 메서드가 109개에서 163개로 늘었습니다.
- 발견: 래퍼의 브라우저는 Chrome 스타일이라 `do_close`가 호출되지 않습니다(F17). 앞서 "구현했으나 시험하지 못함"으로 적은 항목을 도달할 수 없는 경로로 바로잡았습니다.
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [Python API 참조](pages/reference/python-api.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F17), [C++ 핸들러](pages/components/native-handlers.md), [시험](pages/components/tests.md), [설계 결정 기록](pages/reference/design-decisions.md) 외.

## [2026-10-08] ingest | Alloy 스타일 전환과 미검증 항목의 확인

- 사용자의 제안(java-cef처럼 Alloy 스타일만 지원)에 따라 java-cef 위키와 소스(`CefBrowser_N.cpp`)로 근거를 확인하고, 래퍼에 `runtime_style = ALLOY`를 설정했습니다. 전환의 부작용을 실험으로 찾았습니다: 창 제목이 비어 있음(X11로 설정하도록 구현), 첫 프레임 전의 입력이 버려짐, 이전에 알 수 없던 마우스 오프셋은 Chrome 스타일의 창 장식 때문이었음(F18).
- `do_close`가 이제 호출되고 닫기 거부가 시험으로 확인되었습니다. 앞서 도달할 수 없다고 적은 항목(F17의 이전 서술)을 바로잡았습니다.
- Windows를 제외한 미검증 항목을 실행해서 확인했습니다: 리소스 핸들러 콜백의 스레드(F19), `shutdown()` 뒤 재초기화(F20, 세그멘테이션 오류를 `RuntimeError`로 고침), 종료 없이 끝나기(F21), 팩토리가 거절한 경로(F22), 다른 CEF 버전 147과 152의 헤더(F23), manylinux(F24, 불가), GIL 교착(F25, 변형 빌드로 재현).
- 확인하지 못한 채 남은 것: `--build-cef`의 실제 소스 빌드와 `use_allocator=none`(디스크 여유 64GB, 요구 약 120GB), 구조체 출력의 Python 경로(오프스크린 렌더링 필요), 서브프로세스 `stack smashing`의 원인 메커니즘, Alloy 스타일에서의 네이티브 Wayland(실제 화면에 창을 열어야 함), 다른 버전의 `libcef`로 실제 실행.
- 갱신: [설계 결정 기록](pages/reference/design-decisions.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F17 정정, F18 ~ F25), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [C++ 핸들러](pages/components/native-handlers.md), [Python API 참조](pages/reference/python-api.md), [프로세스 모델과 스레드](pages/concepts/process-model-and-threads.md), [시험](pages/components/tests.md), [패키징](pages/components/packaging.md), [Chromium의 Wayland와 X11 동작](pages/analyses/chromium-on-wayland.md) 외.

## [2026-10-08] ingest | 문자열 벡터와 라이브러리 출력 인자(첫 사례)

- 위키의 다음 단계 1순위였던 벡터를 시험 먼저로 구현했습니다. 대부분의 벡터(20건)가 `std::vector<CefString>`이고 범위 안에서 실행으로 검증할 수 있는 사용처가 둘뿐이어서(`browser.get_frame_names()`, `on_favicon_url_change`) 이 방향 둘로 한정하고 나머지는 이유와 함께 보고합니다. 라이브러리 메서드의 출력 인자를 Python 반환값으로 돌려주는 규칙의 첫 사례이기도 합니다.
- 지원 비율이 모든 클래스를 넣었을 때 85%에서 86%로, 범위 안의 메서드가 163개에서 166개로 늘었습니다(`CefBrowser` 21/21).
- 스텁 수정: 핸들러가 받는 문자열, 구조체, 목록에 잘못 붙던 `| None` 5곳을 고쳤습니다.
- `data:` 페이지의 `srcdoc` iframe이 로드를 끝내지 못하는 현상을 발견했습니다(F26, 원인 미조사).
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [Python API 참조](pages/reference/python-api.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F26), [시험](pages/components/tests.md) 외.

## [2026-10-08] ingest | F26(data: 페이지의 srcdoc iframe) 원인 조사

- 원인은 cefweaver가 아니라 CEF 154.0.34입니다(F27). 우리 코드가 없는 `cefsimple`도 같은 페이지에서 멈추고, 일반 Chrome 155는 정상입니다. 조건(부모 URL이 `data:`/`about:blank`), 배제한 가설(GPU, 샌드박스, 사이트 격리, 스타일, 위임, 기능 플래그, 불투명 출처)과 우회를 기록했습니다.
- 고칠 수 없어서 `expectedFailure` 시험으로 CEF의 수정을 감지하게 했습니다. 이전 CEF(152)에서의 동작은 확인하지 못했습니다.
