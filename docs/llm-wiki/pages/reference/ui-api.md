---
title: UI 어댑터 API (cefweaver.ui)
type: reference
sources:
  - cefweaver/ui/__init__.py
  - cefweaver/ui/adapter.py
  - cefweaver/ui/view.py
  - cefweaver/ui/session.py
  - cefweaver/ui/keys.py
  - cefweaver/ui/headless.py
  - tests/test_ui.py
updated: 2026-10-08
---

# UI 어댑터 API (cefweaver.ui)

GUI 툴킷에 오프스크린 브라우저를 붙일 때 [툴킷 예제](toolkit-examples.md)의 위젯 코드를 베끼지 않고 **툴킷이 해야 하는 일만** 구현하게 하는 하위 패키지입니다. 실험적이며 인터페이스가 바뀔 수 있습니다. 설계와 근거는 [UI 어댑터 설계](../analyses/ui-adapter-design.md)에 있고, 여기에는 구현된 것(계획의 2단계)을 적습니다. 순수 Python이고 CEF 프로세스 없이 시험할 수 있습니다.

## 구성

| 이름 | 내용 |
| --- | --- |
| `BrowserView(adapter)` | 브라우저 하나와 CEF 쪽 규칙 전부: 핸들러 5종(`view.client`), 입력 이벤트의 조립, 클릭 횟수, 입력기, 클립보드 키, 드래그 앤 드롭의 순서 |
| `ToolkitAdapter` | 툴킷이 구현할 필수 7개: `view_size`, `scale`, `screen_origin`, `screen_size`, `present(frame)`, `post(fn)`, `call_later(seconds, fn)` |
| 선택 메서드 | `set_cursor`, `clipboard_get`과 `clipboard_set`, `set_ime_rect`, `start_drag_out`, `drag_operation_changed`. 있으면 그 기능이 켜집니다 |
| `capabilities` | 어댑터의 속성(집합). `"native_clipboard"`는 CEF가 클립보드 키를 직접 처리해도 된다는 뜻(GTK 3), `"drag_out"`은 `start_drag_out`으로 툴킷의 드래그를 시작할 수 있다는 뜻 |
| `Session(adapter, switches, cache_path)` | `CefApp`, `JavascriptBridge`, `MessagePump`. CEF의 깨움을 `adapter.post`로, 기한을 `adapter.call_later`로 받아 폴링 없이 돌립니다. `start(view, url)`, `shutdown(done)` |
| `Frame` | `present()`가 받는 그림: `kind`(`VIEW`, `POPUP`, `POPUP_HIDDEN`), `width`, `height`, `buffer`(BGRA, 호출 동안만 유효), `dirty_rects`, 팝업은 `rect` |
| `keys` | CEF 이벤트 플래그(`SHIFT`, `CONTROL`, `ALT`, 단추)와 가상 키 코드(`VK_*`), `vk_for_char`, `vk_for_function` |
| `headless.HeadlessAdapter` | 툴킷 없는 어댑터: 자체 루프(`run_until`, `run_for`), 마지막 그림 보관, `save_png`, `pixel` |

## 툴킷이 부르는 입력

`resized()`, `focus(bool)`, `shown(bool)`, `mouse_move(x, y, mods, leave=False)`, `mouse_button(x, y, "left"|"middle"|"right", pressed, mods, clicks=None)`, `wheel(x, y, dx, dy, mods)`, `key(down, windows_key_code, native_code, mods, char=None)`(클립보드 키를 처리했으면 True), `text(str)`, `preedit(str, cursor)`. 좌표는 논리 픽셀이고 수정 키는 `keys`의 합입니다.

드래그 앤 드롭은 툴킷이 말하는 방식에 따라 둘 중 하나입니다. 단계마다 알려 주는 툴킷(GTK, Qt)은 `drag_enter(x, y, ops, text=, html=, url=, files=)`, `drag_over`, `drag_leave`, `drag_drop`을, 놓는 순간만 알려 주는 툴킷(wx, SDL2, Kivy)은 `drop(x, y, text=, ...)`을 부릅니다. 나가는 드래그는 어댑터에 `start_drag_out`이 없으면 뷰가 페이지 안에서만 중계하고, 있으면 `DragPayload`를 받아 툴킷의 드래그를 시작한 뒤 끝나면 `drag_out_finished(x, y, operation)`을 부릅니다.

## 예제에서 옮겨 온 규칙 (시험으로 지킴)

- 클릭 횟수는 0.4초와 4픽셀 안에서 3까지 세고, 툴킷이 횟수를 주면 그것을 씁니다. 누르면 `focus(True)`를 줍니다(SDL2 예제에서 필요했음).
- Ctrl이나 Alt가 눌리면 `CHAR`를 보내지 않습니다. Enter, Tab, BackSpace는 항상 `CHAR`를 보냅니다.
- 클립보드 키는 어댑터에 `clipboard_get`과 `clipboard_set`이 있고 `native_clipboard`가 없을 때만 뷰가 처리합니다(키를 뗄 때도 소비).
- 로딩이 끝나면 `notify_screen_info_changed()`를 부릅니다([F67](verified-findings-handlers.md)).
- `leave`는 한 박자 미루고(GTK는 놓기 직전에 `leave`를 보냄), 한꺼번에 오는 드롭은 `dragover`의 답(`update_drag_cursor`)을 기다린 뒤 놓되 0.5초가 한계입니다([F69](verified-findings-handlers.md)).

## 아직 하지 않은 것

- 여섯 예제를 이 API로 이식하기(계획의 3단계). 이식으로 인터페이스의 결함이 드러날 수 있습니다.
- 한 세션에 브라우저 하나만 다룹니다.
- 툴킷별 공식 어댑터는 패키지에 넣지 않았습니다(`examples/`에 둘 예정).

## 관련 페이지

- [UI 어댑터 설계](../analyses/ui-adapter-design.md)와 [툴킷 예제](toolkit-examples.md)
- [메시지 펌프](verified-findings-handlers.md)(F62)
