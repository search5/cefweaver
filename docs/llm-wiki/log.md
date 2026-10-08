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
- 갱신한 페이지: [C++ 핸들러](pages/components/native-handlers.md), [핸들러 프록시 구조](pages/concepts/handler-proxies.md), [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [Python API 참조](pages/reference/python-api.md), [설계 결정 기록](pages/reference/design-decisions.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings-api.md)(F15), [시험](pages/components/tests.md), [새 클래스를 생성 범위에 추가하기](pages/procedures/add-class-to-generator.md) 외 개수와 줄 수를 맞춘 페이지.
- 시험은 37개(통합 17, 생성기 19, 위키 1)이고 모두 통과했습니다.

## [2026-10-08] ingest | 값 타입 구조체 지원

- 사용자가 정한 순서(값 타입 구조체, 이어서 `CefBrowserHost`, 둘 다 TDD)의 첫 단계입니다. 시험을 먼저 쓰고(`Struct`를 가져오지 못해 실패) 구현했습니다.
- 헤더에서 필드를 읽는 `Model.structs`, `Struct` 종류, 세 방출기의 변환을 추가했습니다. 전체 지원이 81%에서 85%로, 범위 안의 메서드가 106개에서 109개로 늘었습니다.
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [새 타입 지원 추가하기](pages/procedures/add-type-to-generator.md), [Python API 참조](pages/reference/python-api.md), [설계 결정 기록](pages/reference/design-decisions.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings-api.md)(F16), [시험](pages/components/tests.md). 미사용 함수 경고는 `inline`으로 해소해서 알려진 제약에서 뺐습니다.

## [2026-10-08] ingest | CefBrowserHost

- 사용자가 정한 순서의 둘째 단계입니다. 스파이크 빌드로 CEF의 실제 동작을 먼저 확인하고(줌, 마우스, 자동 크기 조정, 닫기), 그 결과로 시험을 쓴 뒤 이전 wheel에서 실패하는 것을 확인하고 통과시켰습니다.
- `scope.py`에 `CefBrowserHost`를 추가해 53개 메서드가 열렸습니다. 범위 안의 메서드가 109개에서 163개로 늘었습니다.
- 발견: 래퍼의 브라우저는 Chrome 스타일이라 `do_close`가 호출되지 않습니다(F17). 앞서 "구현했으나 시험하지 못함"으로 적은 항목을 도달할 수 없는 경로로 바로잡았습니다.
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [Python API 참조](pages/reference/python-api.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings-api.md)(F17), [C++ 핸들러](pages/components/native-handlers.md), [시험](pages/components/tests.md), [설계 결정 기록](pages/reference/design-decisions.md) 외.

## [2026-10-08] ingest | Alloy 스타일 전환과 미검증 항목의 확인

- 사용자의 제안(java-cef처럼 Alloy 스타일만 지원)에 따라 java-cef 위키와 소스(`CefBrowser_N.cpp`)로 근거를 확인하고, 래퍼에 `runtime_style = ALLOY`를 설정했습니다. 전환의 부작용을 실험으로 찾았습니다: 창 제목이 비어 있음(X11로 설정하도록 구현), 첫 프레임 전의 입력이 버려짐, 이전에 알 수 없던 마우스 오프셋은 Chrome 스타일의 창 장식 때문이었음(F18).
- `do_close`가 이제 호출되고 닫기 거부가 시험으로 확인되었습니다. 앞서 도달할 수 없다고 적은 항목(F17의 이전 서술)을 바로잡았습니다.
- Windows를 제외한 미검증 항목을 실행해서 확인했습니다: 리소스 핸들러 콜백의 스레드(F19), `shutdown()` 뒤 재초기화(F20, 세그멘테이션 오류를 `RuntimeError`로 고침), 종료 없이 끝나기(F21), 팩토리가 거절한 경로(F22), 다른 CEF 버전 147과 152의 헤더(F23), manylinux(F24, 불가), GIL 교착(F25, 변형 빌드로 재현).
- 확인하지 못한 채 남은 것: `--build-cef`의 실제 소스 빌드와 `use_allocator=none`(디스크 여유 64GB, 요구 약 120GB), 구조체 출력의 Python 경로(오프스크린 렌더링 필요), 서브프로세스 `stack smashing`의 원인 메커니즘, Alloy 스타일에서의 네이티브 Wayland(실제 화면에 창을 열어야 함), 다른 버전의 `libcef`로 실제 실행.
- 갱신: [설계 결정 기록](pages/reference/design-decisions.md), [실험으로 확인한 사실](pages/reference/verified-findings-api.md)(F17 정정, F18 ~ F25), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [C++ 핸들러](pages/components/native-handlers.md), [Python API 참조](pages/reference/python-api.md), [프로세스 모델과 스레드](pages/concepts/process-model-and-threads.md), [시험](pages/components/tests.md), [패키징](pages/components/packaging.md), [Chromium의 Wayland와 X11 동작](pages/analyses/chromium-on-wayland.md) 외.

## [2026-10-08] ingest | 문자열 벡터와 라이브러리 출력 인자(첫 사례)

- 위키의 다음 단계 1순위였던 벡터를 시험 먼저로 구현했습니다. 대부분의 벡터(20건)가 `std::vector<CefString>`이고 범위 안에서 실행으로 검증할 수 있는 사용처가 둘뿐이어서(`browser.get_frame_names()`, `on_favicon_url_change`) 이 방향 둘로 한정하고 나머지는 이유와 함께 보고합니다. 라이브러리 메서드의 출력 인자를 Python 반환값으로 돌려주는 규칙의 첫 사례이기도 합니다.
- 지원 비율이 모든 클래스를 넣었을 때 85%에서 86%로, 범위 안의 메서드가 163개에서 166개로 늘었습니다(`CefBrowser` 21/21).
- 스텁 수정: 핸들러가 받는 문자열, 구조체, 목록에 잘못 붙던 `| None` 5곳을 고쳤습니다.
- `data:` 페이지의 `srcdoc` iframe이 로드를 끝내지 못하는 현상을 발견했습니다(F26, 원인 미조사).
- 갱신: [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [Python API 참조](pages/reference/python-api.md), [실험으로 확인한 사실](pages/reference/verified-findings-api.md)(F26), [시험](pages/components/tests.md) 외.

## [2026-10-08] ingest | F26(data: 페이지의 srcdoc iframe) 원인 조사

- 원인은 cefweaver가 아니라 CEF 154.0.34입니다(F27). 우리 코드가 없는 `cefsimple`도 같은 페이지에서 멈추고, 일반 Chrome 155는 정상입니다. 조건(부모 URL이 `data:`/`about:blank`), 배제한 가설(GPU, 샌드박스, 사이트 격리, 스타일, 위임, 기능 플래그, 불투명 출처)과 우회를 기록했습니다.
- 고칠 수 없어서 `expectedFailure` 시험으로 CEF의 수정을 감지하게 했습니다. 이전 CEF(152)에서의 동작은 확인하지 못했습니다.

## [2026-10-08] ingest | types 모듈 (열거형과 값 타입)

- 사용자의 요청(파이썬에서 `types` 모듈로 프로그래밍)을 `cefweaver.types`로 이해해 구현했습니다. 시험 먼저(생성기 9개 실패 확인). 열거형 101개 가운데 100개를 `IntEnum`/`IntFlag`로, 값 타입 6개를 `NamedTuple`로 모았습니다([types 모듈](pages/reference/types-module.md)).
- 핸들러의 열거형 인자와 라이브러리의 열거형 반환이 멤버로 변환되고, 일반 정수와 튜플도 그대로 통합니다.
- 입력 준비의 불안정한 시험을 원인(첫 프레임 뒤에도 10번 중 1번 첫 입력이 버려짐)과 함께 고쳤습니다(F18 정정). 전처리 `#else`가 섞이던 제 버그와 정적 라이브러리 재빌드를 빠뜨린 실수를 F28에 기록했습니다.

## [2026-10-08] ingest | 라이브러리 메서드의 출력 인자

- 사용자가 정한 순서의 세 번째 단계입니다. 시험 먼저(생성기 7개 실패), 이전 wheel에서 통합 시험 3개가 실패하는 것을 확인하고 구현했습니다.
- 규칙: 구조체 참조는 입출력(인자로 받고 바뀐 값을 반환), 기본형, 문자열, 열거형, 벡터 참조는 출력 전용(반환값만). 구조체를 입출력으로 본 것은 헤더가 아니라 실제 메서드(`ConvertPointToPixels`)에 근거한 판단입니다(알려진 제약에 기록).
- 범위에 `CefMenuModel`, `CefMenuModelDelegate`, `CefDisplay`를 추가했습니다(실행으로 검증할 수 있는 사용처). 모든 클래스를 넣었을 때 87%(1,398/1,598), 범위 안 메서드 245개. F29에 확인한 내용을 적었습니다.

## [2026-10-08] ingest | 벡터의 요소 종류 확대와 DragHandler

- 사용자가 정한 순서의 네 번째 단계입니다. 시험 먼저(생성기 8개와 통합 시험 4개가 이전 wheel에서 실패하는 것을 확인).
- 벡터의 요소: 문자열, 숫자, 값 타입 구조체(중첩 구조체 포함), 라이브러리 객체. 범위에 `CefPrintSettings`, `CefTaskManager`, `CefDragHandler`를 더해 실행으로 검증했습니다. 모든 클래스를 넣었을 때 87%에서 89%(1,422/1,598), 범위 안 메서드 276개.
- 발견과 수정: `TaskManager`를 프로세스 종료까지 쥐고 있으면 SIGTRAP(F30). 종료 뒤에 해제되는 라이브러리 객체는 `Release()` 없이 버리게 고쳤습니다.

## [2026-10-08] ingest | Alloy 스타일과 네이티브 Wayland (실제 데스크톱에서 확인)

- 사용자가 실제 화면에 창을 여는 것을 허락해서 확인했습니다. XWayland는 정상이고 **네이티브 Wayland는 Alloy 스타일에서 `libcef` 안에서 죽습니다**(F31). 그래서 `ozone-platform`을 지정하지 않고 `DISPLAY`가 있으면 `x11`을 기본으로 쓰게 했습니다(위키에서 미뤄 둔 결정 (나)의 조건부 채택).
- 창 제목 버그를 찾아 고쳤습니다: 창 관리자가 있는 데스크톱에서는 프레임 창에 제목을 쓰고 있었습니다. Xvfb 시험은 이를 잡지 못했으므로 실제 창 관리자 아래에서 확인하는 선택 실행 시험을 더했습니다.

## [2026-10-08] ingest | 핸들러를 나눠 쓰는 방법 분석과 Wayland 원인 조사 항목

- 사용자의 질문(핸들러를 통합한 것이 문제인가, 분리하면 되는가)에 답하며 코드를 다시 읽었습니다: CEF가 종류마다 핸들러 하나만 받으므로 분리는 불가능하고, 프로세스 메시지는 이름으로 나누면 결정이 필요 없으며, 컨텍스트 메뉴만 선택이 필요합니다. 이전에 두 가지를 모두 설계 결정이 필요하다고 한 것을 바로잡았습니다([분석](pages/analyses/sharing-handlers-with-the-wrapper.md)). `OnContextMenuCommand`의 `default: return true` 결함 의심을 알려진 제약에 적었습니다.
- Wayland 크래시의 원인 조사를 다음 단계 목록에 올렸습니다.

## [2026-10-08] ingest | 컨텍스트 메뉴와 DevTools 항목의 켜고 끔

- 사용자의 결정(DevTools 항목은 코드에서 켜고 끄고 기본은 끔, 켜고 끔이 다른 동작을 바꾸면 안 됨, 메뉴를 열고 고르는 수단 만들기)을 구현했습니다. 시험 먼저(생성기 5개와 통합 시험 5개가 이전 wheel에서 실패하는 것을 확인).
- 코드에서 메뉴를 열고 고르는 수단은 오른쪽 클릭 주입 + `run_context_menu`의 `callback.continue_()`입니다. 범위에 `CefContextMenuHandler`, `CefContextMenuParams`, `CefRunContextMenuCallback`, `CefRunQuickMenuCallback`을 더했습니다.
- 기존 결함 확정(F32): `OnContextMenuCommand`가 모르는 명령에 `true`를 돌려주어 표준 명령이 실행되지 않았습니다(옛 동작의 변형 빌드로 확인). 고쳤습니다.
- 래퍼의 DevTools 항목은 이전에 항상 켜져 있었고 지금은 기본이 꺼짐입니다(동작 변경).

## [2026-10-08] ingest | 프로세스 메시지와 값 컨테이너

- 사용자의 진행 요청으로 구현했습니다(오프스크린 렌더링은 이 다음). 시험 먼저(생성기 5개와 통합 시험이 이전 wheel에서 실패하는 것을 확인).
- 범위에 `CefProcessMessage`, `CefValue`, `CefListValue`, `CefDictionaryValue`, `CefBinaryValue`를 더했고, `Frame.send_process_message`와 `Client.on_process_message_received`가 열렸습니다. 래퍼는 자기 메시지 이름 둘만 가져가고 나머지는 사용자에게 넘깁니다.
- 앞서 "JavaScript와 Python의 양방향 메시지"라고 한 설명은 정확하지 않았습니다. Python은 브라우저 프로세스에만 있어서 사용자 정의 메시지의 보내는 쪽은 렌더러의 C++뿐입니다. 그래서 진단용 ping/pong을 렌더러에 두었습니다(F33).

## [2026-10-08] ingest | JavaScript 통신의 비교 조사 (java-cef, cefpython)

- 사용자의 질문(구조화된 양방향 통신을 java-cef 등은 어떻게 하는가, 열지 못한 부분)에 java-cef와 cefpython의 위키와 CEF 헤더로 답하고 [분석](pages/analyses/js-python-messaging.md)으로 저장했습니다. 구현은 하지 않았습니다. 정정: cefpython도 Python은 브라우저 프로세스에만 있고 렌더러는 C++입니다.

## [2026-10-08] ingest | 메시지 라우터를 java-cef 방식으로 연다

- `QueryHandler`, `QueryCallback`, `CefApp.add_query_handler`, `remove_query_handler`, `set_query_functions`를 더했습니다(손으로 쓴 `query_router.*`와 래퍼, 렌더러, 브라우저 프로세스 핸들러의 연결). 시험 10개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인한 뒤 구현해, 전체 144개가 통과합니다.
- 새 페이지 [메시지 라우터](pages/reference/message-router.md), 확인한 사실 F34(자식 프로세스에는 임의의 명령줄 스위치가 전달되지 않아 `OnBeforeChildProcessLaunch`로 붙임), 설계 결정, 시험 목록, 알려진 제약을 고쳤습니다.

## [2026-10-08] ingest | 메시지 라우터를 여러 프레임과 팝업에서 확인

- iframe과 `window.open` 팝업 시험 2개를 더했습니다(F35). 팝업을 닫으면 `g_IsRunning`이 꺼져 첫 브라우저의 `execute_javascript`가 멈추는 결함을 찾아 고쳤습니다. 팝업에서 바인딩이 안 될 것이라는 추측은 틀렸고 시험이 팝업 차단에 막혔던 것입니다. java-cef도 렌더러 라우터를 `extra_info`로 만든다는 점을 소스로 확인했습니다.

## [2026-10-08] ingest | 명령줄 스위치와 교차 사이트 iframe 확인

- 사용자의 질문으로 명령줄 스위치 서술을 점검해 틀린 곳 셋(자식 프로세스가 물려받는다는 문장)을 고쳤습니다. 실측(F36)에서 스위치는 자식 프로세스에 전달되지 않았습니다. 교차 사이트 iframe이 로드되지 않는 것도 찾았고(F37) 원인은 조사하지 않았습니다.

## [2026-10-08] query | 자식 프로세스 스위치를 java-cef는 어떻게 처리하는가

- java-cef 소스와 위키로 확인: 스위치 전달 수단이 브라우저 프로세스 한정이고 `OnBeforeChildProcessLaunch`가 없습니다. 사용자가 java-cef 수준에 머물기로 해서, 자식에게 스위치를 보내는 옵션을 만들지 않는 결정을 기록했습니다.

## [2026-10-08] ingest | 오프스크린 렌더링의 첫 단계 (읽기용 버퍼, RenderHandler)

- 생성기에 읽기용 버퍼 종류(`SIZED_BUFFERS`, `OnPaint`의 `width * height * 4`)를 더하고 `CefRenderHandler`를 범위에 넣었습니다(14개 메서드). 래퍼는 `offscreen`, `windowless_frame_rate`, `GetRenderHandler` 전달, 오프스크린 팝업 차단을 더했습니다. 시험 7개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했고 전체 153개가 통과합니다.
- 새 페이지 [오프스크린 렌더링](pages/reference/offscreen-rendering.md), 확인한 사실 F38(구조체 출력 경로 확인, `shutdown()`의 반복자 무효화 결함 수정). 설계 결정의 표에서 앞서 빈 줄로 떨어져 있던 행 셋을 표에 붙였습니다.

## [2026-10-08] ingest | 구조체 종류의 확대 (size 머리, 열거형, char16_t)

- 생성기가 `size_t size` 머리, 열거형 멤버, `char16_t`, `CefStructBaseSimple` 정의(`using`과 `class`)의 구조체를 읽습니다. `KeyEvent`, `ScreenInfo`, `PopupFeatures`, `TouchEvent`, `TouchHandleState`, `CompositionUnderline` 등 8개가 공개되어 15개가 되었고, `send_key_event`, `send_touch_event`, `ime_set_composition`, `get_screen_info`가 열렸습니다. 시험 8개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 161개가 통과합니다. F39. 옛 시험 3개(한계를 단정하던 것)를 현재 사실에 맞게 고쳤습니다.

## [2026-10-08] ingest | 바이트열 입출력 (BinaryValue.create, get_data)

- 생성기에 `Bytes` 종류를 더했습니다: 라이브러리 메서드의 `const void*`와 `size_t` 쌍은 바이트열 입력, `BYTES_OUT` 표의 `BinaryValue.GetData`는 `get_data(size, offset) -> bytes`입니다. 크기가 둘인 `CefStreamWriter::Write` 같은 것은 계속 제외합니다. 시험 6개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했고 전체 167개가 통과합니다. F40. 앞서 열지 못한 부분으로 적은 `create`, `get_data`가 열렸습니다.

## [2026-10-08] ingest | 포커스, JS 대화상자, 파일 대화상자, 다운로드 핸들러

- `CefFocusHandler`, `CefJSDialogHandler`, `CefDialogHandler`, `CefDownloadHandler`와 콜백 5개(`CefDownloadItem` 포함)를 범위에 넣고 래퍼가 사용자의 핸들러로 전달합니다. 시험 5개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 172개가 통과합니다. F41. 생성 범위 페이지의 표에서 낡은 행(`CefBrowserHost` 53/72, `CefClient` 6/19)을 현재 값으로 고쳤습니다.

## [2026-10-08] ingest | 키보드와 인쇄 핸들러 (무시하는 인자, T* 출력, 구조체 반환)

- 생성기에 `Ignored`(키보드의 `CefEventHandle os_event`), 핸들러의 `T*` 출력 인자(`bool* is_keyboard_shortcut`), 구조체를 값으로 반환하는 핸들러 메서드(`GetPdfPaperSize`, 숨은 출력 인자)를 더했습니다. `CefKeyboardHandler`, `CefPrintHandler`와 인쇄 콜백 둘을 범위에 넣었습니다. 시험을 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 176개가 통과합니다. F42. 프린터가 없어 인쇄 대화상자와 작업은 확인하지 못했습니다.

## [2026-10-08] ingest | 요청 핸들러와 리소스 요청 핸들러 (java-cef의 핸들러 13개 완성)

- `CefRequestHandler`, `CefResourceRequestHandler`와 `CefAuthCallback`, `CefSSLInfo`, `CefUnresponsiveProcessCallback`을 범위에 넣고, 래퍼의 라우터용 요청 핸들러를 `CwRequestHandlerForward`로 바꿔 사용자의 핸들러와 결합했습니다(취소된 탐색은 라우터에 알리지 않음). 시험 4개를 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 180개가 통과합니다. F43. 인증과 인증서 오류 등은 서버가 필요해 확인하지 못했습니다.

## [2026-10-08] ingest | 스트림과 ZIP 읽기 (크기가 둘인 포인터)

- 사용자의 질문("크기 인자가 둘인 경우는 왜 제외하는가")에 따라 `ItemBytes`를 더했습니다. `CefStreamReader`, `CefStreamWriter`, `CefZipReader`, `CefReadHandler`, `CefWriteHandler`를 범위에 넣고 `ptr, size, n` 규약을 `read(n, size=1)`, `write(data, size=1)`로 엽니다. `ReadFile`의 음수는 `RuntimeError`, 핸들러의 반환값은 `n`으로 제한합니다. 시험을 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 185개가 통과합니다. F44. 새 페이지 [스트림과 ZIP 읽기](pages/reference/streams.md).

## [2026-10-08] ingest | 시간(datetime)과 void* 표 완성

- 사용자의 요청(`GetFileLastModified`도 생성, 표에 없는 `void*`도 표로, 스트림의 CEF 내부 경로를 java-cef는 어떻게 하는지)에 따라 `Time` 종류(`CefBaseTime` → `datetime`), `BYTES_SIZE_FIRST`(`PostDataElement`), 복사하는 V8 배열, 의도적 제외 사유(`DELIBERATE_POINTERS`)를 더했습니다. `CefPostData`와 `CefPostDataElement`를 범위에 넣었습니다. 핸들러의 `const void*`가 const 없이 선언되던 잠재 결함도 고쳤습니다. 시험을 먼저 쓰고 이전 wheel에서 실패하는 것을 확인했으며 전체 191개가 통과합니다. F45. 새 페이지 [바이트열과 시간](pages/reference/bytes-and-times.md).

## [2026-10-08] schema | java-cef의 목록을 바닥으로 삼는다

- 사용자의 결정: java-cef가 여는 것은 바닥(java-cef의 동작에 맞춰 모두 구현), 그보다 더 연 것은 닫지 않고 위키에 정리. 범위를 java-cef 안으로 줄이려던 작업은 중단하고 되돌렸습니다. `tools/gen/surface.py`(java-cef의 네이티브 코드에서 뽑은 목록)와 `derive_surface.py`, 보고서의 격차와 바닥 위 절, 격차를 고정하는 시험을 더했습니다. 격차는 389개 가운데 78개입니다.

## [2026-10-08] ingest | 격차 메우기 1: java-cef가 넘기지 않는 인자의 무시

- `OnBeforePopup`(URL과 프레임 이름만), `OnCursorChange`(종류만), `OnCertificateError`(`ssl_info` 없이)를 java-cef의 방식으로 열었습니다. F46. 격차 78개에서 76개.

## [2026-10-08] ingest | 격차 메우기 2: 헤더 맵

- 문자열 멀티맵과 맵(`HeaderMap`, `SwitchMap`)을 `dict[str, str]`로 여는 `StrMap` 종류를 더해 `Request`, `Response`의 헤더 맵 메서드 5개를 열었습니다(java-cef의 `Map`과 같음). F47. 격차 76개에서 71개.

## [2026-10-08] ingest | 격차 메우기 3: 창 핸들

- `CefWindowHandle`(Linux에서 `unsigned long`)을 정수로 열어 `BrowserHost.get_window_handle()`을 만들었습니다. F48. 격차 71개에서 70개.

## [2026-10-08] ingest | 격차 메우기 4: 방문자, 파일 대화상자 콜백, DevTools 관찰자

- `CefStringVisitor`, `CefRunFileDialogCallback`, `CefDevToolsMessageObserver`, `CefRegistration`을 범위에 넣어 `Frame.get_source`/`get_text`, `BrowserHost.run_file_dialog`, `add_dev_tools_message_observer`를 열었습니다. F49.

## [2026-10-08] ingest | 격차 메우기 5: 문자열과 시간이 든 구조체, PDF 인쇄

- 구조체가 `cef_string_t`(`str`), `cef_basetime_t`(`datetime`) 필드를 갖고 `CefStructBase<Traits>` 형태여도 열립니다. 구조체가 15개에서 22개가 되었고 모든 필드에 기본값을 줍니다. `PdfPrintCallback`과 `BrowserHost.print_to_pdf`를 열었습니다. F50. 격차 64개에서 63개.

## [2026-10-08] ingest | 격차 메우기 6: 쿠키

- `CefCookieManager`, `CefCookieVisitor`, `CefSetCookieCallback`, `CefDeleteCookiesCallback`, `CefCompletionCallback`, `CefCookieAccessFilter`를 열었습니다. 구조체의 문자열 필드가 CEF에 닿지 않던 결함(복사본에 쓰고 있었음)을 찾아 고쳤습니다. F51. 격차 63개에서 54개.

## [2026-10-08] ingest | 격차 메우기 7: 요청 컨텍스트와 URL 요청, 인증과 리다이렉트 확인

- `CefRequestContext`(부모의 환경설정 메서드를 합침), `CefRequestContextHandler`, `CefURLRequest`, `CefURLRequestClient`를 열고, 같은 이름의 오버로드는 첫 번째만 만들도록 했습니다. 로컬 HTTP 서버로 인증, 리다이렉트, 응답 알림을 확인했습니다. `disable-chrome-login-prompt`와 입출력 인자(`new_url`)를 찾았습니다. F52. 격차 54개에서 44개.

## [2026-10-08] ingest | 격차 메우기 8: 명령줄과 앱 핸들러 훅

- `CommandLine`을 생성하고, 직접 쓴 `AppHandler`와 `SchemeRegistrar`로 java-cef의 앱 훅(명령줄 처리, 사용자 스킴 등록, 컨텍스트 초기화, 두 번째 시작)을 열었습니다. 사용자 스킴은 렌더러에 명령줄로 전파합니다. 시험이 `/tmp`를 7GB 채우던 문제를 고쳤습니다. F53. 격차 40개에서 27개.

## [2026-10-08] ingest | 격차 메우기 9: 드래그와 질의 취소, 격차 0

- `CefDragData`와 드래그 관련 메서드(`DragHandler.OnDragEnter`, `RenderHandler.StartDragging`, `BrowserHost.DragTargetDragEnter`)를 열고 라우터의 `CancelPending`(`cancel_pending_queries`)을 더했습니다. F54. 바닥의 격차는 0이 되었습니다(시험이 고정). CEF의 한계 하나를 찾았습니다(`get_file_name`).

## [2026-10-08] schema | java-cef 동등성 마무리

- 도출 도구에서 빠졌던 java-cef의 단순 콜백(`CompletionCallback`, `CookieVisitor`, `StringVisitor`, `RunFileDialogCallback`, `PdfPrintCallback`)을 매핑에 더해 "바닥 위" 분류를 바로잡았습니다(294개에서 289개). 바닥의 격차는 0이고, 바닥 위의 구성은 [java-cef 동등성](pages/reference/java-cef-parity.md)에 묶음별로 정리했습니다.

## [2026-10-08] ingest | 생성만 하고 실행하지 못한 핸들러 확인 (F55)

- 렌더러 종료, 새 탭 요청, 외부 프로토콜, 인증서 오류(로컬 TLS 서버), 요청 컨텍스트 핸들러, 오프스크린의 편집 키와 터치와 IME와 `<select>` 팝업을 실행해 확인했습니다. 시험 10개를 더했고 모두 통과했습니다(전체 239개).
- `CefApp.set_request_context()`를 더해 요청 컨텍스트 핸들러가 브라우저의 요청에 닿게 했습니다. 응답 필터와 창 정보로 꾸미는 팝업은 java-cef 수준을 넘어 열지 않고 [java-cef 동등성](pages/reference/java-cef-parity.md)에 정리했습니다.

## [2026-10-08] ingest | 한글 조합과 교차 사이트 iframe (F56, F57)

- 한글 조합(글자 경계, 밑줄의 두께와 모양)을 확인했고 밑줄 색은 화면에 반영되지 않는 것을 기록했습니다(F56).
- 교차 사이트 iframe이 멈추던 원인(F37)을 찾아 고쳤습니다. `add_javascript_binding`이 켜졌을 때 자식 프레임의 렌더러에서 `GetMainFrame()`이 널이라 렌더러가 죽었습니다. 호출한 프레임에서 보내도록 바꿨고, 서로 다른 렌더러 프로세스의 프레임에서 메시지 라우터가 동작함을 확인했습니다(F57). 메인 프레임의 첫 질의가 간혹 유실되는 관찰은 원인 미조사로 알려진 제약에 남겼습니다.

## [2026-10-08] query | 메인 프레임의 첫 질의 유실은 유실이 아니었다

- 원인을 파니 라우터가 아니라 `app.execute_javascript`가 로딩 중에 `False`를 돌려준 것이었습니다(문서화된 동작). 시험을 `is_ready_to_execute_javascript`를 기다리도록 고쳤고(10번 연속 통과), F57과 알려진 제약의 유실 서술을 정정했습니다.

## [2026-10-08] lint | java-cef 격차 점검

- JNI 수준의 격차는 0입니다(java-cef 소스에서 목록을 다시 뽑아 같았음). 이 도구가 보지 못하는 Java 쪽 공개 API를 대조해 설정 필드 14개, 버전 조회, 브라우저 여러 개, 투명한 오프스크린이 없음을 [java-cef 동등성](pages/reference/java-cef-parity.md)에 기록했습니다.

## [2026-10-08] ingest | 설정과 투명한 오프스크린 (F58)

- java-cef의 `CefSettings` 필드 14개를 `CefApp.settings`(`cefweaver.Settings`)로 열었고 투명한 오프스크린(`CefApp.transparent`)을 더했습니다. 효과를 관찰한 것과 시작만 확인한 것을 구분해 F58에 적었습니다. CEF가 오프스크린에서 전역 `background_color`를 보지 않는 규칙을 찾았습니다.

## [2026-10-08] ingest | 버전 조회 (F59)

- `cefweaver.get_version()`과 `CefApp.get_version()`을 더했습니다(CEF, Chromium, cefweaver의 버전). 헤더의 값과 같음을 시험했습니다.

## [2026-10-08] ingest | 브라우저 여러 개 (F60)

- `CefApp.create_browser(url, offscreen, transparent, request_context)`를 더했습니다(java-cef의 `createBrowser`). 브라우저 생성을 `CefWrapperBrowserProcessHandler::CreateBrowser`로 빼서 첫 브라우저도 같은 경로로 만듭니다. `execute_javascript`의 준비 표시가 다른 브라우저의 로딩에 따라 바뀌던 결함을 고쳤습니다. 이로써 java-cef와의 격차 목록이 모두 닫혔습니다.

## [2026-10-08] query | cefpython과의 API 차이

- cefpython의 API 문서 항목 459개를 스텁과 대조해 [cefpython과 cefweaver의 API 차이](pages/analyses/cefpython-comparison.md)에 저장했습니다.

## [2026-10-08] ingest | root_cache_path와 창 배경색 확인

- `Settings.root_cache_path`를 더해 java-cef의 `CefSettings` 20개를 모두 열었습니다. 창이 있는 브라우저의 배경색은 "픽셀을 읽을 수 없다"고 적었으나 시도하지 않은 것이었고, `XGetImage`로 읽어 확인했습니다(F58 정정).

## [2026-10-08] query | 채워야 할 격차 판단과 헤드리스 오프스크린 (F61)

- 오프스크린이 X 서버와 Wayland 없이 동작함을 확인해 시험으로 고정했습니다(F61). cefpython과의 격차 가운데 채울 것의 순서(메시지 펌프 예약, 스레드 보내기, 브라우저 설정, JS 통신, 가속 페인트)를 [cefpython 비교](pages/analyses/cefpython-comparison.md)에 적었습니다.

## [2026-10-08] ingest | 메시지 펌프 예약 (F62)

- `AppHandler.on_schedule_message_pump_work`, `Settings.external_message_pump`, `cefweaver.MessagePump`를 더했습니다(cefpython에는 있고 java-cef에는 없음). CEF의 규약(대체하는 요청, 1/30초 대비 타이머)을 시험으로 확인하고 `MessagePump`에 담았습니다. 생성기는 `#if CEF_API_ADDED` 멤버를 건너뛰어 `BrowserSettings`를 값 타입으로 만들었습니다.

## [2026-10-08] ingest | 스레드로 보내는 작업 (F63)

- `Task`, `post_task`, `post_delayed_task`, `currently_on`을 생성했습니다(cefpython의 `PostTask`, `PostDelayedTask`, `IsThread`에 해당). 생성기가 `typedef cef_..._t Cef...;` 별칭(`CefThreadId`)을 열거형으로 읽도록 고쳤습니다.

## [2026-10-08] ingest | 브라우저 설정 (F64)

- `types.BrowserSettings`, `CefApp.browser_settings`, `create_browser(settings=)`를 더했습니다. 생성기는 `#if CEF_API_ADDED` 멤버를 건너뜁니다. 유지되는 필드와 CEF가 되돌리는 글꼴 크기, 쓰이지 않는 `default_encoding`을 구분해 기록했습니다. 1, 2, 3번(메시지 펌프, 스레드 작업, 브라우저 설정)이 끝났습니다.

## [2026-10-08] lint | CEF의 한계로 적은 것을 검증

- 사용자의 요청으로 "CEF의 한계"로 보이는 항목을 래퍼 없이 `cefsimple`(두 스타일)과 CEF 소스로 검증하고 [방법과 결과](pages/procedures/verify-cef-limits.md)를 적었습니다. 글꼴 크기의 되돌림, `default_encoding` 미반영은 CEF의 한계로 확인했고, `data:` 이미지는 Blink의 동작, 밑줄 색은 CEF가 전달하나 그리지 않는 쪽은 미확인, 인증서 허용 기억은 Chromium의 동작으로 정정했습니다.
- 같은 점검에서 `DragData.get_file_name()`의 서술을 "CEF 안의 CHECK"에서 "CEF가 확인 없이 Chromium의 함수를 부름"으로 고쳤습니다(소스 확인). `srcdoc` iframe(F27)은 `cefsimple`로, `icudtl.dat` 위치는 시험으로 이미 검증되어 있었습니다.

## [2026-10-08] ingest | JavascriptBridge (F65)

- `cefweaver.JavascriptBridge`, `JsCallback`을 더했습니다. 렌더러에 Python을 두지 않고 렌더러의 C++가 고정된 JS 조각만 실행해 `window.<이름>`을 정의하고, 호출은 메시지 라우터의 JSON 질의로 갑니다. 4번(cefpython의 풍부한 JS 통신)이 끝났습니다.

## [2026-10-08] ingest | 공유 텍스처 (F66)

- `CefApp.shared_texture`, `RenderHandler.on_accelerated_paint`, `AcceleratedPaintInfo`, `read_plane`을 더했습니다. 생성기는 구조체 배열(+개수)과 C++ 클래스가 없는 C 구조체, 플랫폼별 정의(Linux)를 읽습니다. 실제 GPU에서 텍스처와 메타데이터 도착을 확인했고 픽셀 내용(모두 0)은 원인을 찾지 못해 "미확인"으로 기록했습니다.

## [2026-10-08] ingest | GTK 3 예제 (F67)

- `examples/gtk3/`(uv 환경, `CefWidget`, 데모 브라우저, 실제 X 이벤트로 구동하는 `smoke.py`)를 만들어 돌렸습니다. 19개 점검이 1배와 2배에서 통과했습니다. `on_after_created`에서 `CefApp`을 쓸 수 없던 결함을 고쳤고, 뒤로 가기 캐시로 복원된 페이지의 크기 변경 문제(원인 미확인)와 우회를 기록했습니다.

## [2026-10-08] ingest | GTK 3 예제: 복사와 붙여넣기, 드래그 앤 드롭

- 점검을 19개에서 27개로 늘렸습니다. 복사와 붙여넣기는 위젯 코드 없이 통과했고, 드래그 앤 드롭은 GTK의 드롭 대상과 드래그 원본을 위젯에 구현했습니다. CEF 응답의 비동기성과 `drag-end` 오류에서 위젯의 결함 둘을 고쳤습니다.

## [2026-10-08] ingest | 열거형 인자의 폭 (F68)

- Tk 예제가 드러냈습니다: 열거형 인자가 `int`여서 `DragOperationsMask.EVERY`가 넘쳤습니다. 생성기가 `long long`으로 받도록 고쳤습니다.

## [2026-10-08] ingest | 툴킷 예제 (Qt, Tkinter, SDL2, wxPython, Kivy)

- `examples/`에 다섯 툴킷의 오프스크린 위젯 예제를 더했습니다. 공통 데모 페이지와 점검(`common/demo.py`, `common/checks.py`)을 쓰고, 모두 실제 X 이벤트로 구동해 통과했습니다. 새 페이지 `toolkit-examples.md`, F69, 알려진 제약 두 항목(tkdnd 중단, 드롭 경합), `README.rst` 불일치 행을 고쳤습니다.

## [2026-10-08] schema | 생성 파일을 나눠 낸다 (api/*.pxi, types/)

- 11,777줄이던 `cef_api.pxi`를 색인(`cef_api.pxi`)과 헤더별 부분 `cefweaver/api/*.pxi`(45개와 공통 부분)로, 2,140줄이던 `types.py`를 패키지 `cefweaver/types/`(`enums.py`, `structs.py`, `__init__.py`)로 나눴습니다. 생성기는 `generate.py`의 `SPLIT`, `output_path`, `whole`, `stale_files`로 여러 파일을 다루고, 없어진 부분은 `--check`가 잡고 쓰기가 지웁니다. Cython이 `include`를 따라가므로 부분만 바뀌어도 다시 컴파일됩니다(확인함). `.pxd`와 `.pyi`는 그대로 하나입니다.

## [2026-10-08] ingest | 툴킷 예제 위키 보강

- `toolkit-examples.md`에 각 예제의 위젯, 설치의 특이점, 점검 실행의 고정을 표로 더하고 `sources`에 예제별 `browser.py`, `pyproject.toml`, `README.md`를 올렸습니다.

## [2026-10-08] query | UI 어댑터 설계 (1단계)

- 여섯 예제의 위젯 코드를 비교해 공통인 것(라이브러리가 맡을 것)과 툴킷마다 다른 것(어댑터가 맡을 것)을 표로 정리하고 `ToolkitAdapter`, `BrowserView` 초안을 `analyses/ui-adapter-design.md`에 남겼습니다.

## [2026-10-08] ingest | cefweaver.ui (UI 어댑터 2단계)

- `BrowserView`, `ToolkitAdapter`, `Session`, `keys`, `HeadlessAdapter`를 구현했습니다. 단위 시험 47개와 실제 브라우저 시험 1개를 더해 시험은 352개입니다. 새 페이지 `ui-api.md`, F70(`get_file_name` 중단 관찰 포함), `ui-adapter-design.md`에 구현 상태를 적었습니다.

## [2026-10-08] ingest | GTK 3 예제를 cefweaver.ui로 이식 (3단계)

- `examples/gtk3/cefgtk.py`를 `GtkAdapter`, `GlibLoop`, `CefWidget`(이벤트 전달)으로 바꿔 663줄에서 555줄로 줄였고, 점검 27개가 바뀌지 않고 통과했습니다(1배 3번, 배율 2). 라이브러리에는 `commit_text()`, `DragPayload.x/y`, 드래그 시작 시 `drag_operation` 초기화를 더했습니다. 배율 2의 드래그 점검은 화면이 작으면 실패하며(이식 전도 같음) 2560x2048 화면에서 통과합니다.

## [2026-10-08] ingest | 여섯 예제를 cefweaver.ui로 이식 완료

- GTK 3(663줄에서 555), Tk(464에서 326), SDL2(547에서 405), Kivy(530에서 333), wx(547에서 369), Qt(573에서 458)로 위젯 파일이 줄었고, 각 예제의 점검은 바꾸지 않고 통과했습니다(Qt는 PyQt6, PySide6, 배율 1과 2). 이식 중 라이브러리에 더한 것: `commit_text()`, `DragPayload.x/y`, 드래그 시작 시 `drag_operation` 초기화. Qt의 붙여넣기는 이제 일반 텍스트만 다룹니다.

## [2026-10-08] ingest | 키, 수정 키, 커서 표를 객체로 (cefweaver.ui)

- 여섯 위젯이 각자 갖던 `windows_key_code`, `modifier_flags`, 커서 사전 조회를 `KeyTable`, `MaskModifiers`/`NamedModifiers`/`EventModifiers`, `CursorTable`로 올렸습니다. 위젯에는 툴킷의 이름 표만 남습니다. 여섯 예제의 점검은 바뀌지 않고 통과합니다.

## [2026-10-08] ingest | 위젯 기반 클래스 BrowserWidget (cefweaver.ui)

- 여섯 위젯에 똑같던 위임 메서드(`load_url`, `go_back`, `commit_text` 등)와 제목, 주소, 로딩, 준비 알림의 연결을 `ui.BrowserWidget`(`attach_view`와 훅 `browser_*`)로 올렸습니다. 위젯 파일은 GTK 514, Tk 286, SDL2 365, Kivy 298, wx 309, Qt 420줄이 되었고 점검은 바뀌지 않고 통과합니다. (Kivy는 훅을 어댑터 클래스에 잘못 끼웠다가 점검이 시간 초과로 알려 주어 고쳤습니다.)

## [2026-10-08] ingest | 그림 저장소 PictureStore (cefweaver.ui)

- GTK 3와 Qt가 각자 가지던 "dirty rect만 복사"와 크기가 바뀌면 새 표면을 만드는 코드를 `ui.PictureStore`로 올렸습니다. 이로써 툴킷 고유의 사정으로 남던 네 가지(드래그 시작 전략, 표, 위젯 기반 클래스, 그림 저장소)를 모두 뺐습니다. 설치본 기준으로 전체 시험 382개와 여섯 예제의 점검이 통과합니다.

## [2026-10-08] ingest | Session.start가 위젯을 받음, snapshot을 뷰로 (cefweaver.ui)

- 다섯 파일에 똑같던 `Runtime(ui.Session)` 하위 클래스를 없앴습니다(`Session.start`가 `BrowserWidget`을 받고, 끝에 어댑터의 선택 메서드 `release()`를 부름: Tk의 파이프). 여섯 파일에 있던 `snapshot`도 없앴습니다: 뷰가 모든 프레임을 `PictureStore`에 보관하고 `view.snapshot(path)`가 의존성 없이 PNG로 씁니다(GTK와 Qt는 같은 저장소를 `frame.change`와 함께 씀). 위젯 파일은 GTK 485, Tk 266, SDL2 354, Kivy 282, wx 294, Qt 396줄. 훅 이름을 `close`가 아니라 `release`로 한 이유: SDL2의 `SdlBrowser.close()`가 이미 "CEF를 닫는다"는 뜻이라 종료가 재귀로 두 번 일어날 수 있었습니다.

## [2026-10-08] schema | 툴킷별 어댑터를 패키지로 (cefweaver.ui.toolkits)

- `examples/*/cef*.py` 여섯 개를 `cefweaver/ui/toolkits/{gtk3,qt,tk,sdl2,wx,kivy}.py`로 옮겼습니다(`git mv`). 예제 디렉터리에는 데모 브라우저와 점검만 남습니다. 패키지에 두는 이유(핵심 API가 아직 바뀜, 책임질 사람이 없음)와 나누는 기준(외부 이슈와 PR이 처리 속도를 넘을 때)을 `ui-api.md`에 기록했습니다. 모듈은 서로 임포트하지 않고 지연 임포트이며, `pyproject.toml`에 선택 의존성(qt, gtk3, tk, sdl2, kivy)을 더했습니다. 설치본 기준으로 전체 시험 392개와 여섯 예제의 점검이 통과합니다.

## [2026-10-08] ingest | quickstart와 어댑터 정리

- 여섯 어댑터 모듈에서 쓰이지 않던 별명(`SHIFT, CONTROL, ALT`, 단추 상수)을 지우고, 키 표의 숫자 20을 `keys.VK_CAPITAL`로 바꿨습니다. 드래그 동작 변환(GTK와 Qt)은 툴킷마다 달라질 수 있어서 통합하지 않기로 했습니다. 예제마다 `quickstart.py`를 만들고(코드는 예제 README와 `README.rst`에 그대로 실음), 시험이 문서와 파일의 일치(`QuickstartDocs`)와 실제 실행·정상 종료(`Quickstarts`)를 확인합니다.

## [2026-10-08] query | java-cef의 오디오와 WebRTC 처리

- java-cef에는 `CefAudioHandler`도 `CefPermissionHandler`도 없음을 소스로 확인했습니다(키보드의 미디어 키 변환과 컨텍스트 메뉴의 `MediaType`만 있음). `java-cef-parity.md`가 `AudioHandler.on_audio_stream_packet`을 "java-cef도 열지 않은 포인터 배열"이라 적은 것은 틀려서 고쳤고, 확인한 내용과 핸들러가 없을 때의 CEF 기본 동작(Alloy는 거부)을 "오디오, WebRTC" 절에 기록했습니다.

## [2026-10-08] ingest | 권한 핸들러를 연다 (F71)

- `PermissionHandler`, `MediaAccessCallback`, `PermissionPromptCallback`을 범위에 넣었습니다. 래퍼의 `CefWrapperClientHandler`에 `GetPermissionHandler()`를 더하지 않으면 핸들러가 불리지 않는 것을 시험이 드러냈습니다. 가짜 장치로 허용, 거부, 기본 처리(거부), `enable-media-stream` 스위치(핸들러를 건너뜀)를 확인했습니다. cefpython의 `cefpython147` 브랜치(CEF 123, 리눅스와 맥 버전 헤더는 옛 값 그대로)도 조사했고 오디오와 권한 핸들러를 감싸지 않았습니다.
