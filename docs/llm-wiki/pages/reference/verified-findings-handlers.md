---
title: 실행해서 확인한 핸들러 (F55부터)
type: reference
sources:
  - tests/test_smoke.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - native/cefwrapper/javascript_bindings_handler.h
  - native/cefwrapper/javascript_python_binding_handler.h
updated: 2026-10-08
---

# 실행해서 확인한 핸들러 (F55부터)

생성만 하고 실행하지 못했던 핸들러와 오프스크린 입력을 가상 X 서버에서 실행해 확인했습니다. 시험은 [시험](../components/tests.md)에 있습니다.

## F55. 확인한 것

- **렌더러 종료**: 렌더러 프로세스에 `SIGKILL`을 보내면 `RequestHandler.on_render_process_terminated(browser, status, error_code, error_string)`이 `TerminationStatus`와 함께 오고, 메시지 라우터가 열려 있던 질의를 취소합니다(`on_query_canceled`). 렌더러 프로세스는 `/proc/<pid>/cmdline`에서 `--type=renderer`로 찾았고, Chromium이 자식 프로세스의 제목을 한 문자열로 다시 쓰므로 `\0`으로 나누지 않고 부분 문자열로 찾아야 합니다.
- **새 탭 요청**: 링크를 Ctrl을 누른 채 클릭하면 `RequestHandler.on_open_url_from_tab(browser, frame, target_url, target_disposition, user_gesture)`가 불립니다. `True`를 돌려주면 브라우저가 늘지 않습니다.
- **외부 프로토콜**: `mailto:` 링크를 클릭하면 `RequestHandler.get_resource_request_handler`가 준 `ResourceRequestHandler.on_protocol_execution(browser, frame, request)`가 요청 URL과 함께 불립니다. `False`를 돌려주면 운영체제가 프로그램을 실행하지 않습니다.
- **인증서 오류**: 자체 서명 인증서의 로컬 TLS 서버(시험이 `openssl`로 만듦)에서 `RequestHandler.on_certificate_error(browser, cert_error, request_url, callback)`이 `ErrorCode.CERT_AUTHORITY_INVALID`와 URL로 불립니다. `False`를 돌려주면 페이지가 로드되지 않고, `callback.continue_()`와 `True`를 돌려주면 로드됩니다. Chromium은 허용한 인증서를 호스트별로 기억하므로 거부를 먼저 시험해야 합니다.
- **요청 컨텍스트 핸들러**: `AppHandler.on_context_initialized()`에서 `RequestContext.create_context(settings, handler)`로 만든 컨텍스트를 `set_request_context()`로 첫 브라우저에 주면, 그 브라우저의 요청마다 `RequestContextHandler.get_resource_request_handler`가 브라우저와 프레임과 함께 불리고 돌려준 `ResourceRequestHandler`가 쓰입니다. 핸들러 없는 컨텍스트에서는 이 경로가 없습니다(java-cef도 브라우저를 만들 때 컨텍스트를 줍니다).
- **오프스크린 키 입력**: 영문 한 글자 밖의 `Backspace`, `Delete`, 화살표, `Shift`+문자, `CHAR`만으로 보낸 한글, `Enter`가 입력란의 값과 캐럿, 페이지의 `keydown`에 반영됩니다.
- **터치**: `touch-events` 스위치를 켜고 `send_touch_event`로 누름과 뗌을 보내면 페이지에 `touchstart`와 `touchend`가 옵니다.
- **IME**: `ime_set_composition`이 `compositionupdate`를, `ime_commit_text`가 `compositionend`와 입력란의 값을 만듭니다.
- **팝업 영역**: `<select>`를 클릭하면 `RenderHandler.on_popup_show(browser, True)`, `on_popup_size`, `PaintElementType.POPUP`의 `on_paint`가 오고, 버퍼 크기가 `너비 × 높이 × 4`이며 `on_popup_size`의 `Rect`와 같습니다.

## F56. 한글 조합

- **방법**: 흰 바탕의 입력란에 `ㄱ`, `가`, `각`, `각나` 순서로 `ime_set_composition`을 보내고, 렌더 핸들러의 `on_ime_composition_range_changed`와 `on_paint`의 픽셀을 관찰했습니다. 시험은 3번 연속 통과했습니다.
- **결과**:
  - 글자마다 `compositionupdate`가 오고, 조합이 끝난 뒤 `ime_commit_text`로 확정하면 입력란의 값이 바뀝니다.
  - `on_ime_composition_range_changed(browser, selected_range, character_bounds)`의 `character_bounds`는 조합 중인 글자 수만큼의 `Rect`이고, 입력란 안에 있으며, 둘째 글자의 `x`가 첫째 글자보다 큽니다. 후보 창을 놓을 위치로 쓸 수 있습니다.
  - 밑줄은 `CompositionUnderline`의 두께와 모양이 화면에 반영됩니다. 밑줄 목록이 비었을 때, 얇은 실선, 굵은 실선, 점선의 흰색이 아닌 픽셀 수가 각각 다르고, 굵은 쪽이 더 많습니다.
- **발견(색은 반영되지 않음)**: 밑줄 색을 빨강, 파랑, 초록으로 바꿔 보내도 화면의 색 있는 픽셀은 거의 없었고(0~1개), 밑줄은 글자색(검정)으로 그려졌습니다. Chromium이 색을 쓰지 않는지 CEF가 전달하지 않는지는 조사하지 않았습니다. 그래서 `CompositionUnderline.color`는 기대하지 않는 편이 안전합니다.

## F57. 교차 사이트 iframe의 렌더러 종료와 해결

- **방법**: 로컬 HTTP 서버 둘(`127.0.0.1`과 `localhost`는 다른 사이트)로 메인 페이지와 자식 페이지를 제공하고, 바인딩과 라우터를 하나씩 켜 가며 자식이 스크립트를 실행하는지 서버 요청(`fetch`)으로 확인했습니다.
- **결과**:
  - 바인딩과 라우터가 모두 꺼졌거나 라우터만 켜졌을 때는 교차 사이트 자식이 정상으로 로드되고 스크립트가 돕니다(cefsimple도 같음).
  - `add_javascript_binding`이 켜지면 자식의 `report()` 호출에서 렌더러가 죽었습니다. 렌더러 쪽 `Execute`가 `browser->GetMainFrame()->SendProcessMessage`를 불렀는데, 교차 사이트 자식의 렌더러 프로세스에서는 메인 프레임이 원격 프레임이라 `GetMainFrame()`이 널이기 때문입니다.
  - 호출한 V8 컨텍스트의 프레임(`CefV8Context::GetCurrentContext()->GetFrame()`)에서 메시지를 보내도록 고쳤습니다(두 바인딩 핸들러). 이제 자식 프레임의 `report()`와 메시지 라우터 질의가 브라우저에 닿고, 질의는 자식 프레임(`frame.is_main()`이 `False`)으로 알려집니다. 서로 다른 렌더러 프로세스에 있는 프레임의 라우터가 이것으로 확인되었습니다.
- **유실처럼 보였던 것(정정)**: 자식 프레임이 붙는 중에 메인 프레임에서 보낸 첫 질의가 간혹 오지 않았습니다. 라우터의 문제가 아니었습니다. `app.execute_javascript`는 페이지가 로딩 중이면 실행하지 않고 `False`를 돌려주는데(`OnLoadingStateChange`가 준비 표시를 끔), 자식 iframe의 로드도 로딩에 포함되어 실행되지 않은 것을 시험이 반환값을 보지 않고 지나쳤습니다. 유실된 10번 중 6번은 반환값이 `False`였고 실행된 4번은 모두 답이 왔으며, `Frame.execute_java_script`로 같은 일을 하면 10번 모두 정상이었습니다. `is_ready_to_execute_javascript`를 기다린 뒤에 보내면 10번 모두 통과합니다.

## 관련 페이지

- [실험으로 확인한 사실 (F36부터)](verified-findings-more.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [오프스크린 렌더링](offscreen-rendering.md)
