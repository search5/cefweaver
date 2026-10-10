---
title: 수명 주기와 메시지 루프
type: concept
sources:
  - native/cefwrapper/library.cpp
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - cefweaver/_cefweaver.pyx
  - tests/test_smoke.py
updated: 2026-10-10
---

# 수명 주기와 메시지 루프

Python에서 보이는 흐름은 `CefApp()` 생성, 설정, `initialize()`, `do_message_loop_work()` 반복, `shutdown()`입니다.

```python
app = cefweaver.CefApp()
app.add_javascript_binding("hello", print)
app.initialize("https://example.com")
while app.is_running:
    app.do_message_loop_work()
app.shutdown()
```

## 설정 단계 (initialize 전)

`set_subprocess_path`, `set_cache_path`, `set_resources_path`, `add_command_line_switch`, `add_javascript_binding`은 `initialize()` 전에만 부를 수 있습니다. 이후에 부르면 `RuntimeError("this must be done before initialize()")`가 납니다(`_require_not_initialized`). 값은 `CefWrapper`(C++)의 멤버에 모였다가 초기화 때 한꺼번에 쓰입니다.

## initialize()

`CefWrapper::InitCefSimple()`(`native/cefwrapper/library.cpp`)가 이 순서로 실행합니다.

1. Windows에서만 `CefEnableHighDPISupport()`를 호출합니다.
2. Linux에서는 `argv = {"cefweaver"}`로 `CefMainArgs`를 만듭니다. 내장된 인터프리터에는 의미 있는 argc, argv가 없기 때문입니다.
3. 바인딩과 시작 URL을 가진 `CefWrapperApp`을 만들고 모아 둔 명령줄 스위치를 넘깁니다.
4. `CefExecuteProcess()`를 호출합니다. 브라우저 프로세스에서는 -1을 돌려주며 반환값은 쓰지 않습니다.
5. `CefSettings`를 채웁니다. 캐시 경로(`cache_path`와 `root_cache_path`)는 지정값 또는 `현재 디렉터리/cache`, `no_sandbox = true`, 선택적 리소스 경로, 서브프로세스 경로입니다.
6. `CefInitialize()`를 호출합니다. 실패하면 `CefApp`을 비우고 `false`를 돌려주어 Python에서 `RuntimeError("CefInitialize() failed")`가 됩니다. 성공하면 전역 플래그 `g_IsRunning`을 `true`로 둡니다.

브라우저는 `CefWrapperBrowserProcessHandler::OnContextInitialized()`에서 `CreateBrowserSync()`로 만들어지고 `Browser` 멤버에 저장됩니다. 시험에서 `initialize()` 직후 메시지 루프를 한 번도 돌리지 않았는데 `load_url()`이 `True`를 돌려주었으므로, 관찰된 바로는 브라우저가 `initialize()` 안에서 이미 만들어집니다. 이것이 CEF의 보장인지는 확인하지 않았습니다. 창은 Linux에서 부모 없이 최상위 창으로 만들어지고, Windows에서는 `SetAsPopup`을 씁니다.

첫 브라우저는 `initialize()` 안에서 만들어지므로 `LifeSpanHandler.on_after_created`는 `initialize()`가 끝나기 전에 불립니다. 그 안에서도 `add_resource`, `load_url` 같은 `CefApp` 메서드를 쓸 수 있습니다([F67](../reference/verified-findings-handlers.md)). `execute_javascript`는 페이지가 아직 없어 `False`를 돌려줍니다.

## 메시지 루프와 상태

`do_message_loop_work()`는 `CefDoMessageLoopWork()`를 한 번 실행합니다. 호출하지 않으면 CEF가 아무것도 처리하지 못합니다.

| 속성 | 의미 |
| --- | --- |
| `is_running` | `initialize()`를 마쳤고, `shutdown()` 전이며, `g_IsRunning`이 켜져 있으면 `True`입니다. |
| `is_ready_to_execute_javascript` | 페이지 로딩이 끝나 JS를 실행할 수 있으면 `True`입니다(`OnLoadingStateChange`가 로딩 중이면 끄고 끝나면 켭니다). |

`g_IsRunning`은 `CefWrapperClientHandler::OnBeforeClose()`에서도 꺼집니다. 그래서 **사용자가 창을 닫으면 `is_running`이 `False`가 되어** 위 루프가 끝납니다. 창 관리자가 없는 가상 X 서버에서 닫기 요청(`WM_DELETE_WINDOW`)을 직접 보내 확인했고, 요청 약 4초 뒤 루프가 끝났습니다(이 시험은 `python-xlib`가 필요해서 저장소의 `tests/`에는 없습니다).

`execute_javascript()`와 `load_url()`은 준비되지 않았을 때 예외 대신 `False`를 돌려줍니다. `initialize()` 전, 또는 `shutdown()` 뒤에 부르면 `RuntimeError`입니다.

### CEF가 창을 소유하면 폴링이어야 한다 (Views)

`MessagePump`(`external_message_pump`)는 툴킷이 창과 이벤트 루프를 소유하는 오프스크린 어댑터를 위한 것입니다. **CEF가 자기 창을 소유하는 경우**(Views의 `Window`)에는 외부 펌프로 돌리면 그려지고 레이아웃도 되지만 **창의 X11 마우스와 키 입력이 처리되지 않았습니다**. `do_message_loop_work()`를 자주 부르는 폴링으로 바꾸면 입력이 옵니다([F97](../reference/verified-findings-views.md)). 또 `initialize(None)`은 첫 브라우저 없이 시작하고 `is_running`은 `shutdown()`까지 `True`이며, **창이 열린 채로 `shutdown()`을 부르면 죽으므로** `on_window_destroyed`를 받은 뒤에 부릅니다.

## shutdown()

`CefWrapper::ShutdownCefSimple()`이 실행하는 순서입니다.

1. 클라이언트 핸들러가 있으면 `CloseAllBrowsers(true)`를 호출하고, 브라우저 목록이 빌 때까지 최대 500번(10밀리초 간격, 약 5초) `CefDoMessageLoopWork()`를 돕니다.
2. `Browser` 참조를 비웁니다.
3. `CefShutdown()`을 호출하고 `CefApp`을 비우고 `g_IsRunning`을 끕니다.

브라우저를 닫고 참조를 놓기 전에 `CefShutdown()`을 호출하면 세그멘테이션 오류가 났습니다. 이 순서는 그 오류를 고친 결과입니다.

`shutdown()`을 부르지 않고 `CefApp` 객체가 사라지면, 실행 중인 CEF의 `CefApp`이 `CefShutdown()`보다 오래 살아야 하므로 C++ 객체를 삭제하지 않고 의도적으로 남겨 둡니다(`__dealloc__`). `shutdown()`은 여러 번 불러도 안전합니다.

## 한 프로세스에 한 번

`CefApp` 문서는 프로세스당 한 번만 초기화할 수 있다고 적습니다. 시험도 이 때문에 CEF를 띄우는 시험마다 새 프로세스에서 실행합니다([시험](../components/tests.md)). `shutdown()` 뒤에 다시 `initialize()`를 시도하면 세그멘테이션 오류가 나서(F20) 지금은 `RuntimeError`로 막습니다.

## 관련 페이지

- [프로세스 모델과 스레드](process-model-and-threads.md)
- [C++ 핸들러](../components/native-handlers.md)
- [CefWrapper 클래스](../components/native-library-api.md)
- [Python API 참조](../reference/python-api.md)
