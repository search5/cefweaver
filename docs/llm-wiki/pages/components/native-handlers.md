---
title: C++ 핸들러
type: component
sources:
  - native/cefwrapper/cef_wrapper_app.h
  - native/cefwrapper/cef_wrapper_app.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.h
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler.h
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler_linux.cc
  - native/cefwrapper/cef_wrapper_client_handler_win.cc
  - native/cefwrapper/cef_wrapper_render_process_handler.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - native/cefwrapper/javascript_binding.h
  - native/cefwrapper/javascript_python_binding_handler.h
  - native/cefwrapper/javascript_bindings_handler.h
updated: 2026-10-08
---

# C++ 핸들러

`native/cefwrapper/`의 손으로 쓴 CEF 핸들러들입니다. 원래 cef-wrapper 예제에서 가져온 구조입니다. 래퍼가 스스로 해야 하는 일(브라우저 목록, 준비 플래그, 오류 페이지, 창 제목, JavaScript 바인딩, 컨텍스트 메뉴)은 이 클래스들에 고정되어 있고, **표시, 수명 주기, 로드 이벤트는 사용자의 `Client`로 위임**됩니다(`CefApp.set_client()`, 아래 `CefWrapperClientHandler`와 [핸들러 프록시 구조](../concepts/handler-proxies.md)).

## CefWrapperApp (`cef_wrapper_app.*`)

`CefApp`을 구현합니다. 브라우저 프로세스와 서브프로세스 모두에서 쓰입니다.

- `GetBrowserProcessHandler()`는 `CefWrapperBrowserProcessHandler`의 싱글턴, `GetRenderProcessHandler()`는 `SimpleRenderProcessHandler`의 싱글턴을 돌려줍니다.
- 생성자가 바인딩 목록을 두 핸들러의 정적 설정 함수로 넘기고 시작 URL을 기록합니다.
- `OnBeforeCommandLineProcessing()`은 프로세스 종류가 비어 있을 때(브라우저 프로세스)만 `AddCommandLineSwitch()`로 모은 스위치를 적용합니다. 자식 프로세스는 브라우저 프로세스의 명령줄을 물려받습니다.
- `OnRegisterCustomSchemes()`의 사용자 지정 스킴 등록 줄은 주석 처리되어 있습니다.
- `LoadUrl()`은 호출하는 곳이 없습니다([사용하지 않는 코드와 유산](legacy-code.md)).

## CefWrapperBrowserProcessHandler

- `OnContextInitialized()`(UI 스레드): 클라이언트 핸들러를 만들고, 렌더러 핸들러에 바인딩을 알리고, 바인딩 **이름 목록**을 `extra_info`에 담아 `CefBrowserHost::CreateBrowserSync()`로 브라우저를 만들어 `Browser` 멤버에 저장합니다. Windows에서는 `SetAsPopup`을 씁니다.
- 브라우저는 **Alloy 스타일**로 만듭니다(`window_info.runtime_style = CEF_RUNTIME_STYLE_ALLOY`). java-cef와 같은 설정이며 이유는 [설계 결정 기록](../reference/design-decisions.md)에 있습니다.
- `GetDefaultClient()`는 클라이언트 핸들러를 돌려줍니다.
- 싱글턴(`GetInstance()`)입니다.

## CefWrapperClientHandler

`CefClient`, `CefContextMenuHandler`와, 표시, 수명 주기, 로드 핸들러의 **생성된 전달 클래스**(`CwDisplayHandlerForward`, `CwLifeSpanHandlerForward`, `CwLoadHandlerForward`)를 한 클래스에서 구현합니다. 인스턴스는 전역 `g_instance`로 접근합니다(`GetInstance()`).

생성자는 사용자의 클라이언트(`user_client`, 생성된 `CwClientProxy`)를 선택 인자로 받습니다. `GetDisplayHandler()`, `GetLifeSpanHandler()`, `GetLoadHandler()`는 CEF가 물을 때마다 `user_client->GetXxxHandler()`를 불러 그 결과를 전달 대상(`forward_..._handler_`)에 넣고 자기 자신을 돌려줍니다. 사용자의 클라이언트가 없으면 전달 대상이 비어 있어서 전달 클래스가 CEF 기반 클래스의 동작을 합니다. 컨텍스트 메뉴 핸들러와 `OnProcessMessageReceived`는 생성 범위 밖이라 위임하지 않습니다.

래퍼의 일과 사용자 핸들러의 호출 순서는 다음과 같습니다.

| 이벤트 | 순서 |
| --- | --- |
| `OnAfterCreated` | 래퍼(브라우저 목록에 추가), 그다음 사용자 |
| `DoClose` | 사용자 먼저. `true`를 돌려주면 닫기를 막고 래퍼는 아무것도 하지 않습니다. 아니면 래퍼가 처리하고 `false`. Alloy 스타일 브라우저에서만 호출되며 닫기를 막는 것을 시험으로 확인했습니다([실험으로 확인한 사실](../reference/verified-findings-api.md) F18). |
| `OnBeforeClose` | 사용자 먼저(브라우저가 아직 목록에 있음), 그다음 래퍼(목록에서 제거) |
| `OnLoadStart`, `OnLoadingStateChange`, `OnLoadEnd`, `OnTitleChange` | 래퍼, 그다음 사용자 |
| `OnLoadError` | 사용자 먼저, 그다음 래퍼(오류 페이지로 교체) |
| 그 밖의 표시, 수명 주기 이벤트 | 전달 클래스가 사용자에게 곧바로 전달 |

| 콜백 | 동작 |
| --- | --- |
| `OnAfterCreated` / `OnBeforeClose` | 브라우저 목록(`browser_list_`)을 관리합니다. `OnBeforeClose`는 `g_IsRunning`을 끄고 목록이 비면 `CefQuitMessageLoop()`을 부릅니다(외부 펌프에서는 효과가 없습니다). |
| `DoClose` | 마지막 브라우저이면 `is_closing_`을 켜고 닫기를 허용합니다. |
| `OnLoadStart` / `OnLoadingStateChange` | 준비 플래그 `m_IsReadyToExecuteJs`를 로딩 중에는 끄고 끝나면 켭니다(초기값은 `false`). |
| `OnLoadEnd` | 페이지에서 `window.dispatchEvent(new Event('cefready'))`를 실행합니다. 페이지가 `addEventListener('cefready', ...)`로 로드 완료를 알 수 있습니다. |
| `OnLoadError` | 오류가 `ERR_ABORTED`가 아니면 오류 내용을 담은 `data:` URI 페이지를 보여 줍니다(Chrome 런타임이 아닐 때). |
| `OnTitleChange` | `PlatformTitleChange`를 부릅니다. Windows 구현(`cef_wrapper_client_handler_win.cc`)은 `SetWindowText`로 창 제목을 바꿉니다. **Linux 구현(`..._linux.cc`)은 X11로** `_NET_WM_NAME`과 `WM_NAME`을 최상위 창에 설정합니다(`cef_get_xdisplay()`, `GetWindowHandle()`에서 `XQueryTree`로 루트의 자식까지 올라감). Alloy 스타일 창은 제목이 없어서 필요하고, `libX11`을 링크합니다. |
| `OnProcessMessageReceived` | 렌더러가 보낸 `javascript-python-binding`, `javascript-binding` 메시지를 풀어 등록된 핸들러를 부릅니다([JavaScript 바인딩](../concepts/javascript-bindings.md)). |
| 컨텍스트 메뉴 | "Show DevTools", "Close DevTools", "Inspect Element" 항목을 추가하고 `ShowDevTools`/`CloseDevTools`를 구현합니다. |

`CloseAllBrowsers(bool force_close)`는 UI 스레드가 아니면 작업을 UI 스레드에 게시합니다. `IsChromeRuntimeEnabled()`는 명령줄 스위치 `enable-chrome-runtime`를 확인합니다. `HasOpenBrowsers()`는 종료 과정에서 브라우저가 다 닫혔는지 확인하는 용도로 추가했습니다.

## SimpleRenderProcessHandler (`cef_wrapper_render_process_handler.*`)

렌더러 프로세스에서 실행되는 `CefRenderProcessHandler`입니다.

- `OnBrowserCreated()`: `extra_info`가 널이 아니면 `JSCallbackNames`, `JSNativePythonApiNames` 목록에서 바인딩을 이름만으로 다시 만듭니다. 널이면 아무것도 하지 않습니다(이 wrapper가 만들지 않은 브라우저).
- `OnContextCreated()`: V8 전역 객체에 바인딩 이름마다 함수를 만들고, 호출을 `JavascriptPythonBindingsHandler`(또는 인자 없는 `JavascriptBindingsHandler`)가 받습니다.

## 바인딩 자료형 (`javascript_binding.h`)

- `CefValueWrapper`: JS 값을 담는 구조(`Type`, `IntValue`, `BoolValue`, `DoubleValue`, `StringValue`). 필드는 모두 기본값으로 초기화됩니다.
- `JavascriptPythonBinding`: `HandlerFunction`, `MessageTopic`(이름), `PythonCallbackObject`. `CallHandler(argsSize, args)`로 호출합니다.
- `JavascriptBinding`: 인자 없는 바인딩(`functionName`, `function`).

## 관련 페이지

- [CefWrapper 클래스](native-library-api.md)
- [cefsubprocess 실행 파일](native-cefsubprocess.md)
- [프로세스 모델과 스레드](../concepts/process-model-and-threads.md)
- [사용하지 않는 코드와 유산](legacy-code.md)
