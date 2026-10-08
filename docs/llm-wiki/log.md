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
