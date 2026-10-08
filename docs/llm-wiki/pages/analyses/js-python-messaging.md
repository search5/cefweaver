---
title: JavaScript와 호스트 사이의 통신 (java-cef, cefpython과 비교)
type: analysis
sources:
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/javascript_binding.h
  - tools/gen/typesys.py
updated: 2026-10-08
---

# JavaScript와 호스트 사이의 통신 (java-cef, cefpython과 비교)

프로세스 메시지를 열면서 "구조화된 양방향 통신(객체, 반환값)은 어떻게 하는가"를 java-cef와 cefpython의 위키(`/home/jiho/cef_framework/java-cef/docs/llm-wiki/`, `/home/jiho/cef_framework/cefpython/docs/llm-wiki/`)와 CEF 헤더로 조사한 결과입니다. 아무것도 구현하지 않았고, 선택지와 의견을 적습니다.

## 공통점: 호스트 언어는 브라우저 프로세스에만 있고, 렌더러는 C++입니다

세 프로젝트 모두 렌더러 프로세스에서 JavaScript와 만나는 코드가 C++입니다. 차이는 그 C++ 중계가 무엇을 하느냐입니다.

| | java-cef | cefpython | cefweaver (지금) |
| --- | --- | --- | --- |
| JavaScript → 호스트 | CEF의 **메시지 라우터**: `window.cefQuery({request, persistent, onSuccess, onFailure})` | `JavascriptBindings`로 함수, 객체의 메서드, 속성을 `window`에 바인딩. 인자는 `CefListValue`로 바뀜 | `window.<이름>(...)`. 인자는 정수, 불리언, 실수, 문자열 |
| 인자로 넘길 수 있는 것 | 요청은 **문자열**(관례상 JSON) | 리스트, 딕셔너리, 숫자, 불리언, null, 문자열, **JavaScript 콜백, Python 콜백** | 위의 기본형 4종 |
| 반환값 | 비동기 응답: `callback.success(문자열 또는 바이트)` / `failure(코드, 메시지)`, 질의 번호, 취소, 지속 질의(구독) | 비동기: 콜백을 인자로 넘기고, Python은 `JavascriptCallback.Call()`로 부름 | 없음 |
| 호스트 → JavaScript | `executeJavaScript` | `Frame.ExecuteFunction`, `JavascriptCallback.Call` | `execute_javascript(코드)` |
| 렌더러 쪽 구현 | `CefMessageRouterRendererSide`(`jcef_helper`) | 직접 만든 V8 중계(`cefpython_app.cpp`, `v8function_handler.cpp`) | `SimpleRenderProcessHandler` |
| 프로세스 메시지 이름 | 라우터의 것 + `AddMessageRouter`/`RemoveMessageRouter` | `DoJavascriptBindings`, `ExecuteJavascriptCallback`, `ExecutePythonCallback`, `OnContextReleased` | `javascript-binding`, `javascript-python-binding`(+ 진단용 `cefweaver-ping`/`pong`) |

cefpython의 설명에 따르면 CEF 3에서 JavaScript와 Python 사이의 통신은 프로세스 간 메시징이라 **항상 비동기**이고, 값을 돌려받으려면 콜백을 씁니다. java-cef도 응답을 콜백으로 줍니다. 즉 "함수 호출이 값을 반환한다"는 형태는 어느 쪽에도 없습니다.

## cefweaver가 취할 수 있는 길

### A. CEF의 메시지 라우터 (java-cef 방식)

`include/wrapper/cef_message_router.h`는 `libcef_dll_wrapper`에 들어 있고 우리가 이미 링크합니다. 렌더러에 `CefMessageRouterRendererSide`, 브라우저에 `CefMessageRouterBrowserSide`를 두고 CEF의 이벤트(`OnContextCreated`, `OnContextReleased`, `OnProcessMessageReceived`, `OnBeforeBrowse`, `OnRenderProcessTerminated`)를 전달하는 방식입니다.

- Python 쪽 API는 `on_query(browser, frame, query_id, request, persistent, callback)`와 `callback.success(str)`, `callback.failure(code, message)`, `on_query_canceled`가 됩니다. 헤더에는 바이트 응답(`Success(const void*, size_t)`)도 있습니다.
- 장점: CEF가 만들고 시험하는 코드이고, 질의 번호, 취소, 지속 질의(구독), 브라우저가 닫힐 때의 정리를 맡습니다. 구조가 단순합니다.
- 한계: 요청과 응답이 문자열입니다(JSON을 쓰면 객체를 보낼 수 있고 변환은 호출하는 쪽이 합니다).
- 구현: 이 클래스는 `include/wrapper/`에 있어서 생성기의 입력(`include`, `include/test`, `include/views`)이 아니므로 **손으로 쓴 중계**가 됩니다. java-cef도 `message_router_handler.cpp`를 손으로 썼습니다. 렌더러 쪽 설정(`js_query_function`)을 새 브라우저와 기존 브라우저에 전달하는 일도 java-cef와 같이 필요합니다.

### B. cefpython 방식의 풍부한 중계

JavaScript 값과 `CefListValue` 사이의 변환, JavaScript 콜백과 Python 콜백의 수명 관리(브라우저나 프레임이 닫힐 때의 정리 포함)를 렌더러에 직접 만드는 방식입니다. 표현력은 가장 크지만 가장 큰 작업이고 수명 문제가 어렵다는 것을 cefpython의 코드(`RemovePythonCallbacksForFrame` 등)가 보여 줍니다.

### C. 지금의 바인딩을 넓히기

기본형 인자에 JSON 문자열이나 배열을 더하고 콜백 하나를 허용하는 정도의 점진적 확장입니다. 작지만 지속 질의나 취소가 없어서 결국 A와 겹칩니다.

**의견과 결정**: A가 비용 대비 효과가 가장 큽니다. 객체는 JSON 문자열로 보내면 되고, 반환값은 `success`/`failure`로 돌려받고, 구독(`persistent`)과 취소와 정리를 CEF가 맡습니다. 지금의 `add_javascript_binding`은 그대로 두어 가벼운 호출에 씁니다. 사용자가 A(java-cef 방식)를 골라 구현했습니다: [메시지 라우터](../reference/message-router.md).

## 열지 못한 부분

프로세스 메시지를 열면서 열지 못한 것들입니다.

| 항목 | 이유 | java-cef, cefpython | 가능한 방법 |
| --- | --- | --- | --- |
| `BinaryValue.create(data, size)` | `const void*`와 크기 쌍을 라이브러리 메서드가 받음(지금 생성기는 클라이언트 쪽의 쓰기 가능한 쌍만 지원) | java-cef는 `ByteBuffer`를 `CefBinaryValue`로 바꾸는 변환을 가짐(`GetCefValueFromJNIObject`). cefpython은 콜백 id를 `CefBinaryValue`에 담아 전달 | 읽기용 버퍼 종류를 더해 `bytes`와 `memoryview` 같은 버퍼 객체를 받음 |
| `BinaryValue.get_data(buffer, size, offset)` | 호출하는 쪽의 버퍼를 CEF가 채움 | 위와 같음 | `get_data(size, offset) -> bytes`로 바꿔서 돌려줌 |
| `BinaryValue.get_raw_data()` | CEF가 가진 메모리를 가리키는 `const void*`, 크기는 `get_size()` | | 객체의 수명을 넘어서 쓰면 위험해서 열지 않고 `get_data`로 복사해 `bytes`를 줌 |
| `ProcessMessage.get_shared_memory_region()` | `CefSharedMemoryRegion`(`Memory()`가 `void*`, `Size()`)이 범위 밖. 지금 렌더러가 공유 메모리 메시지를 만들지 않음 | 둘 다 쓰지 않음 | 보내는 쪽이 생길 때까지 닫아 둠 |

**읽기용 버퍼 종류는 오프스크린 렌더링의 선행 작업과 같은 것입니다.** `CefRenderHandler::OnPaint(browser, type, dirty_rects, const void* buffer, int width, int height)`의 `buffer`는 `BinaryValue.create`와 같은 `const void*`이지만 크기가 인자로 오지 않고 `width * height * 4`입니다(헤더 주석). java-cef는 `NewDirectByteBuffer(buffer, width * height * 4)`로, cefpython은 `PaintBuffer`(`GetString()`, `GetIntPointer()`)로 풉니다. 생성기에서는 "포인터와 명시적인 크기 쌍"(`BinaryValue.create`)과 "메서드마다 정하는 크기 규칙"(`OnPaint`)을 하나의 읽기용 버퍼 종류로 풀 수 있습니다.

## 관련 페이지

- [메시지 라우터 (구현)](../reference/message-router.md)
- [래퍼와 사용자가 핸들러를 나눠 쓰는 방법](sharing-handlers-with-the-wrapper.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
- [Python API 참조](../reference/python-api.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
