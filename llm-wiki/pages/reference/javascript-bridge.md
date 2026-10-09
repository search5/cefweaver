---
title: JavascriptBridge (JSON으로 JavaScript와 Python을 잇는 계층)
type: reference
sources:
  - cefweaver/bridge.py
  - native/cefwrapper/bridge.h
  - native/cefwrapper/cef_wrapper_render_process_handler.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - tests/test_smoke.py
updated: 2026-10-08
---

# JavascriptBridge

cefpython의 `JavascriptBindings`(함수, 객체, 속성, 목록과 사전과 `None`, 반환값, `JavascriptCallback`)에 해당하는 기능입니다. cefpython은 렌더러 프로세스에 Python을 두지만, cefweaver는 **렌더러에 Python을 두지 않고** 이미 있는 메시지 라우터(`window.cefQuery`) 위에서 JSON을 주고받습니다. 근거와 검증은 [F65](verified-findings-handlers.md)에 있고, 기본형 인자만 받는 기존 `add_javascript_binding`은 [JavaScript 바인딩](../concepts/javascript-bindings.md)에 있습니다. java-cef에는 없는 범위입니다.

## 쓰는 방법

```python
bridge = cefweaver.JavascriptBridge(app, origins=["https://example.org/"])   # initialize() 전에
bridge.expose("add", lambda a, b: a + b)              # 페이지에서: await add(1, 2)  ->  3
bridge.expose("who", lambda frame, tag: ..., with_frame=True)   # 호출한 Frame을 먼저 받음
app.initialize(url)

bridge.execute_function(frame, "api.greet", "Ada", {"k": [1, None]})   # 페이지의 함수 호출, 결과는 안 받음
bridge.evaluate(frame, "double(21)", lambda value, error: ...)          # 식의 값(Promise는 기다림)
```

| 항목 | 설명 |
| --- | --- |
| `JavascriptBridge(app, origins=None)` | `app`은 아직 시작하지 않은 `CefApp`. `origins`(URL 접두사의 목록)를 주면 그 프레임의 호출만 받습니다. 기본은 모든 프레임이므로 바깥 페이지가 올라올 수 있으면 반드시 정합니다. 목록이 아니면 `TypeError` |
| `expose(name, function, with_frame=False)` | `window.<name>`을 만듭니다(`initialize()` 전에만). 이름은 JavaScript 식별자이고 예약어가 아니어야 하며 중복되면 `ValueError`. 함수의 예외는 `Promise`를 `유형: 메시지`로 거부합니다. JSON으로 만들 수 없는 반환값(`object()`, `NaN`)도 거부됩니다 |
| `execute_function(frame, path, *args)` | `window`에서 시작하는 경로(`"a.b.c"`)의 함수를 JSON 인자로 부릅니다 |
| `evaluate(frame, expression, callback)` | 식을 실행하고 나중에 `callback(value, error)`를 `do_message_loop_work()` 안에서 부릅니다. 실패하면 `value`는 `None`이고 `error`는 `SyntaxError: ...` 같은 문자열 |
| `JsCallback` | 페이지의 함수를 인자로 주면 Python이 받는 객체. `call(*args)`는 그 함수를 원래 프레임에서 JSON 인자로 부르고, `release()`는 페이지가 잊게 합니다 |

## 동작

1. `expose`가 이름을 JSON 배열로 `CefApp._set_bridge_names`에 넘기고, 브라우저 프로세스가 자식 프로세스의 명령줄에 `--cefweaver-bridge=[...]`를 붙입니다(`OnBeforeChildProcessLaunch`).
2. 각 렌더러 프로세스의 `OnContextCreated`가 라우터 뒤에서 고정된 JavaScript 조각(`native/cefwrapper/bridge.h`의 `kBridgeShim`)을 실행해 `window.<name>`과 `window.__cefweaverBridge`를 정의합니다. 페이지의 스크립트보다 먼저이고, iframe도 같습니다. 렌더러에서 도는 Python은 없습니다.
3. `window.add(1, 2)`는 `cefQuery({request: '{"cefweaver":1,"t":"call","n":"add","a":[1,2]}'})`를 보내고 `Promise`를 돌려줍니다. 브라우저 프로세스의 `JavascriptBridge`의 질의 핸들러(`first=True`로 추가됨)가 JSON을 풀어 함수를 부르고 결과를 JSON으로 답합니다. `{"cefweaver":1`로 시작하지 않는 질의는 `False`로 넘겨 응용 자신의 `QueryHandler`가 받습니다.
4. 함수 인자는 `{"__cb": 아이디}`로 바뀌어 가고 Python에서는 `JsCallback`이 됩니다. `call`은 `execute_java_script`로 `window.__cefweaverBridge.invoke`를 부릅니다.
5. `evaluate`의 결과는 페이지가 `{"t":"result"}` 질의로 돌려주고, 대기 중인 `callback`이 불립니다.

## 한계

- 함수 인자는 **최상위만** `JsCallback`이 됩니다(목록이나 사전 안의 함수는 아님).
- 함수는 **동기**로 실행됩니다. 오래 걸리는 일은 메시지 루프를 막으므로 스레드로 넘기고 `JsCallback`으로 알리십시오.
- `expose`는 `initialize()` 전에만 됩니다(렌더러가 시작할 때 이름을 받음).
- 값은 JSON입니다. `undefined`는 `null`, `Date`나 `Map` 같은 것은 JSON이 만드는 모양이 됩니다. 정수는 `float`이 될 수 있는 JavaScript의 수 규칙을 따릅니다.
- cefpython의 객체와 속성 바인딩(`SetObject`, `SetProperty`)과 `JavascriptCallback.GetFrame`은 없습니다. 함수 하나씩 노출합니다.

## 관련 페이지

- [JavaScript 바인딩](../concepts/javascript-bindings.md)
- [메시지 라우터](message-router.md)
- [cefpython과 cefweaver의 API 차이](../analyses/cefpython-comparison.md)
