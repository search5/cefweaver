---
title: 실행해서 확인한 남은 API (F102~F111)
type: reference
sources:
  - tests/test_smoke.py
  - tools/gen/scope.py
  - native/cefwrapper/app_hooks.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - cefweaver/renderer_events.py
  - native/cefwrapper/bridge.h
updated: 2026-10-10
---

# 실행해서 확인한 남은 API (F102~F111)

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

- **미디어 라우터**: 이 환경에는 Cast 장치가 없어 싱크와 경로가 0개로 옵니다(`on_sinks`, `on_routes`). 실제 장치와의 동작은 확인하지 못했습니다.
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

## 관련 페이지

- [열지 않은 CEF 메서드와 cefpython의 비교](../analyses/unopened-cef-api.md)
- [Views 확인 기록](verified-findings-views.md)
- [앱 핸들러](app-handler.md)
