---
title: 실행해서 확인한 핸들러 (F55)
type: reference
sources:
  - tests/test_smoke.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
updated: 2026-10-08
---

# 실행해서 확인한 핸들러 (F55)

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

## 관련 페이지

- [실험으로 확인한 사실 (F36부터)](verified-findings-more.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [오프스크린 렌더링](offscreen-rendering.md)
