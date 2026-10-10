---
title: 핸들러와 이벤트
---

# 핸들러와 이벤트

CEF가 알려 주는 이벤트와 시작 훅 가운데, 시험으로 확인한 것을 모았습니다. 시그니처의 전체는 `cefweaver/_cefweaver.pyi`에 있습니다. 확인한 환경은 Linux x86_64, CEF 154입니다.

## 렌더러 프로세스의 사건

렌더러는 C++이라서 Python 코드를 렌더러에서 실행할 수는 없습니다. 대신 `enable_renderer_events()`를 켜면 렌더러가 사건을 브라우저 프로세스로 알려 주고, `RendererEvents`가 이를 풀어 Python 메서드를 부릅니다.

```python
class Events(cefweaver.RendererEventHandler):
    def on_uncaught_exception(self, browser, frame, exception):      # 잡히지 않은 JavaScript 오류
        print(exception.message, exception.script_name, exception.line, exception.stack[0].function_name)
    def on_focused_node_changed(self, browser, frame, node):         # 초점이 간 노드(없으면 None)
        print(node and (node.tag, node.editable, node.bounds))
    def on_context_created(self, browser, frame, is_main, url): ...
    def on_context_released(self, browser, frame, is_main, url): ...

decoder = cefweaver.RendererEvents(Events())
# 클라이언트의 on_process_message_received에서 decoder.on_process_message_received(...)를 부릅니다
app.enable_renderer_events()                                         # initialize() 전에만
```

- 켜지 않으면 렌더러는 아무것도 보내지 않습니다.
- 메인 프레임이 다른 페이지로 이동할 때는 이전 컨텍스트의 해제 알림이 오지 않았습니다(iframe을 없앴을 때는 옵니다).

## 시작 훅 (`AppHandler`)

```python
class Hooks(cefweaver.AppHandler):
    def on_before_child_process_launch(self, command_line):          # 렌더러, GPU 등을 시작하기 전
        print(command_line.get_switch_value("type"))
    def on_register_custom_preferences(self, type, registrar):       # 전역과 요청 컨텍스트마다 한 번씩
        registrar.add_preference("myapp.greeting", value)            # value: cefweaver.Value, 이 호출 안에서만 유효

app.set_app_handler(Hooks())                                         # initialize() 전에만
```

등록한 환경설정은 `request_context.has_preference()`, `get_preference()`, `set_preference()`로 읽고 바꿉니다.

## 클라이언트가 돌려주는 핸들러

| 핸들러 | 받는 것 |
| --- | --- |
| `FindHandler` | `browser.get_host().find(...)`의 결과(`on_find_result`). 첫 결과의 서수는 0입니다 |
| `FrameHandler` | 프레임이 생기고 사라지는 것과 메인 프레임의 교체 |
| `AccessibilityHandler` | `set_accessibility_state(ENABLED)` 뒤의 접근성 트리 |
| `RequestHandler.on_select_client_certificate` | 서버가 요구하는 클라이언트 인증서 선택 |

찾기와 프레임 핸들러는 `Client`의 `get_find_handler()`, `get_frame_handler()`가 돌려줍니다. 인증서 정보는 `on_certificate_error`가 아니라 `browser.get_host().get_visible_navigation_entry().get_ssl_status()`로 읽습니다.

## 그 밖에 열린 것

- **HTTP 서버**: `Server`와 `ServerHandler`로 Python이 CEF의 HTTP 서버에 응답합니다.
- **응답 본문 바꾸기**: `ResponseFilter`(`ResourceRequestHandler.get_resource_response_filter`가 돌려줌).
- **개발자 도구**: `browser.get_host().show_dev_tools()`는 자기 창을 엽니다. 닫은 직후에 다시 열면 무시되므로 잠깐 `do_message_loop_work()`를 돈 뒤에 엽니다.
- **공유 메모리 메시지**: `SharedProcessMessageBuilder.write()`와 `SharedMemoryRegion.to_bytes()`는 바이트를 복사해서 주고받습니다.
- **추적**: `begin_tracing()`과 `end_tracing(파일, 콜백)`.
- **미디어 라우터와 구성요소 갱신**: `request_context.get_media_router()`, `ComponentUpdater`. Cast 장치가 없는 환경에서만 확인했습니다(싱크와 경로가 0개).

`CefIsRTL`에 해당하는 `is_rtl()`처럼 CEF를 시작하기 전에 부르면 프로세스가 죽는 함수는, 시작 전에 부르면 `RuntimeError`가 납니다.
