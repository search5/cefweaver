---
title: 메시지 라우터 (window.cefQuery)
type: reference
sources:
  - native/cefwrapper/query_router.h
  - native/cefwrapper/query_router.cc
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - tools/gen/handwritten.pyi
updated: 2026-10-08
---

# 메시지 라우터 (window.cefQuery)

페이지의 JavaScript가 호스트(Python)에 질의를 보내고 비동기로 응답을 받는 통로입니다. java-cef와 같이 CEF의 메시지 라우터(`include/wrapper/cef_message_router.h`)를 쓰며, 비교는 [분석](../analyses/js-python-messaging.md)에 있습니다. 기존 `add_javascript_binding`(기본형 인자, 반환값 없음)은 가벼운 호출용으로 그대로 있습니다.

## Python에서 쓰는 방법

```python
class Handler(cefweaver.QueryHandler):
    def on_query(self, browser, frame, query_id, request, persistent, callback):
        if request == "ping":
            callback.success("pong")          # 또는 callback.failure(7, "이유")
            return True                        # 질의를 받았다
        return False                           # 다음 핸들러에게

app = cefweaver.CefApp()
app.add_query_handler(Handler())               # initialize() 전에 하나 이상
app.initialize(url)
```

```javascript
window.cefQuery({request: "ping", persistent: false,
                 onSuccess: (response) => ..., onFailure: (code, message) => ...});
```

| 항목 | 동작 |
| --- | --- |
| `CefApp.add_query_handler(handler, first=False)` | 핸들러를 더합니다. 처음 더하는 것은 `initialize()` 전이어야 합니다(렌더러가 시작할 때 라우터를 만듭니다). 시작 뒤에는 라우터가 있을 때만 더할 수 있고 없으면 `RuntimeError`입니다. `QueryHandler`가 아니면 `TypeError`, 이미 더했으면 `ValueError`. 순서대로 물어보고 `first=True`이면 맨 앞에 둡니다. |
| `CefApp.remove_query_handler(handler) -> bool` | 뺍니다. 받아 둔 질의는 취소되어 `on_query_canceled()`가 불리고 페이지의 `onFailure`가 -1을 받습니다. 더한 적이 없으면 `False`. |
| `CefApp.set_query_functions(query="cefQuery", cancel="cefQueryCancel")` | JavaScript 함수 이름. `initialize()` 전에만(`RuntimeError`), `str`이 아니면 `TypeError`, 식별자가 아니면 `ValueError`. |
| `QueryHandler.on_query(browser, frame, query_id, request, persistent, callback) -> bool` | `request`는 `str`, 페이지가 `ArrayBuffer`를 보내면 `bytes`. `True`면 받은 것이고 `callback`으로 지금 또는 나중에(다른 스레드도 가능) 답해야 합니다. 어느 핸들러도 받지 않으면 페이지의 `onFailure`가 -1을 받습니다. 예외는 `sys.excepthook`으로 가고 "받지 않음"입니다. |
| `QueryHandler.on_query_canceled(browser, frame, query_id)` | 페이지가 `cefQueryCancel`을 불렀거나, 페이지를 떠났거나, 렌더러나 브라우저가 사라졌거나, 핸들러를 뺐을 때. |
| `QueryCallback.success(str 또는 bytes) -> bool` | `onSuccess`에 문자열(또는 `ArrayBuffer`)로 답합니다. 보냈으면 `True`. 한 번 답한 질의는 `False`(지속 질의는 계속 답할 수 있음). |
| `QueryCallback.failure(error_code, message="") -> bool` | `onFailure`로 답하고 질의를 닫습니다. |

콜백은 어느 스레드에서나 부를 수 있습니다. 답하지 않고 버린 콜백은 질의를 -1로 실패시킵니다(CEF는 열린 질의의 콜백이 소멸하는 것을 오류로 봅니다).

## 구현

- 손으로 쓴 중계입니다. `libcef_dll_wrapper`의 클래스가 `include/wrapper/`에 있어 생성기의 입력(`include`, `include/test`, `include/views`) 밖이기 때문입니다.
- `query_router.*`: `PythonQueryHandler`(CEF의 `Handler`를 구현해 Python으로 부름), `QueryCallbackHolder`(응답을 한 번만 보내고 소멸 때 실패시킴, 전역 재귀 뮤텍스로 다른 스레드의 응답과 취소를 직렬화), `QueryRouter`(프로세스 전역의 핸들러 목록과 브라우저 쪽 라우터). Python은 뮤텍스를 잡은 채로 부르지 않습니다.
- 브라우저 쪽: `CefWrapperClientHandler`가 `OnProcessMessageReceived`(라우터가 먼저), `OnBeforeClose`, `OnBeforeBrowse`, `OnRenderProcessTerminated`에서 라우터를 부릅니다. 뒤의 둘은 `CefRequestHandler` 구현이고, 라우터가 있을 때만 `GetRequestHandler()`가 이것을 돌려줍니다.
- 렌더러 쪽: `SimpleRenderProcessHandler`가 `OnContextCreated`, `OnContextReleased`, `OnProcessMessageReceived`에서 `CefMessageRouterRendererSide`를 부릅니다. 라우터는 명령줄 스위치 `cefweaver-query-function`, `cefweaver-cancel-function`이 있을 때 만듭니다.
- 스위치는 `CefWrapperBrowserProcessHandler::OnBeforeChildProcessLaunch`가 자식 프로세스의 명령줄에 붙입니다([실험으로 확인한 사실](verified-findings-api.md) F34). java-cef는 같은 설정을 브라우저를 만들 때 `extra_info`로 렌더러에 주고 `OnBrowserCreated`에서 라우터를 만드는데(`jcef_helper.cpp`), `extra_info`가 없는 브라우저(팝업 등)는 건너뜁니다. 명령줄 방식은 브라우저와 상관없이 모든 렌더러에 적용됩니다.

## 제약

- 요청과 응답은 문자열 또는 바이트입니다. 객체는 JSON으로 주고받습니다(변환은 호출하는 쪽).
- 핸들러 목록은 프로세스 전역입니다(CEF가 프로세스당 한 번만 시작되기 때문).
- 래퍼의 `CefRequestHandler`는 라우터만을 위한 것입니다. 사용자의 요청 핸들러는 아직 열리지 않았습니다.
- 여러 프레임과 `window.open`의 팝업 브라우저는 시험으로 확인했습니다([실험으로 확인한 사실](verified-findings-api.md) F35). 서로 다른 렌더러 프로세스에 있는 프레임(사이트 격리)은 확인하지 못했습니다. 교차 사이트 iframe이 로드되지 않았기 때문입니다(F37).
- `execute_javascript`, `load_url`, `is_ready_to_execute_javascript`는 처음 만든 브라우저에만 적용됩니다(팝업에는 쓸 수 없습니다).

## 관련 페이지

- [JavaScript와 호스트 사이의 통신 (java-cef, cefpython과 비교)](../analyses/js-python-messaging.md)
- [JavaScript 바인딩](../concepts/javascript-bindings.md)
- [Python API 참조](python-api.md)
- [C++ 핸들러](../components/native-handlers.md)
