---
title: 실행해서 확인한 남은 API (F102~F112)
type: reference
sources:
  - tests/test_smoke.py
  - tools/gen/scope.py
  - native/cefwrapper/app_hooks.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - cefweaver/renderer_events.py
  - native/cefwrapper/bridge.h
updated: 2026-10-11
---

# 실행해서 확인한 남은 API (F102~F112)

2026-10-10에 연 핸들러, 서버, 렌더러 이벤트, 미디어 라우터 등을 실제 CEF로 구동해 확인한 기록입니다. 각 항목의 시험은 `tests/test_smoke.py`에 있습니다. 표시한 것 말고는 Linux x86_64, CEF 154, 가상 X 서버에서 확인했습니다.

## F102. 핸들러와 서버의 동작 (측정한 값)

- **찾기**: `FindHandler.on_find_result`의 첫 결과의 서수는 0입니다(시험 `test_the_find_handler_gets_the_results_of_a_search`).
- **프레임 이벤트**: `FrameHandler`는 프레임이 생기고 사라지는 것을 봅니다. `data:` 페이지의 `srcdoc` iframe은 [F27](verified-findings-api.md)의 문제로 시험에 쓸 수 없어서 `add_resource`로 준 페이지를 씁니다. 전환 유형은 열거형이 아니라 `int`로 옵니다.
- **서버**: `Server`의 `is_running`은 서버 스레드에서만 `True`이고, `client_address`에는 포트가 붙어 있습니다.
- **`resolve_host`**: 호스트 이름이 아니라 origin URL(`https://...`)을 받아야 합니다.
- **응답 필터**: 입력의 끝은 빈 `memoryview`로 오고, 그때 `DONE`을 돌려주면 됩니다. 필터는 `ResourceRequestHandler.get_resource_response_filter`가 줍니다.
- **`get_resource_request_handler`** 는 `(핸들러, False)` 튜플을 돌려줍니다(둘째 값은 헤더가 정한 출력 인자).
- **클라이언트 인증서**: 서버가 클라이언트 인증서를 요구하면 `RequestHandler.on_select_client_certificate`가 `(is_proxy, host, port, certificates, callback)`으로 불립니다. 이 환경에서는 인증서가 0개였고 `callback.select(None)`으로 진행됩니다.
- **인증서 정보**: `on_certificate_error`는 `ssl_info`를 넘기지 않습니다. 인증서는 `get_visible_navigation_entry().get_ssl_status()`로 읽습니다(시험 `test_the_certificate_of_a_page_is_read_from_its_ssl_status`). `ssl_info`를 넘길지는 정하지 않았습니다([알려진 제약](known-constraints.md)).

## F103. 초기화 전에 부르면 죽는 함수 (`NEEDS_CEF_RUNNING`)

`CefIsRTL()`(`is_rtl()`)은 CEF를 시작하기 전에 부르면 프로세스가 세그멘테이션 오류로 죽었습니다. `scope.py`의 `NEEDS_CEF_RUNNING`에 더해 시작 전에는 `RuntimeError`로 거절하게 했습니다(시험 `test_is_rtl_is_refused_before_cef_runs`).

## F104. 렌더러 이벤트 (`app.enable_renderer_events()`)

- 렌더러는 C++이라 Python을 돌릴 수 없으므로, 렌더러가 **프로세스 메시지**(`cefweaver-renderer-event`)로 브라우저 프로세스에 알리고 `cefweaver.RendererEvents`가 순수 Python으로 풉니다. 켜지 않으면 메시지가 오지 않습니다(시험 `test_the_renderer_sends_no_events_unless_they_are_enabled`, 300회 펌프 동안 0개).
- 켜면 잡히지 않은 JavaScript 오류(메시지, 스크립트 이름, 줄, 호출 스택의 함수 이름), 초점이 간 노드(편집 가능 여부, 태그, 페이지 안의 위치와 크기, 초점이 떠나면 `None`), V8 컨텍스트의 생성과 해제가 옵니다.
- **컨텍스트 해제는 메인 프레임이 다른 페이지로 이동할 때는 오지 않았습니다**(렌더러가 내려가며 메시지가 사라짐). iframe을 제거하면 옵니다. 시험도 iframe 제거로 확인합니다.
- 컨텍스트 해제 메시지는 브라우저의 메인 프레임으로 보냅니다(해제되는 프레임은 이미 없을 수 있어서). `stack_size`(기본 10)는 호출 스택에 담는 프레임 수(`settings.uncaught_exception_stack_size`)입니다.

## F105. 앱 핸들러에 더한 훅

- `on_before_child_process_launch(command_line)`: 자식 프로세스를 시작하기 전에 불립니다. `type` 스위치로 종류를 알 수 있고 `renderer`가 왔습니다.
- `on_register_custom_preferences(type, registrar)`: 전역(`PreferencesType.GLOBAL`)과 요청 컨텍스트(`REQUEST_CONTEXT`) 두 번 불립니다. `registrar.add_preference(이름, 값)`으로 등록한 기본값은 `has_preference`, `get_preference`로 읽히고 `set_preference`로 바꿀 수 있습니다. 이름이 겹치면 `False`입니다. **등록기는 그 호출 안에서만 유효**하고 밖에서 부르면 `RuntimeError("... valid only during ...")`입니다.

## F106. 미디어 라우터, 구성요소 갱신, 추적, 접근성

- **미디어 라우터**: 이 환경에는 Cast 장치가 없어 싱크와 경로가 0개로 옵니다(`on_sinks`, `on_routes`). 실제 장치와의 동작은 이 시험에서 확인하지 못했고, 나중에 직접 확인했습니다([F114](#f114-실제-chromecast로-확인한-미디어-라우터-2026-10-11)).
- **구성요소 갱신**: `ComponentUpdater.get_components()`는 1개 이상을 돌려주고 각각 ID, 이름, 상태를 읽을 수 있었습니다.
- **추적**: `begin_tracing`, `end_tracing`이 파일을 쓰고(1,000바이트 넘음) 완료 콜백이 불립니다.
- **접근성**: `set_accessibility_state(ENABLED)` 뒤에 `AccessibilityHandler.on_accessibility_tree_change`가 사전 값(`ValueType.DICTIONARY`)으로 옵니다. 핸들러는 렌더 핸들러가 줍니다.

## F107. 공유 메모리와 개발자 도구

- **공유 메모리**: `SharedProcessMessageBuilder.write(offset, data)`는 바이트를 복사해 넣고, 범위를 넘으면 `False`입니다. `SharedMemoryRegion.to_bytes()`는 복사본(`bytes`)을 줍니다. 메모리는 CEF가 해제할 수 있어 포인터를 빌려주지 않습니다.
- **개발자 도구**: `BrowserHost.show_dev_tools()`는 CEF의 기본값으로 자기 창을 엽니다. `close_dev_tools()` 직후에 다시 열면 무시되므로 잠깐(약 0.3초) 펌프한 뒤 엽니다. `show_dev_tools(x, y)`로 요소를 가리킬 수 있습니다.

## F108. 간헐적인 시험 실패 (이번 변경과 무관해 보임)

- `test_a_second_offscreen_browser_paints_on_its_own_and_the_first_is_unaffected`: 변경 전 wheel에서도 20회 중 2회 실패했습니다.
- 철자 메뉴 시험(`test_a_suggestion_of_the_menu_replaces_the_misspelled_word_on_a_page_that_lost_the_focus`): 전체 526개를 한 번에 돌린 실행에서 1회 실패했고, 단독으로는 4회 모두 통과했습니다. 부하 때문으로 보지만 원인은 확인하지 못했습니다.

## F109. 첫 브라우저가 없을 때 `load_url`과 `execute_javascript` (2026-10-10)

- `app.initialize(None)`로 시작하면 래퍼의 첫 브라우저가 없습니다. 이때 `app.load_url()`, `app.execute_javascript()`, `app.is_ready_to_execute_javascript`는 모두 `False`입니다(시험 `test_the_first_browser_functions_say_no_when_cef_starts_without_a_first_browser`).
- **결함을 찾아 고쳤습니다**: `is_ready_to_execute_javascript`는 클라이언트 핸들러가 없는데(첫 브라우저가 없으면 만들어지지 않음) 널 검사 없이 역참조해서 프로세스가 세그멘테이션 오류(종료 코드 -11)로 죽었습니다. `CefWrapper::IsReadyToExecuteJavascript()`(`native/cefwrapper/library.cpp`)에 널 검사를 더해 고쳤고, 고치기 전 wheel에서 시험이 -11로 실패하는 것을 먼저 확인했습니다.
- **Views 브라우저가 있어도 같습니다**: Views의 `BrowserView`로 만든 브라우저가 로드를 마친 뒤에도 `app.load_url()`과 `app.execute_javascript()`는 `False`이고 그 브라우저의 페이지는 바뀌지 않았습니다. 이 함수들은 래퍼의 첫 브라우저에만 적용됩니다. `create_browser()`나 Views의 브라우저에는 `browser.get_main_frame().load_url()`, `execute_java_script()`를 씁니다.
- **`create_browser()`와의 관계**: `initialize(None)` 뒤에 `app.create_browser()`를 부르면 `RuntimeError("a browser can be created on the thread of initialize() once the first browser exists")`가 납니다. 그래서 `initialize(None)`은 Views의 `BrowserView`로만 브라우저를 만드는 용도입니다. 첫 브라우저가 있을 때 둘째 브라우저(`create_browser()`, 식별자 2)를 만들고 `app.load_url()`을 부르면 **첫 브라우저(식별자 1)의 페이지만** 바뀌었고 둘째는 그대로였습니다. 같은 실행에서 `execute_javascript()`를 `load_url()` 직후에 부르면 `False`였습니다(문서화된 대로 로딩 중이어서로 보이나 이 실행에서 따로 확인하지는 않았습니다).

## F110. `JavascriptBridge`의 shim 결함 두 가지와 `Eval` 경로 실험 (2026-10-10)

**고친 것** (`native/cefwrapper/bridge.h`, 시험 `test_evaluate_answers_with_an_error_when_the_result_cannot_be_sent_as_json`, `test_a_page_cannot_break_the_bridge_by_replacing_what_it_uses`. 둘 다 고치기 전에는 callback이 오지 않아 시간 초과로 실패했습니다)
- **보낼 수 없는 결과**: 순환 구조나 `BigInt`를 돌려주는 식은 `JSON.stringify`가 shim 안에서 던졌고, 마지막 `.catch(function () {})`가 삼켜서 Python에 값도 오류도 가지 않았습니다. 이제 `TypeError: ...`가 `error`로 옵니다.
- **페이지의 덮어쓰기**: 페이지가 `window.cefQuery`(질의 함수)나 `window.__cefweaverBridge`를 바꾸면 이후 `evaluate`가 깨졌습니다. 질의 함수는 설치 때 잡아 두고, `__cefweaverBridge`는 쓰기와 설정이 안 되는 속성으로 정의했습니다(페이지가 엄격 모드에서 대입하면 그 페이지의 코드가 `TypeError`를 받습니다).

**`CefV8Context::Eval`로 실행하도록 바꾼 것** (실험으로 가능함을 보인 뒤 구현했습니다. `native/cefwrapper/cef_wrapper_render_process_handler.cc`, `bridge.h`, `cefweaver/bridge.py`)
- 방식: Python의 `evaluate`가 프로세스 메시지 `cefweaver-eval`을 보내고, 렌더러가 `OnContextCreated`에서 (브라우저, 프레임)별로 모아 둔 컨텍스트에서 소스를 `{ ... }` 블록에 넣어 `Eval`한 뒤 결과를 shim의 `settle`에 넘깁니다. 해제할 때는 `IsSame`인 항목만 지우고, 요청을 받을 때 `frame->GetV8Context()->IsSame()`로 교차 확인합니다. 설명은 [JavascriptBridge](javascript-bridge.md)에 있습니다.
- **엄격한 CSP와 Trusted Types 페이지에서 통과합니다**(헤더 `script-src 'self' 'unsafe-inline'; require-trusted-types-for 'script'`). 같은 페이지에서 옛 경로는 `EvalError`였습니다. 소스 안에서 다시 `eval(...)`이나 `new Function(...)`을 부르면 페이지처럼 막히고, Trusted Types 싱크(`innerHTML = '...'`)도 페이지처럼 `TypeError`입니다.
- **실제 사이트(2026-10-10, 수동 확인)**: GitHub(CSP)와 YouTube(Trusted Types)에서 `1 + 1`, `document.title`, `location.hostname`, `var z = [1,2,3]; z.length`, `const k = 5; k`(두 번), `Promise.resolve({a: [1]})`가 모두 값을 돌려줬고, 같은 식을 옛 경로로 보내면 모두 `EvalError`였습니다.
- **옛 경로와의 비교**: 32개 식(`var`, 함수 선언, `typeof`, 객체 리터럴, 줄 주석, 배열, `Promise`의 성공과 거부, `throw 5`, 예외 종류, `undefined`, `null`, `NaN`, `class`, 같은 `let`과 `const`를 두 번)에서 29개가 같은 결과였습니다. 다른 3개: (1) `1 +`의 메시지가 `Unexpected end of input`에서 `Unexpected token '}'`로 바뀝니다(블록의 닫는 괄호). (2) `'use strict'` 지시문이 블록 안에서는 지시문이 아니라서 `this === undefined`가 `True`에서 `False`가 됩니다. (3) `Symbol('s')`는 `null`에서 `TypeError`가 됩니다.
- **블록으로 감싸는 효과**: 최상위 `let`과 `const`는 그 호출 안에서만 살아서 같은 식을 두 번 실행해도 성공합니다(감싸지 않으면 두 번째가 `already been declared`). `var`와 함수 선언은 전역에 남고(`typeof f` → `function`), `{a: 1}`은 옛 경로처럼 `1`입니다.
- **오류 형식**: `Eval`의 예외 메시지에서 `Uncaught `를 떼어 지금의 형식(`RangeError: r`)을 맞춥니다.
- **`BigInt`**: `CefV8Value`에 `BigInt` 형이 없어서 결과를 shim에 넘기는 `ExecuteFunction`이 실패했고, 처음에는 callback이 오지 않았습니다. 실패하면 `TypeError: the result cannot be passed to the bridge`를 대신 보내도록 고쳤습니다.
- **다른 사이트의 iframe**: 기존 시험(`test_the_bridge_works_in_an_iframe_and_in_every_browser`, `test_the_bridge_works_in_a_frame_of_another_site_with_a_renderer_of_its_own`)이 새 경로로 통과합니다.
- **페이지 이동**: 엄격한 CSP 페이지 A에서 B로 `load_url`한 뒤 `window.which`가 `'A'` 다음 `'B'`로 바뀌었고, 새 컨텍스트로 찾아갔습니다. 이동 직후에는 옛 문서가 답하기도 했습니다.
- **알려진 한계**: 컨텍스트가 만들어지기 전에 보낸 요청(시험이 처음에 간헐적으로 시간 초과가 난 원인이었고, 페이지의 `ready()` 신호를 기다리게 고쳐 6회 모두 통과)과, 답하기 전에 페이지를 떠난 요청(느린 `Promise` 400ms, 중간에 이동)은 callback이 오지 않습니다. `_pending`의 항목도 남습니다. 옛 경로에서 이 두 경우가 어땠는지는 비교하지 않았습니다.
- **`Eval`이 던진 예외**: 렌더러 이벤트의 `on_uncaught_exception`을 일으키지 않았습니다([F104](verified-findings-opened.md)).
- **모듈 문법**: 동적 `import()`는 옛 경로와 새 경로의 결과가 같았고(`import('/x.js').then(m => m.value)` → 42, 모듈 객체 전체 → `{'default': 'dflt', 'value': 42}`, 없는 파일은 `TypeError`, `(async () => (await import(...)).value)()`도 같음), 엄격한 CSP 페이지에서는 새 경로만 됩니다(같은 출처의 `script-src 'self'`). 정적 `import x from ...`, `import.meta`, 최상위 `await`는 두 경로 모두 `SyntaxError: Cannot use import statement outside a module` 등 같은 오류입니다(식은 모듈이 아니라 스크립트로 실행됨).
- 확인하지 못한 것: 다른 출처의 모듈을 `import()`할 때의 CORS와 CSP 동작.

## F111. `evaluate`의 시간 제한 (2026-10-10)

- `JavascriptBridge.evaluate(frame, expression, callback, timeout=30.0)`: 답이 없으면 `timeout`초 뒤에 `callback(None, "TimeoutError: no answer in N s")`를 부르고 `_pending`의 항목을 지웁니다. 늦게 온 답은 무시되고(콜백은 한 번만 불림), `timeout=None`이면 제한 없이 기다립니다. `0`, 음수, 문자열, `True`는 `ValueError`입니다. `post_delayed_task`(UI 스레드)로 `Task`를 예약하므로 콜백은 `do_message_loop_work()` 안에서 불립니다.
- 확인: 끝나지 않는 `Promise`는 약 0.3초 뒤 `TimeoutError`, 제한보다 늦게 답하는 식은 `TimeoutError`만 받고 늦은 답은 무시됨, 빠른 식과 `timeout=None`의 느린 식(500ms)은 정상(시험 `test_evaluate_gives_up_after_its_timeout_and_ignores_a_late_answer`, 5회 통과). 답하기 전에 페이지를 떠난 식(`Promise` 800ms, 중간에 이동)은 1.5초 뒤 `TimeoutError`이고 `_pending`이 비며, 다음 페이지의 `evaluate`는 정상이었습니다.
- 기본값 30초는 시험의 기본 대기 시간(`wait_until`)에 맞춘 값이고 근거가 있는 최적값은 아닙니다. 이보다 오래 걸리는 식은 `timeout`을 늘리거나 `None`을 줘야 합니다.
- 답이 오고 나서도 예약한 작업은 `timeout`초까지 남아 있다가 아무것도 하지 않고 끝납니다(항목이 이미 없음).

## F112. 새 wheel을 동결해도 같다 (2026-10-10)

- **환경**: Linux x86_64, Python 3.13.11, CEF 154, PyInstaller 6.22.3, cx_Freeze 8.7.1(F93과 같은 버전), 이번 작업을 모두 넣어 새로 빌드한 wheel. 새 가상환경에 설치해 `-P`로 실행했습니다.
- **최소 앱**: 엄격한 CSP와 Trusted Types 헤더를 준 `add_resource` 페이지, 로드 이벤트, JavaScript 바인딩, `JavascriptBridge.evaluate`(렌더러의 `Eval`, `timeout`), 렌더러 이벤트(`enable_renderer_events`, 잡히지 않은 오류)를 쓰고 `shutdown()`합니다. 동결하지 않은 실행과 같은 결과(`evaluate` → `(42, None)`, 렌더러의 오류 이벤트, 종료 코드 0)가 PyInstaller onedir, PyInstaller onefile, cx_Freeze에서 각각 3회씩 9회 모두 나왔고 `stack smashing`은 없었습니다. 크기는 PyInstaller onedir 약 461MB, onefile 약 191MB, cx_Freeze 약 412MB로 F93(451MB, 188MB, 402MB)보다 조금 커졌습니다(생성 파일이 늘어서로 보이나 원인은 확인하지 않았습니다).
- **Tk 예제의 `smoke.py`**(점검 30개): 동결하지 않은 실행이 30개 통과(`ALL OK`)이고, PyInstaller onedir, onefile, cx_Freeze 모두 3회씩 9회 모두 30개 통과, 종료 코드 0, `stack smashing` 없음이었습니다. PyInstaller에는 `--collect-all cefweaver --hidden-import PIL._tkinter_finder`를 줬습니다.
- **Views 예제의 `smoke.py`**(점검 13개, 툴킷 없이 CEF의 창만 씀): 동결하지 않은 실행이 13개 통과이고, PyInstaller onedir, onefile, cx_Freeze 모두 3회씩 9회 모두 13개 통과, 종료 코드 0, `stack smashing` 없음이었습니다. 창을 실제 X 이벤트(xdotool)로 조작하는 점검이라, CEF가 소유한 창과 폴링 루프도 동결본에서 동작한다는 뜻입니다. PyInstaller에는 `--collect-all cefweaver`만 줬고 Tk처럼 숨은 import는 필요하지 않았습니다.
- 확인하지 못한 것: Tk와 Views 외 툴킷(SDL2, GTK 3, Qt, wxPython)의 동결본, Python이 없는 기계에서의 실행, 새 wheel에서 PyInstaller가 `--collect-all` 없이 여전히 죽는지.

## F113. scikit-build-core로 옮긴 저장소의 Linux 확인 (2026-10-11)

`setup.py`와 `MANIFEST.in`을 지우고 `pyproject.toml`의 백엔드를 scikit-build-core로 바꾼 저장소에서 확인했습니다(Python 3.13, Linux x86_64, CEF 154).

- `CEF_ROOT=$PWD/build/native/cef uv build --wheel`이 성공했습니다(약 1분 37초). wheel은 156,076,117바이트이고 `_cefweaver.cpython-313-x86_64-linux-gnu.so`, `cefsubprocess`, 272,219,288바이트의 `libcef.so`가 들어 있으며 `.pyx`, `.pxi`, `.cpp`는 없습니다.
- 그 wheel로 전체 시험을 돌려 532개 중 CEF를 쓰는 시험은 모두 통과했습니다(건너뜀 9, 예상된 실패 3). 실패 1건은 위키 점검 시험이었고, 삭제된 `setup.py`를 `sources`로 가리킨 페이지 때문이었습니다(위키를 고쳐 해결).
- `tools/prepare.py`를 다시 실행하면 이전에 `cefweaver/`에 스테이징된 런타임이 지워졌고(소스 트리에 중복되어 wheel에 두 번 들어가는 것을 막기 위함) `build/native/prepare.json`의 `staged`는 비었습니다.
- `uv build --sdist`는 약 1MB의 sdist를 만들었고(361개 항목, `docs/`, `examples/`, `llm-wiki/`, `tests/`, `tools/` 포함), 그 sdist 하나로 `uv build --wheel`이 wheel(156,076,804바이트)을 만들었습니다. `CEF_ROOT`를 주지 않았으므로 CMake가 CEF를 구했는데 어디에서 구했는지는 확인하지 않았습니다.
- 인자 없는 `uv build`(`CEF_ROOT` 지정)도 sdist 1,062,753바이트와 wheel 156,076,196바이트를 모두 만들었습니다(약 1분 39초).
- 확인하지 못한 것: macOS 빌드(프레임워크 옵션, `cefsubprocess.app` 조립과 wheel 포함), Windows 전부, CI.

## F114. 실제 Chromecast로 확인한 미디어 라우터 (2026-10-11)

이 컴퓨터가 붙은 네트워크의 실제 Cast 장치로 한 번씩 돌려 본 기록입니다. 자동 시험이 아니고(장치가 있어야 하므로 `tests/`에 넣지 않음), 스크립트는 저장소에 두지 않았습니다. 사용자가 장치에 화면을 보내도 된다고 허락했습니다. Linux x86_64, CEF 154, 가상 X 서버, `app.offscreen`.

- **싱크 검색**: `MediaObserver.on_sinks`에 처음에는 빈 목록이 오고 뒤이어 장치가 나타났습니다(`notify_current_sinks()`를 반복하며 기다림). 이름이 `욕실`, `집`(Google Nest Hub), `그룹`인 싱크가 나타났고(`그룹`의 동작은 보지 않음) 실행마다 목록의 순서가 달랐습니다. `is_cast_sink()`는 True, `is_dial_sink()`는 False, `get_icon_type()`은 열거값이었습니다.
- **장치 정보**: `sink.get_device_info(콜백)`이 `MediaSinkDeviceInfo(ip_address='192.168.50.120', port=8009, model_name='Google Nest Hub')`를 돌려주었습니다.
- **소스**: `router.get_source("cast:CC1AD845?clientId=cefweaver1")`(기본 미디어 수신기)는 `is_cast_source()`가 True이고 싱크와 `is_compatible_with`가 True였습니다. 탭 소스 URN은 이전 시험대로 `None`이어서, 탭 화면 미러링은 이 API로 하지 못했습니다(시도하지 않음).
- **경로 생성과 종료**: `create_route(source, sink, 콜백)`의 콜백에 결과 `1`, 빈 오류, 경로가 왔습니다. `on_route_state_changed`가 `CONNECTED`를 주었고 `route.terminate()` 뒤에 `TERMINATED`가 왔으며 `on_routes`가 빈 목록으로 바뀌었습니다. 장치에는 기본 미디어 수신기가 떴습니다.
- **메시지 수신**: `on_route_message_received`가 JSON 바이트(`memoryview`)를 받았습니다: `receiver_action`, `new_session`, `update_session`, `app_message`(멀티존 상태), `v2_message`(`MEDIA_STATUS`).
- **메시지 송신**: `client_connect` 뒤에 `route.send_route_message()`로 `{"type":"v2_message","clientId":...,"message":{"type":"LOAD","sessionId":<세션>,"media":{"contentId":<주소>,"contentType":"video/mp4","streamType":"BUFFERED"}}}`를 보내면 장치가 `MEDIA_STATUS`로 응답합니다. 네임스페이스로 감싼 형식(`"message":{"namespace":...,"message":{...}}`)으로 보낸 첫 시도에는 LOAD에 대한 응답이 없었습니다.
- **재생 (외부 주소는 실패, 이 컴퓨터가 제공하면 성공)**: 처음 보낸 외부 주소(`commondatastorage.googleapis.com`의 Big Buck Bunny)는 그날 `403`을 돌려주었고(`curl -I`로 확인), 장치는 `LOADING` 뒤에 `IDLE`(사유 `ERROR`)로 끝났으며 사용자가 장치 화면에서 재생 막대가 잠깐 나왔다가 기본 화면으로 돌아가는 것을 봤습니다. 이 컴퓨터에서 gstreamer로 만든 10초짜리 시험 영상(H.264 baseline, 640x360, 약 219KB)을 HTTP(`http://<이 컴퓨터의 IP>:8765/test.mp4`, CORS와 Range 응답 포함)로 제공해 보내자 장치(다른 IP)가 직접 받아 갔고 상태가 `IDLE`, `BUFFERING`, `PLAYING`, `BUFFERING`, `PLAYING`(10초 위치), `IDLE`(사유 `FINISHED`)로 바뀌었습니다. `집`(Google Nest Hub)에 다시 보냈을 때 사용자가 화면에서 공이 떠다니는 영상을 직접 봤습니다(상태는 `BUFFERING`, `PLAYING`, `IDLE`/`FINISHED`). `욕실`로 보낸 실행은 상태 메시지만 확인했습니다.
- **재생 제어 (`집`, 60초 시험 영상)**: 모두 `v2_message`의 `message`에 `{"type":..., "requestId":..., "sessionId":<세션>}`을 넣어 `send_route_message()`로 보냈습니다. 미디어 메시지(`PLAY`, `PAUSE`, `SEEK`, `STOP`, `GET_STATUS`)에는 `"mediaSessionId":1`을 더했습니다.
  - `PAUSE`: `MEDIA_STATUS`의 `playerState`가 `PAUSED`(위치 4.7초)가 됐습니다. `PLAY`: 같은 위치에서 `PLAYING`이 됐습니다.
  - `SEEK`(`currentTime`: 30): `PLAYING`이고 `currentTime`이 30이었습니다.
  - `SET_VOLUME`(`{"volume":{"level":0.3}}`과 `{"muted":true/false}`): 응답은 `MEDIA_STATUS`가 아니라 멀티존 네임스페이스의 `DEVICE_UPDATED`(장치의 `volume.level`, `muted`)였습니다. `MEDIA_STATUS`의 `volume`은 스트림 음량(`level` 1)으로 따로입니다. 장치의 원래 음량은 0.19였고 시험 뒤에 0.19, 음소거 해제로 되돌렸습니다(`DEVICE_UPDATED`로 확인).
  - `MEDIA_STATUS`의 `requestId`는 보낸 값(101 등)이 아니라 CEF가 다시 매긴 값(12, 13, 14, 15)이었습니다. 그래서 상태 메시지로 요청을 짝짓지 않고 상태 변화를 기다리는 방식으로 다뤄야 합니다. 다만 `STOP`에는 `"message":null`에 보낸 `sequenceNumber`(102)가 그대로 담긴 확인 메시지가 왔습니다(아래).
  - `STOP`(`집`, 재생 중 보냄, 두 번째 확인): 6초 동안 받은 메시지는 `{"clientId":...,"message":null,"sequenceNumber":102,...}` 하나뿐이었고 `MEDIA_STATUS`(`IDLE`)는 오지 않았습니다. 장치가 재생을 멈췄는지는 이 메시지로 알 수 없었습니다. 따로 한 번 더 보내(`집`, 8초에 `STOP`, 20초에 `terminate()`) 사용자가 화면을 봤습니다: `STOP` 직후 사진 화면(기본 화면)으로 돌아갔고, 20초의 종료 뒤에도 그대로 사진 화면이었습니다. 즉 `STOP`은 재생을 끝내고 수신기를 내려놓지만, 그 사실을 `MEDIA_STATUS`로 알려 주지는 않았습니다(두 번째 확인에서도 6초 동안 확인 메시지 하나뿐이었고 `sequenceNumber`는 보낸 값 101). 이어 보낸 `GET_STATUS`는 3초 동안 아무 메시지도 오지 않았습니다. 재생 중에 보낸 `GET_STATUS`도 4초 동안 응답이 없었습니다(`MEDIA_STATUS`가 따로 계속 오는 것은 CEF가 보내는 것으로 보임, 확인하지 않음).
  - 경로 종료(`terminate()`, 두 번 더 확인): `on_routes`가 빈 목록이 되기까지 두 번 모두 약 1초(확인 간격이 1초)였습니다. 재생 중에 종료한 실행에서는 `on_route_state_changed`가 `TERMINATED`(3)로 왔고 `receiver_action`(`action: stop`) 메시지도 왔습니다. `STOP`을 보낸 뒤 종료한 실행에서는 그 상태 변화를 기다린 1초 안에 오지 않았습니다. 앞서 "시간 안에 끝나지 않은" 두 실행의 원인은 재현하지 못했고, 시험 스크립트의 기다리는 방식 탓이었는지 확인하지 못했습니다.
- **`cefweaver.cast`로 다시 확인 (`집`, 60초 영상)**: `Cast.open`, `find("집")`, `connect`, `load`, `pause`, `play`, `seek(30)`, `set_volume`, `stop`을 8초, 12초, 16초, 20초(음량 0.3), 22초(0.19로 복구), 24초에 불렀습니다. 상태 메시지: 1.8초에 `connected`와 음량 0.19, `BUFFERING` 뒤 `PLAYING`, 8초의 `pause`는 0.2초 뒤 `PAUSED`(영상 위치 5.16초), 12초의 `play`는 0.1초 뒤 `PLAYING`, `seek(30)` 뒤 위치 30.0, 음량은 `on_volume`으로 0.3 뒤 0.19, `stop` 0.2초 뒤 세션이 `closed`가 됐습니다(`disconnect()`는 이미 닫혀 있어 변화 없음). 사용자 확인: 화면에서 일시정지된 위치가 5초였고(영상 위치 5.16초와 맞음, 정지한 시각 8초가 아님), 나머지(다시 재생, 사진 화면으로 돌아감)는 표와 같았습니다. 음량은 0.19로 되돌렸습니다. 설계는 [cefweaver.cast](cast-module.md)에 있습니다.
- **`disconnect()`와 `GET_STATUS` (`집`, `cefweaver.cast`)**: 재생 중(20초)에 `session.disconnect()`를 부르면 장치가 같은 순간 `receiver_action`(`action: stop`)을 보냈고 0.2초 뒤 세션이 `closed`가 됐습니다(14초에 부른 앞선 실행에서는 0.1초). 첫 실행에서는 화면을 보지 못했고, 시간을 늘려 20초에 다시 한 실행에서 사용자가 공 영상이 사라지고 사진 화면으로 돌아간 것 "같다"고 했습니다(확신하지는 않음). 재생 중 8초에 보낸 `GET_STATUS`에는 두 실행 모두 응답이 없었습니다. 싱크 목록은 실행마다 달랐습니다(`집` 하나, `집`과 `욕실`, `집`과 `욕실`과 `그룹`). `욕실`은 화면이 없는 스피커입니다(사용자 설명), 그래서 화면 영상 시험 대상이 아닙니다.
- **페이지 송출 시제품 (`집`, 2026-10-11)**: CEF의 탭 미러링을 쓰지 못하므로(위) 오프스크린 브라우저가 외부 사이트 `https://www.naver.com`을 열고(이 컴퓨터의 일회성 수동 확인, 외부 접속), `on_paint`의 BGRA 프레임(1280x720)을 초당 10장으로 gstreamer(`fdsrc`, `videoparse`, `x264enc`, `mpegtsmux`, `hlssink`, 1초 조각, 목록 3개)에 넘겨 HLS로 만들고, 이 컴퓨터의 HTTP 서버가 내는 `live.m3u8`을 `session.load(주소, content_type="application/x-mpegURL", stream_type="LIVE", media_options={"hlsSegmentFormat": "ts", "hlsVideoSegmentFormat": "mpeg2_ts"})`로 보냈습니다. 장치 없이 만든 조각은 `gst-discoverer`로 H.264 Constrained Baseline, 1280x720, 10fps의 MPEG-TS로 읽혔습니다. 장치(`집`)는 60초 동안 플레이리스트를 58번, 조각을 38번 가져갔고 상태는 `BUFFERING`과 `PLAYING`을 약 3초 간격으로 오갔습니다. 사용자: 화면에 naver.com이 나왔고 오른쪽 위에 겹쳐 넣은 시각이 실제 시각과 일치하는 듯하며(지연을 숫자로 재지는 못했고 눈으로 구분되지 않음), 영상 끊김은 묻는 말에 답하지 않았습니다. 스크롤은 5초마다 넣도록 했는데 사용자는 5초보다 훨씬 빨리 된 것 같다고 했습니다(스크립트의 스크롤 시각 계산을 확인하지 않음). 소리는 넣지 않았습니다. 자동 시험이 아니고 코드는 저장소에 없습니다.
- **DIAL 싱크 검색 (40초)**: `get_name`이 `욕실`(아이콘 `CAST_AUDIO`), `그룹`(`CAST_AUDIO_GROUP`), `집`(`CAST`)인 세 싱크가 나왔고 모두 `is_cast_sink()`가 True, `is_dial_sink()`는 False였습니다. DIAL 싱크는 없었습니다. `get_source("dial:YouTube")`는 `None`이 아닌 소스를 돌려주었으나 `is_dial_source()`가 False, `is_cast_source()`가 True였습니다(`dial:Netflix`, `dial:naver`도 같음). DIAL은 이름 있는 앱을 장치에서 실행하는 프로토콜이라 임의의 웹 페이지를 보내는 수단이 아니라고 알고 있으나 이 환경에서 확인하지는 못했습니다.
- **확인하지 못한 것**: `STOP` 뒤 앱이 내려가는 것을 알리는 메시지가 있는지(오지 않았음), `GET_STATUS`의 응답, `STOP` 뒤 종료의 상태 변화, DIAL 싱크, 탭 화면 미러링, 여러 경로의 동시 사용, 장치 연결이 끊길 때의 `on_route_state_changed`.

## 관련 페이지

- [열지 않은 CEF 메서드와 cefpython의 비교](../analyses/unopened-cef-api.md)
- [Views 확인 기록](verified-findings-views.md)
- [앱 핸들러](app-handler.md)
