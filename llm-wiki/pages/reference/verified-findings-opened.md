---
title: 실행해서 확인한 남은 API (F102~F108)
type: reference
sources:
  - tests/test_smoke.py
  - tools/gen/scope.py
  - native/cefwrapper/app_hooks.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - cefweaver/renderer_events.py
updated: 2026-10-10
---

# 실행해서 확인한 남은 API (F102~F108)

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

## 관련 페이지

- [열지 않은 CEF 메서드와 cefpython의 비교](../analyses/unopened-cef-api.md)
- [Views 확인 기록](verified-findings-views.md)
- [앱 핸들러](app-handler.md)
