---
title: JavaScript 바인딩
type: concept
sources:
  - cefweaver/_cefweaver.pyx
  - native/cefwrapper/javascript_binding.h
  - native/cefwrapper/javascript_python_binding_handler.h
  - native/cefwrapper/javascript_bindings_handler.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - tests/test_smoke.py
updated: 2026-10-08
---

# JavaScript 바인딩

`CefApp.add_javascript_binding(name, callback)`는 페이지에 전역 함수 `window.<name>(...)`을 만들고, 호출하면 `callback(*args)`를 실행합니다. `initialize()` 전에만 등록할 수 있습니다.

```python
app.add_javascript_binding("report", lambda key, *values: print(key, values))
```

## 동작 흐름

두 프로세스를 거치므로 단계가 많습니다.

1. **등록(Python)**: `callback`을 `CefApp._callbacks` 목록에 보관하고(C++이 원시 포인터만 쥐므로 수명 유지용) `AddJavascriptPythonBinding(name, _dispatch, <void*>callback)`을 부릅니다.
2. **브라우저 생성(브라우저 프로세스)**: `OnContextInitialized()`가 바인딩 **이름 목록**만 `CefListValue`에 담아 `extra_info`의 `JSNativePythonApiNames`로 브라우저에 붙입니다.
3. **렌더러에서 함수 정의**: `SimpleRenderProcessHandler::OnBrowserCreated()`가 이름 목록을 읽고, `OnContextCreated()`가 V8 컨텍스트의 전역 객체에 이름마다 함수를 만듭니다.
4. **JS 호출(렌더러)**: `JavascriptPythonBindingsHandler::Execute()`가 인자를 `int`, `bool`, `double`, `string` 네 종류만 골라 담아 프로세스 메시지 `javascript-python-binding`을 브라우저 프로세스로 보냅니다. 메시지의 인자 목록은 `[이름, 타입 목록, 값 목록]`입니다.
5. **수신(브라우저 프로세스, UI 스레드)**: `CefWrapperClientHandler::OnProcessMessageReceived()`가 `CefValueWrapper` 배열로 풀어 이름이 같은 바인딩의 핸들러 함수를 부릅니다.
6. **Python 콜백**: Cython의 `_dispatch`(`noexcept with gil`)가 값을 Python 객체로 바꿔 `callback(*args)`를 부릅니다.

콜백은 `do_message_loop_work()` 안에서 UI 스레드(Python 스레드)에서 실행됩니다. 콜백이 예외를 일으켜도 `sys.excepthook`으로 보고될 뿐 CEF로 전파되지 않고, 이후 호출은 계속 동작합니다(시험으로 확인).

## 값 변환

| JavaScript | `CefValueWrapper.Type` | Python |
| --- | --- | --- |
| 정수로 표현되는 숫자(`IsInt`) | 0 | `int` |
| 불리언 | 1 | `bool` |
| 그 밖의 숫자(`IsDouble`) | 2 | `float` |
| 문자열 | 3 | `str`(UTF-8, 깨진 바이트는 대체 문자) |
| 그 밖의 종류(`undefined`, 객체, 배열 등) | 렌더러가 건너뜀 | 전달되지 않음 |

렌더러가 지원하지 않는 종류의 인자를 건너뛰므로 JS에서 넘긴 인자 수와 Python이 받는 인자 수가 다를 수 있습니다. 반환값은 지원하지 않습니다. JS 함수는 항상 `undefined`를 돌려주고, Python 콜백의 반환값은 버려집니다. 인자가 없는 호출(`noargs()`)은 `callback()`으로 전달됩니다.

`CefValueWrapper`의 필드는 기본값(`Type = -1` 등)으로 초기화되어 있어서 알 수 없는 종류가 섞여도 `None`으로 변환됩니다.

## 이름만 보내는 이유

초기 구현은 `JavascriptPythonBinding` 객체 배열을 `CefBinaryValue`로 만들어 렌더러 프로세스에 그대로 복사했습니다. 이 객체는 `std::string`과 함수 포인터를 품고 있어서 다른 프로세스에서는 유효하지 않은 주소를 가리키므로, JS 콜백이 전혀 동작하지 않았습니다. 렌더러는 이름만 필요하고 호출은 브라우저 프로세스가 처리하므로 이름 목록만 보내도록 바꿨습니다([설계 결정 기록](../reference/design-decisions.md)).

## 인자 없는 C++ 바인딩 (Python 미노출)

C++에는 함수 포인터 `void()`를 받는 `AddJavascriptBinding`과 메시지 `javascript-binding` 경로(`javascript_bindings_handler.h`)가 따로 있습니다. 함수 포인터에 Python 객체를 실을 수 없어서 Python API에는 노출하지 않았습니다. 인자 없는 호출은 위의 Python 바인딩이 이미 지원합니다.

## 자식 프레임과 렌더러 프로세스

렌더러 쪽 핸들러(`javascript_bindings_handler.h`, `javascript_python_binding_handler.h`)는 호출을 **호출한 프레임**에서 브라우저 프로세스로 보냅니다(`CefV8Context::GetCurrentContext()->GetFrame()`). 교차 사이트 iframe은 다른 렌더러 프로세스에 있고, 그 프로세스에서는 메인 프레임이 원격 프레임이라 `browser->GetMainFrame()`이 널이므로 메인 프레임으로 보내면 렌더러가 죽습니다(F57, [검증](../reference/verified-findings-handlers.md)). 컨텍스트에서 프레임을 얻지 못할 때만 메인 프레임으로 되돌아갑니다.

## 더 풍부한 통신

목록, 사전, `None`, 반환값(`Promise`), 페이지 함수의 콜백이 필요하면 [JavascriptBridge](../reference/javascript-bridge.md)를 씁니다. 렌더러에 Python을 두지 않고 메시지 라우터 위의 JSON으로 합니다.

## 관련 페이지

- [프로세스 모델과 스레드](process-model-and-threads.md)
- [C++ 핸들러](../components/native-handlers.md)
- [사용하지 않는 코드와 유산](../components/legacy-code.md)
- [Python API 참조](../reference/python-api.md)
