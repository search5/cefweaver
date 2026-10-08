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

cefpython의 API 문서(`api/*.md`, 위키 `docs/llm-wiki`)의 항목 459개를 뽑아 cefweaver의 스텁(`_cefweaver.pyi`, `types.py`, `settings.py`)과 이름으로 대조하고(CamelCase를 snake_case로 바꿔 비교), 이름이 없는 것은 뜻으로 다시 따졌습니다. 이름이 없다고 해서 기능이 없는 것은 아닙니다.

## 한눈에

| 영역 | cefpython | cefweaver |
| --- | --- | --- |
| CEF와 플랫폼 | 오래된 CEF(v66 계열), Windows, Linux, Mac, Python 2와 3 | CEF 154, Linux x86_64만(Windows 미검증), Python 3.11 이상 |
| 방식 | 손으로 쓴 Cython 바인딩 | 헤더에서 생성(범위 안의 메서드 2131/2255의 타입을 지원) |
| 핸들러 | 12개(소수는 문서만 있음) | java-cef의 13개와 그 밖을 포함해 대부분 |
| 오프스크린 | 있음 | 있음(여러 브라우저, 투명 여부 포함) |
| 값 컨테이너와 스트림, 쿠키, URL 요청 | 일부 | 대부분 |
| 창 임베딩과 GUI 툴킷 | 있음(`WindowInfo.SetAsChild`, Qt, wx, GTK, Tk 예제) | **없음** |
| JavaScript와 Python의 통신 | 풍부함 | 제한적(메시지 라우터가 있음) |
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

## 맺음

용도가 갈립니다. cefpython은 **GUI 툴킷에 브라우저를 심고 Python과 JavaScript가 깊게 얽히는 응용**에, cefweaver는 **최신 CEF의 API를 넓게(그리고 헤더에 맞춰 정확하게) 쓰는 응용**에 맞습니다. cefweaver가 cefpython을 대체하려면 창 임베딩과 JS 바인딩의 확장이 가장 큰 일이고, 둘 다 java-cef에는 없는 범위(창 임베딩은 AWT에 맡김, JS는 메시지 라우터)입니다.

## 관련 페이지

- [java-cef 동등성](../reference/java-cef-parity.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
- [cefpython의 CEF 패치와 cefweaver](cefpython-patches.md)
