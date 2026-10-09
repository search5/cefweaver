---
title: 실행해서 확인한 핸들러 (F55부터)
type: reference
sources:
  - tests/test_smoke.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - cefweaver/settings.py
  - cefweaver/version.py
  - native/cefwrapper/library.cpp
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
- **인증서 오류**: 자체 서명 인증서의 로컬 TLS 서버(시험이 `openssl`로 만듦)에서 `RequestHandler.on_certificate_error(browser, cert_error, request_url, callback)`이 `ErrorCode.CERT_AUTHORITY_INVALID`와 URL로 불립니다. `False`를 돌려주면 페이지가 로드되지 않고, `callback.continue_()`와 `True`를 돌려주면 로드됩니다. 한 번 허용하면 같은 호스트의 다음 요청에서는 핸들러가 다시 불리지 않고(거부하도록 바꿔도 `/second`, `/third`가 로드됨) 페이지가 로드됩니다. 이 예외 기억은 Chromium의 것이고 CEF는 `Continue()`를 넘기기만 합니다(`libcef/browser/certificate_query.cc`). 그래서 거부 시험을 먼저 해야 합니다.
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
- **발견(색은 반영되지 않음)**: 밑줄 색을 빨강, 파랑, 초록으로 바꿔 보내도 화면의 색 있는 픽셀은 거의 없었고(0~1개), 밑줄은 글자색(검정)으로 그려졌습니다. CEF는 색을 `ImeTextSpan`의 `underline_color`로 그대로 전달합니다(`libcef/browser/osr/render_widget_host_view_osr.cc` 853~860줄에서 확인). 그리지 않는 쪽은 Chromium의 렌더러이고, 그 소스가 이 환경에 없어 원인은 확인하지 못했습니다. 그래서 `CompositionUnderline.color`는 기대하지 않는 편이 안전합니다.

## F57. 교차 사이트 iframe의 렌더러 종료와 해결

- **방법**: 로컬 HTTP 서버 둘(`127.0.0.1`과 `localhost`는 다른 사이트)로 메인 페이지와 자식 페이지를 제공하고, 바인딩과 라우터를 하나씩 켜 가며 자식이 스크립트를 실행하는지 서버 요청(`fetch`)으로 확인했습니다.
- **결과**:
  - 바인딩과 라우터가 모두 꺼졌거나 라우터만 켜졌을 때는 교차 사이트 자식이 정상으로 로드되고 스크립트가 돕니다(cefsimple도 같음).
  - `add_javascript_binding`이 켜지면 자식의 `report()` 호출에서 렌더러가 죽었습니다. 렌더러 쪽 `Execute`가 `browser->GetMainFrame()->SendProcessMessage`를 불렀는데, 교차 사이트 자식의 렌더러 프로세스에서는 메인 프레임이 원격 프레임이라 `GetMainFrame()`이 널이기 때문입니다.
  - 호출한 V8 컨텍스트의 프레임(`CefV8Context::GetCurrentContext()->GetFrame()`)에서 메시지를 보내도록 고쳤습니다(두 바인딩 핸들러). 이제 자식 프레임의 `report()`와 메시지 라우터 질의가 브라우저에 닿고, 질의는 자식 프레임(`frame.is_main()`이 `False`)으로 알려집니다. 서로 다른 렌더러 프로세스에 있는 프레임의 라우터가 이것으로 확인되었습니다.
- **유실처럼 보였던 것(정정)**: 자식 프레임이 붙는 중에 메인 프레임에서 보낸 첫 질의가 간혹 오지 않았습니다. 라우터의 문제가 아니었습니다. `app.execute_javascript`는 페이지가 로딩 중이면 실행하지 않고 `False`를 돌려주는데(`OnLoadingStateChange`가 준비 표시를 끔), 자식 iframe의 로드도 로딩에 포함되어 실행되지 않은 것을 시험이 반환값을 보지 않고 지나쳤습니다. 유실된 10번 중 6번은 반환값이 `False`였고 실행된 4번은 모두 답이 왔으며, `Frame.execute_java_script`로 같은 일을 하면 10번 모두 정상이었습니다. `is_ready_to_execute_javascript`를 기다린 뒤에 보내면 10번 모두 통과합니다.

## F58. 설정(`CefSettings`)과 투명한 오프스크린

- **방법**: `CefApp.settings`(`cefweaver.Settings`)의 필드를 정하고 `initialize()`한 뒤 효과를 관찰했습니다.
- **효과를 확인한 것**:
  - `user_agent`: `navigator.userAgent`가 그 문자열이 됩니다. `user_agent_product`: 기본 사용자 에이전트에 그 토큰이 들어갑니다.
  - `locale="ko"`: `navigator.language`가 `ko`로 시작합니다. `javascript_flags="--expose-gc"`: 페이지에 `gc`가 있습니다.
  - `log_file`, `log_severity`: 로그 파일이 만들어지고 내용이 있습니다.
  - `remote_debugging_port`: `http://127.0.0.1:<포트>/json/version`이 `Browser` 항목을 줍니다.
  - `persist_session_cookies`: 캐시 디렉터리를 공유하는 두 프로세스에서 켜면 세션 쿠키가 다음 프로세스에 남고(쓰는 쪽은 `CookieManager.flush_store` 뒤 종료), 끄면 남지 않습니다.
  - `background_color`: 투명하지 않은 오프스크린 브라우저에서 문서가 그리지 않는 곳이 그 색이 됩니다(`0xFF00FF00`이 초록).
- **효과를 확인하지 못한 것**: `chrome_policy_id`, `uncaught_exception_stack_size`, `command_line_args_disabled`, `cookieable_schemes_list`, `cookieable_schemes_exclude_defaults`는 설정하고 CEF가 시작해 페이지가 동작하는 것만 확인했습니다(정책 파일, 렌더러의 예외 핸들러, 쿠키를 쓰는 사용자 스킴이 필요함).
- **발견(CEF의 규칙)**: 오프스크린 브라우저는 브라우저 설정의 색 알파가 0이면 "투명하게 그린다"로 확정되어 `CefSettings.background_color`를 보지 않습니다(`CefContext::GetBackgroundColor`). java-cef도 투명하지 않을 때 브라우저 설정에 흰색을 넣습니다. 그래서 `CefApp.transparent`(기본 `True`, 지금까지의 동작)를 만들고, `False`이면 `settings.background_color`(알파 0xFF일 때) 또는 흰색을 브라우저 설정에 넣습니다. 창이 있는 브라우저는 전역 `background_color`가 그대로 쓰입니다. 창의 픽셀은 X 서버에서 `XGetImage`로 읽어 확인했습니다(`ctypes`로 `libX11`을 부름): 설정하지 않으면 `0xFFFFFF`, `0xFF00FF00`을 주면 `0x00FF00`입니다.
- **`root_cache_path`**: 따로 정할 수 있습니다(java-cef와 같음). 정하면 프로필 데이터(`Local State`, `Default/`)가 그 아래에 생기고, `set_cache_path()`의 디렉터리는 만들어지기만 합니다(CEF가 프로필을 루트에 둠). `set_cache_path()`가 루트 안에 있지 않으면 CEF의 요구(캐시 경로는 루트이거나 그 안)에 맞추어 캐시 경로를 루트로 바꿉니다. 정하지 않으면 지금까지처럼 둘이 같습니다.

## F59. 버전 조회

- **방법**: `cefweaver.get_version()`을 CEF를 시작하기 전에 불러, 설치된 CEF 헤더(`cef_version.h`)의 값과 비교했습니다.
- **결과**: `Version(cefweaver, cef_major, cef_minor, cef_patch, cef_commit, chrome_major, chrome_minor, chrome_build, chrome_patch)`가 헤더의 `CEF_VERSION_*`, `CEF_COMMIT_NUMBER`, `CHROME_VERSION_*`와 같고, `version.cef`(`154.0.34`)와 `version.chrome`(`154.0.8037.98`)이 문자열을 줍니다. `CefApp.get_version()`은 같은 값을 돌려줍니다. 값은 libcef의 `cef_version_info()`에서 오므로 `initialize()` 전에도 부를 수 있습니다. `cefweaver` 항목은 설치된 패키지 메타데이터의 버전입니다(java-cef의 JCEF 버전에 해당).

## F60. 브라우저 여러 개

- **방법**: `CefApp.create_browser(url, offscreen=None, transparent=None, request_context=None)`로 첫 브라우저 뒤에 브라우저를 만들고, 그림, JS 바인딩, 라우터, 닫기, 요청 컨텍스트를 확인했습니다.
- **결과**:
  - 오프스크린 브라우저는 자기 `on_paint`를 받고(`browser`로 구분) 첫 브라우저의 그림은 그대로입니다. 투명 여부는 브라우저마다 정합니다(`transparent=False`가 흰색, 기본이 투명).
  - 창이 있는 앱에서 창이 있는 브라우저와 오프스크린 브라우저(`offscreen=True`)를 섞을 수 있습니다(`is_window_rendering_disabled`로 확인).
  - JS 바인딩(`report`)과 메시지 라우터가 모든 브라우저에서 동작하고, 핸들러는 질의한 `browser`를 받습니다.
  - 한 브라우저를 닫아도 나머지와 앱은 계속 돕니다(`is_running`). 모든 브라우저가 닫히면 `is_running`이 거짓이 됩니다.
  - `request_context`를 주면 그 브라우저의 요청이 그 컨텍스트의 핸들러를 거칩니다(`get_resource_request_handler`에 그 브라우저가 옴).
  - 인자의 형식이 틀리면 `TypeError`, CEF가 돌지 않거나 첫 브라우저가 아직 없으면 `RuntimeError`입니다.
- **발견(결함, 수정)**: `is_ready_to_execute_javascript`(`execute_javascript`가 실행되는 조건)가 어느 브라우저의 로딩에나 따라 바뀌었습니다. 로딩이 긴 브라우저를 만들면 첫 브라우저의 스크립트 실행이 막혔습니다(팝업도 같았음). 이제 첫 브라우저(`initialize()`가 만든 것)의 로딩만 따릅니다. 또 첫 브라우저가 닫힌 뒤 `execute_javascript`가 널 프레임을 참조할 수 있어 `False`를 돌려주도록 했습니다.
- **제약**: `load_url()`과 `execute_javascript()`는 첫 브라우저만 다룹니다(다른 브라우저는 `Browser.get_main_frame()`으로). 같은 스레드(`initialize()`를 부른 스레드)에서만 만들 수 있습니다.

## F61. 오프스크린은 디스플레이 서버가 필요 없다

- **방법**: `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_SESSION_TYPE`을 지우고 `ozone-platform=headless`로 오프스크린 브라우저를 띄웠습니다.
- **결과**: X 서버도 Wayland도 없이 그림(`on_paint`), 스크립트 실행, 정상 종료가 모두 동작했습니다. 오프스크린의 픽셀은 창 시스템이 아니라 CEF가 만들어 주므로 창 임베딩(`SetAsChild`)이 필요 없고, Wayland에서 Alloy 창이 죽는 문제(F31)를 피합니다. 네이티브 Wayland(`ozone-platform=wayland`)에서의 오프스크린은 확인하지 않았습니다.

## F62. 메시지 펌프 예약

- **방법**: `settings.external_message_pump = True`와 `AppHandler.on_schedule_message_pump_work`로 CEF의 요청을 받고, 폴링 없이 요청의 기한에만 `do_message_loop_work()`를 불러 페이지를 로드했습니다.
- **결과**:
  - 훅은 CEF의 여러 스레드에서 불리고(주 스레드가 아닌 스레드 포함) 지연은 `int`입니다. 설정을 켜지 않으면 불리지 않습니다.
  - 요청 하나로는 부족했습니다. 처음에 한 번 요청한 뒤 CEF가 더 요청하지 않아 페이지가 로드되지 않았습니다. CEF의 규약은 (1) 새 요청이 이전 요청을 대체하고 (2) 모든 종류의 일이 알려지지는 않으므로 어느 경우에도 1/30초(cefclient의 `kMaxTimerDelay`)보다 오래 기다리지 않는 것입니다.
  - 이 규약을 `cefweaver.MessagePump`(순수 Python)에 담았습니다. `timeout()`은 다음 실행까지의 초(최대 1/30), `run()`은 기한이 되었으면 `do_message_loop_work()`를 부르고 `True`를 돌려줍니다(재진입 방지, 실행 중에 CEF가 요청하면 그 요청을 잃지 않음). `wake(delay)`는 CEF가 요청할 때마다 어느 스레드에서나 불려 잠든 이벤트 루프를 깨웁니다. 폴링 없이 기한만으로 페이지가 로드되는 것을 5번 확인했습니다.
- **제약**: `on_schedule_message_pump_work`는 다른 훅과 달리 `initialize()`를 부른 스레드에서 불리지 않으므로 그 안에서 CEF나 툴킷의 객체를 만지면 안 됩니다.

## F63. 스레드로 보내는 작업

- **방법**: `cefweaver.Task`를 상속한 객체를 `post_task(ThreadId.UI, task)`, `post_delayed_task(..., delay_ms)`로 보내고, 어느 스레드에서 도는지 `currently_on(thread_id)`와 스레드 번호로 확인했습니다.
- **결과**:
  - `post_task`는 어느 스레드에서 불러도 되고, UI 작업은 `post_task` 안이 아니라 메시지 루프(`do_message_loop_work()`) 안에서 `initialize()`를 부른 스레드로 돕니다. 파이썬 스레드에서 보낸 작업도 같습니다.
  - `ThreadId.IO`로 보낸 작업은 다른 스레드에서 돌고 그 안에서 `currently_on(ThreadId.IO)`가 참입니다. `Task.execute`는 그 스레드에서 GIL을 잡고 실행됩니다.
  - `post_delayed_task(ThreadId.UI, task, 300)`은 300ms 전에 돌지 않습니다(250ms 이상).
  - 다른 스레드에서 UI 작업을 보내면 CEF가 메시지 펌프 예약을 요청하므로, `MessagePump`의 기한만으로 돌리는 응용에서도 그 작업이 실행됩니다(F62).
- **생성기의 수정**: `CefThreadId`는 `typedef cef_thread_id_t CefThreadId;`라는 C++ 별칭이어서 구조체로 오인되어 함수가 만들어지지 않았습니다. 생성기가 `typedef cef_..._t Cef...;` 별칭을 열거형으로 읽도록 고쳤습니다(`CefProcessId`, `CefValueType`도 같은 별칭).

## F64. 브라우저 설정(`BrowserSettings`)

- **방법**: `CefApp.browser_settings`(첫 브라우저와 설정 없이 만드는 브라우저) 또는 `create_browser(settings=...)`에 `types.BrowserSettings`를 주고 페이지에서 관찰했습니다.
- **생성기의 수정**: `cef_browser_settings_t`에는 `#if CEF_API_ADDED(...)` 아래의 멤버가 있어 구조체로 읽히지 않았습니다. 조건부 블록은 컴파일하는 API 버전에 따라 달라지므로 필드에서 뺍니다(`databases`, `ax_viewport_collapse`). 초기화 전용인 `CefSettings`는 값 타입에서 제외합니다.
- **효과가 유지되는 것**: `javascript`(꺼진 브라우저가 `<noscript>` 내용을 보임, `meta refresh`로 이동한 두 번째 문서도), `image_loading`(`http:`의 이미지가 그려지지 않음), `local_storage`(`localStorage`가 막힘), 글꼴 이름(`standard_font_family`), `background_color`(불투명 오프스크린에서 `BrowserSettings`의 색이 앱의 색보다 우선). 브라우저마다 따로 정할 수 있고 다른 브라우저는 영향이 없습니다.
- **CEF의 한계로 확인한 것**([검증 방법](../procedures/verify-cef-limits.md): 래퍼 없이 `cefsimple`에 같은 설정을 넣고 Chrome 스타일과 Alloy 스타일 모두에서 DevTools 프로토콜로 읽음):
  - 글꼴 크기 4개(`default_font_size`, `default_fixed_font_size`, `minimum_font_size`, `minimum_logical_font_size`)는 유지되지 않습니다. `cefsimple`의 Chrome 스타일에서 처음 값(30px, 50px)이 나온 뒤 16px로 되돌아가고, Alloy 스타일에서는 처음부터 16px입니다. 래퍼가 만든 현상이 아닙니다.
  - `default_encoding`은 두 스타일 모두 반영되지 않습니다(`document.characterSet`이 `windows-1252`).
  - `image_loading`을 꺼도 `data:` URL의 이미지는 로드됩니다(`http:` 이미지만 막힘, `naturalWidth` 0). Blink의 동작입니다.
  - 앞의 둘은 `expectedFailure` 시험이 CEF의 수정을 알려 줍니다.
- **기본값 규칙**: 필드의 기본값은 CEF가 정합니다(0, 빈 문자열, `State.DEFAULT`). 앱은 `windowless_frame_rate`가 0이면 `CefApp.windowless_frame_rate`를, 불투명 오프스크린에서 `background_color`의 알파가 0xFF가 아니면 설정의 색(없으면 흰색)을 넣습니다.
- **창 정보 구조체(`CefWindowInfo`)는 여전히 열지 않았습니다.**

## F65. JavascriptBridge

- **방법**: `JavascriptBridge`로 함수를 노출하고 페이지의 `Promise`, 콜백, `evaluate`를 `report` 바인딩으로 관찰했습니다. 사용법과 동작은 [JavascriptBridge](javascript-bridge.md)에 있습니다.
- **결과**:
  - 인자와 반환값에 `None`, 불리언, 정수, 실수(`0.1 + 0.2`가 `0.30000000000000004`), 문자열, 중첩한 목록과 사전이 오갑니다. `Promise.all`도 됩니다. 파이썬 예외는 `ZeroDivisionError: ...`로, JSON이 되지 않는 반환값은 `TypeError: ...`로 `Promise`를 거부합니다.
  - 페이지의 함수를 인자로 주면 `JsCallback`이 되어 Python이 호출 안에서도, 그 뒤 언제든 부를 수 있습니다. `release()` 뒤에는 페이지에서 불리지 않습니다.
  - `execute_function`과 `evaluate`는 중첩한 경로(`api.greet`)와 `Promise`를 지원합니다. 문법 오류는 `SyntaxError: Unexpected end of input`으로 돌아옵니다.
  - `origins`에 없는 URL의 프레임은 `origin not allowed`로 거부되고, 응용 자신의 `cefQuery`는 영향받지 않습니다.
  - iframe, 둘째 브라우저, **다른 사이트의 프레임(다른 렌더러 프로세스)**에서도 동작합니다. 그 프레임의 `JsCallback.call`이 해당 렌더러로 들어갑니다.
- **발견(시험으로 고친 것)**: `evaluate`의 오류 문자열에 오류 이름이 없어 `Unexpected end of input`만 왔습니다. 이름을 붙여 `SyntaxError: ...`가 되게 고쳤습니다.
- **안정성**: 브리지 시험 6개를 묶어 5번 연속 통과했고(한 번의 실행에 약 2.5초), 다른 사이트의 프레임 시험은 따로 4번 연속 통과했습니다. 간헐적 실패는 보이지 않았습니다.
- **안전**: `origins`를 정하지 않으면 모든 프레임이 노출한 함수를 부를 수 있습니다. 바깥 페이지가 올라올 수 있는 응용은 `origins`를 정해야 합니다.

## F66. 공유 텍스처 (GPU 가속 페인트)

사용법과 규칙은 [공유 텍스처](shared-textures.md)에 있습니다. 여기에는 실행해서 확인한 것을 적습니다.

- **GPU가 없는 환경(Xvfb)**: DRI3가 없어 `gbm device is missing`이 나고, CEF는 `on_accelerated_paint` 대신 `on_paint`로 그림을 줍니다(`shared_texture`를 켜도). 그래서 켜진 브라우저가 어느 쪽으로든 프레임을 받고 충돌하지 않는 것을 항상 시험합니다. `headless` 플랫폼에서도 텍스처는 오지 않았습니다.
- **실제 GPU(NVIDIA RTX 4060 Laptop, 독점 드라이버 580, XWayland `DISPLAY=:0`, 오프스크린이라 창은 열리지 않음)**:
  - 기본 설정과 `use-angle=gl`에서는 텍스처가 오지 않고 `OzoneImageBacking::ProduceSkiaGanesh failed to create GL representation`이 납니다.
  - `use-gl=angle`, `use-angle=vulkan`, `enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan`에서 텍스처가 옵니다(DevTools의 `SystemInfo`로 ANGLE Vulkan, NVIDIA를 확인). `info.format`은 `BGRA_8888`, `modifier`는 0(선형), 평면 1개(stride 1024, 크기 102400, 200x100 + 정렬), `extra.coded_size`는 200x100, 더티 사각형이 함께 옵니다. 디스크립터는 콜백 안에서 열려 있고(`os.fstat`), 페이지를 바꾸면 새 프레임이 옵니다. `on_paint`는 불리지 않습니다. 이 시험(`CEFWEAVER_TEST_GPU=1`)은 3번 연속 통과했습니다.
- **확인하지 못한 것(픽셀 내용)**: 위 설정에서 텍스처가 **모두 0**으로 읽혔습니다. 같은 설정의 일반 경로(`on_paint`)에서는 빨간 픽셀이 나오므로 페이지는 그려지고 있습니다. 해 본 것: `mmap`으로 읽기(`read_plane`), EGL로 가져와 외부 텍스처로 샘플링하고 `glReadPixels`(렌더 대상에 붙이는 방식은 `GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT`로 막힘), 콜백 안과 콜백 뒤 1.5초 뒤(복제한 디스크립터), 페이지를 초록으로 바꾼 뒤, `transparent`를 켜고 끄기, Mesa EGL 강제(`__EGL_VENDOR_LIBRARY_FILENAMES`). 모두 0이었고 AMD 내장 GPU(RADV)로 강제하는 시도는 GPU 프로세스가 종료되어 비교하지 못했습니다. **원인(드라이버의 암묵적 동기화 부재, CEF/Chromium, 우리 쪽)은 가르지 못했습니다.** 그러므로 CEF의 한계로 적지 않습니다. 가르는 방법: Mesa만 쓰는 GPU(Intel, AMD 전용 기기)에서 `CEFWEAVER_TEST_GPU_PIXELS=1`로 같은 시험 실행, 또는 CEF 예제 `cefclient`의 오프스크린 공유 텍스처와 비교.

## F67. GTK 3 예제

실제 GTK 3 창에서 돌린 결과는 [GTK 3 예제](gtk3-example.md)에 있습니다. 요약: 27개 점검(복사와 붙여넣기, 드래그 앤 드롭 포함)이(지금은 33개) 1배와 2배(HiDPI)에서 모두 통과했고, `on_after_created`에서 `CefApp`을 쓸 수 없던 결함을 고쳤으며, 뒤로 가기 캐시로 복원된 페이지가 크기 변경을 받지 않는 현상(원인 미확인, `notify_screen_info_changed()`로 우회)을 찾았습니다.

## F68. 열거형 인자의 폭

생성된 메서드의 열거형 인자가 부호 있는 `int`여서 `DragOperationsMask.EVERY`(0xFFFFFFFF)를 넘기면 `OverflowError`가 났습니다. 페이지가 드래그를 시작하면 `start_dragging`의 `allowed_ops`가 바로 `EVERY`이고 이를 `drag_target_drag_over`에 되돌려 주는 것이 자연스러운 사용입니다(Tk 예제에서 발견). 열거형 인자를 `long long`으로 받도록 생성기를 고쳤습니다(시험 `test_a_flags_enum_with_the_highest_bit_can_be_given_to_cef`).

## F69. 툴킷 예제 (Qt, Tkinter, SDL2, wxPython, Kivy)

방법: 각 예제를 uv 환경에 설치해 가상 X 서버에서 X11을 강제하고 실제 X 이벤트(xdotool)로 구동했습니다(`examples/*/smoke.py`). 결과와 근거는 [툴킷 예제](toolkit-examples.md)에 있고, 여기에는 확인한 사실과 확인하지 못한 것만 적습니다.

- **확인함**: 다섯 예제의 점검이 모두 통과합니다(24~27개). Qt는 PyQt6와 PySide6 모두 통과했습니다.
- **확인함(wx)**: `wx.DropSource.DoDragDrop()`은 마우스 이벤트 핸들러 밖에서(`wx.CallAfter`) 부르면 0.2 ms 만에 `DragNone`으로 돌아옵니다. 임시 데이터 객체를 넘기면(`SetData`가 소유하지 않음) `DoDragDrop` 안에서 SIGSEGV가 납니다(gdb로 확인).
- **확인함(wx)**: 한꺼번에 보낸 `drag_target_drag_enter`, `drag_target_drag_over`, `drag_target_drop`에서 첫 드롭이 페이지에 `dragenter`, `dragover`, `dragleave`로만 닿았고 `drop`이 오지 않았습니다. `update_drag_cursor`(`dragover`에 대한 답)가 온 뒤 `drop`을 보내면 닿았습니다. **렌더러가 답하기 전에 놓기가 처리되는 경합으로 추정하지만 CEF 소스에서 확인하지 않았습니다.** `cefweaver.ui`로 옮기기 전의 SDL2 예제는 한꺼번에 보내는 방식으로 통과했고(같은 경합이 있을 수 있었음), 지금은 `BrowserView.drop()`이 답을 기다립니다.
- **확인함(Kivy)**: 기본 설정에서 Esc를 누르면 앱이 끝납니다(`exit_on_escape`). Kivy가 보고하는 휠 방향 `scrollup`은 X의 버튼 5(페이지가 아래로)입니다.
- **확인함(Qt, Tk)**: CEF에 맡긴 복사와 붙여넣기는 멈추거나 값이 비었고, 위젯이 직접 처리하니 통과했습니다. SDL2, wx, Kivy는 처음부터 위젯이 처리해서 CEF에 맡겼을 때의 동작은 확인하지 않았습니다.
- **확인함**: SDL2에서 `on_after_created`의 `set_focus(True)`만으로는 한글 조합과 `<select>` 팝업이 동작하지 않았고 클릭에서 다시 주면 동작했습니다. 원인 미조사.
- **확인함**: `tkinterdnd2`의 루트(`TkinterDnD.Tk()`)는 CEF 시작 시 `Unknown sequence number`로 프로세스를 중단시킵니다. `XInitThreads` 호출과 정적 X11 링크 가설은 아니었습니다. **원인 미확인.**
- **확인함(uv)**: wxPython은 PyPI에 Linux wheel이 없어 `find-links`로는 uv가 PyPI의 소스 배포본을 골라 오래 빌드합니다. wxPython 사이트의 wheel 주소를 `tool.uv.sources`에 직접 적어야 설치됩니다(해석에 2분, 이 사이트는 요청 하나에 20초 이상).

## F70. UI 어댑터 (cefweaver.ui)

- **확인함**: `HeadlessAdapter`로 실제 브라우저를 띄워 첫 그림(페이지의 색), 클릭(제목이 바뀜), 키와 한글 확정(입력란), 외부 드롭, 크기 변경, 정상 종료가 `BrowserView`와 `Session`만으로 동작합니다(5번 연속 통과). 단위 시험 47개는 가짜 브라우저로 이벤트 변환을 확인합니다([UI 어댑터 API](ui-api.md)).
- **확인함**: `DragData.get_file_name()`은 CEF를 초기화하기 전에 부르면 프로세스를 중단시키고(`Trace/breakpoint trap`, 종료 코드 133), 초기화한 뒤에는 `add_file`로 파일을 넣은 데이터에서도 빈 문자열을 돌려줍니다. 같은 데이터의 `get_file_names()`와 `get_file_paths()`는 초기화 전에도 값을 줍니다. **초기화 전에 중단하는 원인은 조사하지 않았습니다.** 파일 이름은 `get_file_paths()`로 얻습니다.

## 관련 페이지

- [실행해서 확인한 미디어 (F71부터)](verified-findings-media.md): 권한, 오디오, 유튜브 재생
- [실험으로 확인한 사실 (F36부터)](verified-findings-more.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [오프스크린 렌더링](offscreen-rendering.md)
