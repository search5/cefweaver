---
title: cefpython과 cefweaver의 API 차이
type: analysis
sources:
  - cefweaver/_cefweaver.pyi
  - cefweaver/settings.py
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - tools/gen/scope.py
updated: 2026-10-08
---

# cefpython과 cefweaver의 API 차이

> 2026-10-10 점검: 아래 "한눈에" 표의 일부(플랫폼, 툴킷, JavaScript 통신)를 현재 상태로 고쳤습니다. 이하 서술은 2026-10-08 기준이라 "창 임베딩이 없다"처럼 이후에 바뀐 부분이 있습니다. CEF 클래스별로 열린 범위를 대조한 것은 [열지 않은 CEF 메서드와 cefpython의 비교](unopened-cef-api.md)에 있습니다.

cefpython의 API 문서(`api/*.md`, 위키 `docs/llm-wiki`)의 항목 459개를 뽑아 cefweaver의 스텁(`_cefweaver.pyi`, `types.py`, `settings.py`)과 이름으로 대조하고(CamelCase를 snake_case로 바꿔 비교), 이름이 없는 것은 뜻으로 다시 따졌습니다. 이름이 없다고 해서 기능이 없는 것은 아닙니다.

## 한눈에

| 영역 | cefpython | cefweaver |
| --- | --- | --- |
| CEF와 플랫폼 | 오래된 CEF(v66 계열), Windows, Linux, Mac, Python 2와 3 | CEF 154, Linux x86_64와 macOS arm64(Windows 미검증), Python 3.11 이상 |
| 방식 | 손으로 쓴 Cython 바인딩 | 헤더에서 생성(범위 안의 메서드 2131/2255의 타입을 지원) |
| 핸들러 | 12개(소수는 문서만 있음) | java-cef의 13개와 그 밖을 포함해 대부분 |
| 오프스크린 | 있음 | 있음(여러 브라우저, 투명 여부 포함) |
| 값 컨테이너와 스트림, 쿠키, URL 요청 | 일부 | 대부분 |
| 창 임베딩과 GUI 툴킷 | 있음(`WindowInfo.SetAsChild`, Qt, wx, GTK, Tk 예제) | 오프스크린 어댑터 6개(`cefweaver.ui`: Tk, Qt, GTK 3, SDL2, wxPython, Kivy)와 macOS의 네이티브 `NSView`(`parent_view`). **Linux의 창 모드 임베딩(`SetAsChild`)은 확인하지 않음** (2026-10-10 갱신) |
| JavaScript와 Python의 통신 | 풍부함 | 메시지 라우터와 `JavascriptBridge`(JSON, `Promise`, 콜백, `evaluate`). 객체와 속성 바인딩은 없음 (2026-10-10 갱신) |
| 렌더러 프로세스의 Python | 있음 | **없음**(C++만) |

## cefpython에 있고 cefweaver에 없는 것 (큰 순서)

1. **창 임베딩.** `WindowInfo.SetAsChild(부모 창)`, `WindowUtils`, `DpiAware`로 Qt나 wx, GTK, Tk 창 안에 브라우저를 넣습니다. cefweaver는 창 정보를 열지 않아 브라우저가 항상 자기 최상위 창을 만듭니다(`CefWindowInfo`가 범위 밖, [java-cef 동등성](../reference/java-cef-parity.md)). 오프스크린으로 그린 픽셀을 툴킷에 직접 그리는 방식만 가능합니다.
2. **JavaScript와 Python의 풍부한 통신.** `JavascriptBindings`는 함수, 객체, 속성을 바인딩하고, 인자와 반환값에 목록과 사전과 `None`을 쓰며, `JavascriptCallback`으로 JS 콜백을 Python에서 부르고, `Frame.ExecuteFunction`이 JS 함수를 이름으로 부릅니다. cefweaver는 `add_javascript_binding`이 정수, 불리언, 실수, 문자열 인자만 받고 반환값이 없으며, 대신 java-cef와 같은 메시지 라우터(`cefQuery`)가 문자열과 `bytes`를 주고받습니다([메시지 라우터](../reference/message-router.md)).
3. **렌더러 프로세스에서 도는 Python.** cefpython의 `V8ContextHandler`(`OnContextCreated`, `OnContextReleased`)와 렌더러 쪽 훅은 Python 코드가 렌더러에서 동작해야 합니다. cefweaver의 렌더러는 C++만이라 이런 핸들러가 없습니다([알려진 제약](../reference/known-constraints.md)).
4. **CEF를 대신 돌리는 메시지 루프.** `cef.MessageLoop()`(막는 루프), `QuitMessageLoop`, `multi_threaded_message_loop`, `single_process`는 없고 `do_message_loop_work()`를 호출하는 쪽이 부르는 외부 펌프만 있습니다.
5. **스레드 도구.** `PostTask`, `PostDelayedTask`, `IsThread`(생성 범위 밖의 전역 함수).
6. **브라우저 설정.** cefpython의 `BrowserSettings`는 25개 키(`javascript_disabled`, `web_security_disabled`, `image_load_disabled`, `default_encoding`, `local_storage_disabled`, 글꼴 등)입니다. CEF 154의 `CefBrowserSettings`에도 같은 종류의 필드(`javascript`, `image_loading`, `local_storage`, `webgl`, 글꼴 계열과 크기, `default_encoding` 등)가 있지만 cefweaver는 `windowless_frame_rate`만 열었습니다. java-cef도 이것만 엽니다. 그래서 java-cef 수준에서는 격차가 아닙니다.
7. **브라우저 보조 기능**: `Browser.ShowDevTools`(창 정보 구조체 필요), `ToggleFullscreen`, `SetMouseCursorChangeDisabled`, `GetImage`와 `Image`, `LoadString`, `GetBrowserByWindowHandle`, `LoadCrlSetsFile`, 사용자 데이터(`GetUserData`는 파이썬 속성으로 대신 가능).
8. **플랫폼 도구**: Windows와 Mac 전용(`DpiAware`, `SetOsModalLoop`, `app_user_model_id`, `framework_dir_path`, Mac의 키 처리 훅).
9. **오래된 것**: 플러그인과 Flash(`OnPluginCrashed`, `WebPluginInfo`), `OnQuotaRequest`, `AccessibilityHandler`의 전역 콜백, `ApplicationSettings`의 폐기된 키.

## 이름은 다르지만 있는 것

- `CreateBrowserSync`는 `create_browser`, `MessageLoopWork`는 `do_message_loop_work`, `GetFrame(s)`는 `get_frame_by_identifier`와 `get_frame_identifiers`, `SendFocusEvent`는 `set_focus`, `GetOuterWindowHandle`은 `get_window_handle`입니다.
- `RequestHandler.CanGetCookies`와 `CanSetCookie`는 쿠키 접근 필터(`can_send_cookie`, `can_save_cookie`), `OnRendererProcessTerminated`는 `on_render_process_terminated`, 요청 컨텍스트별 쿠키는 `RequestContext`입니다.
- `ApplicationSettings`의 키 가운데 `locale`, `javascript_flags`, `command_line_args_disabled`, `browser_subprocess_path`, `windowless_rendering_enabled`(`offscreen`), `unique_request_context_per_browser`(`create_browser(request_context=...)`), `product_version`(`user_agent_product`)에 대응이 있습니다.
- `NetworkError`의 상수 50개는 `types.ErrorCode`, `Cookie`의 getter와 setter 17개는 `Cookie` 구조체의 필드, `WebRequest`는 `URLRequest`입니다.
- `SetGlobalClientCallback`과 `SetClientHandler`는 `set_client(Client)` 하나로 합쳐져 있습니다.

## cefweaver에만 있는 것

생성기로 연 라이브러리 클래스(`BrowserHost`의 IME, 터치, 줌, 인쇄, 요청 컨텍스트와 설정, 값 컨테이너, 스트림, ZIP, 작업 관리자 등), 쿠키 접근 필터, DevTools 메시지 관찰자, 메시지 라우터의 `bytes`, 사용자 스킴 등록(`AppHandler`), 여러 브라우저와 브라우저별 투명도, `Settings`, `get_version()` 등. 자세한 목록은 [java-cef 동등성](../reference/java-cef-parity.md)의 "바닥 위"에 있습니다.

## cefweaver가 채워야 하는 격차 (2026-10-08 판단)

기준은 "오프스크린을 툴킷의 위젯으로 감싸는 임베딩"입니다. 창 핸들을 얻는 X11 방식(`SetAsChild`)은 Wayland에 임베딩 수단이 없고, 오프스크린은 디스플레이 서버 없이도 동작합니다([F61](../reference/verified-findings-handlers.md)). 위젯이 키, 마우스, 터치, IME, 드래그, 팝업, 배율을 이미 주고받을 수 있으므로(F38, F55, F56) 창 임베딩은 채우지 않습니다.

| 순서 | 격차 | 이유 |
| --- | --- | --- |
| 1 (**완료**, F62) | 메시지 펌프 예약(`on_schedule_message_pump_work`, `external_message_pump`) | 툴킷이 이벤트 루프를 가지므로 CEF가 "지금 돌려 달라"고 알리는 훅이 있어야 타이머 폴링 없이 지연과 CPU를 줄입니다. 지금은 호출하는 쪽이 짧은 주기로 `do_message_loop_work()`를 부릅니다. cefpython에는 있고 java-cef에는 없습니다. |
| 2 (**완료**, F63) | `post_task`, `is_thread`(UI 스레드로 보내기) | 툴킷과 CEF가 다른 스레드에서 얽힐 때 필요하고, 예약 훅과 함께 쓰입니다. |
| 3 (**완료**, [F64](../reference/verified-findings-handlers.md)) | 브라우저 설정(`BrowserSettings`) | 글꼴, 기본 인코딩, JavaScript나 로컬 저장소 끄기 등을 위젯 하나마다 정합니다. CEF 154의 필드를 구조체로 열면 됩니다(생성기가 문자열 필드를 지원). java-cef 수준을 넘음. |
| 4 (**완료**, [JavascriptBridge](../reference/javascript-bridge.md)) | JS와 Python의 풍부한 통신 | 위젯 앞 화면(HTML)과 Python의 연결이 임베딩 응용의 핵심입니다. 렌더러에 Python을 두지 않고 메시지 라우터 위에서 JSON으로 목록, 사전, `None`, 반환값, 콜백을 주고받는 보조 계층으로 풀 수 있습니다. java-cef 수준을 넘음. |
| 5 (**기능 완료, 내용은 미확인**, [공유 텍스처](../reference/shared-textures.md)) | GPU 가속 페인트(`on_accelerated_paint`) | 복사 없이 텍스처를 넘기는 최적화입니다. 콜백과 메타데이터는 확인했고 픽셀 내용은 이 환경에서 확인하지 못했습니다. |

채우지 않을 것: 창 임베딩(`SetAsChild`, `WindowUtils`, `DpiAware`), 렌더러의 Python, 막는 `MessageLoop`(툴킷이 루프를 가짐), `ShowDevTools`(원격 디버깅 포트로 대신함), 플랫폼 전용과 오래된 항목.

## 맺음

용도가 갈립니다. cefpython은 **GUI 툴킷에 브라우저를 심고 Python과 JavaScript가 깊게 얽히는 응용**에, cefweaver는 **최신 CEF의 API를 넓게(그리고 헤더에 맞춰 정확하게) 쓰는 응용**에 맞습니다. cefweaver가 cefpython을 대체하려면 창 임베딩과 JS 바인딩의 확장이 가장 큰 일이고, 둘 다 java-cef에는 없는 범위(창 임베딩은 AWT에 맡김, JS는 메시지 라우터)입니다.

## 관련 페이지

- [java-cef 동등성](../reference/java-cef-parity.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
- [cefpython의 CEF 패치와 cefweaver](cefpython-patches.md)
