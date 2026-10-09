---
title: GUI 툴킷에 넣기
---

# GUI 툴킷에 넣기 (`cefweaver.ui`)

`cefweaver.ui`는 **오프스크린** 브라우저를 GUI 툴킷의 위젯 안에 보여 줍니다. 창을 위젯에 심는 방식이 아니라 CEF가 그린 픽셀을 받아 툴킷의 방식으로 그립니다. 그래서 Wayland에서도 같은 방식으로 동작하고, 마우스, 키, 입력기, 클립보드, 끌어서 놓기를 위젯이 CEF 이벤트로 바꿔 줍니다.

## 구성 요소

| 이름 | 하는 일 |
| --- | --- |
| `ui.Session` | CEF, JavaScript 브리지, 메시지 펌프를 한 묶음으로 가집니다. CEF가 일할 때가 되면 툴킷의 루프를 깨워서 돌리므로 별도 스레드나 폴링이 없습니다. 한 세션에 브라우저는 하나입니다 |
| `ui.BrowserView` | CEF 쪽의 일을 합니다. 핸들러, 이벤트 기록, 클릭 횟수, 입력기, 클립보드 키, 끌어서 놓기를 처리하고 소리, 권한, 메뉴 같은 기능의 옵션을 가집니다 |
| `ui.BrowserWidget` | 툴킷 위젯의 기반 클래스입니다. `load_url()`, `go_back()`, `reload()`, `snapshot(경로)`와 훅 `on_title`, `on_address`, `on_loading`, `on_ready`를 줍니다 |
| 툴킷 어댑터 | 툴킷이 뷰에게 주는 것(크기, 그리기, 커서, 클립보드 등). `cefweaver.ui.toolkits` 아래에 여섯 개가 있습니다([툴킷별 상태](toolkits.md)) |

## 기본 흐름

```python
from cefweaver import ui

session = ui.Session(loop, switches=[("autoplay-policy", "no-user-gesture-required")], cache_path="/tmp/my-cache")
widget = 툴킷의_위젯(...)                       # 툴킷 모듈의 위젯 (예: CefCanvas)
widget.on_ready = lambda: widget.load_url("https://example.org/")
session.start(widget)                           # 위젯이나 BrowserView
...
session.shutdown(done=툴킷을_끝내는_함수)      # 브라우저를 먼저 닫고, 끝나면 done을 부릅니다
```

- `loop`는 툴킷의 루프 객체입니다(`TkLoop(root)` 같은 것). 세션이 필요한 것은 `post(함수)`(메인 스레드에서 실행, 어느 스레드에서든 호출 가능)와 `call_later(초, 함수)` 둘뿐입니다.
- `switches`는 Chromium 명령줄 스위치 `(이름, 값)`의 목록입니다. 주지 않은 `ozone-platform`은 Wayland 컴포지터가 있으면 `wayland`로 채워집니다([Wayland와 GPU](wayland-gpu.md)). 실제로 CEF에 준 목록은 `session.switches`입니다.
- `cache_path`를 주지 않으면 CEF가 작업 폴더에 `cache/`를 만듭니다. 임시 폴더를 쓰는 것이 안전합니다.

## 페이지와 Python 사이의 호출

`session.bridge`로 Python 함수를 페이지에 내놓고 페이지에서 Python을 부릅니다. 함수는 `session.start()` **전에** 내놓습니다.

```python
session.bridge.expose("add", lambda a, b: a + b)
```

```javascript
add(2, 3).then(function (sum) { console.log(sum); });   // 페이지에서는 Promise를 돌려줍니다
```

Python에서 페이지의 JavaScript를 실행하려면 `session.bridge.evaluate(frame, "식", 콜백)`을 씁니다. 다만 `eval`을 막는 페이지(Trusted Types나 엄격한 CSP를 쓰는 YouTube, GitHub 등)에서는 콜백의 오류 값으로 `EvalError`가 옵니다. 그런 페이지에는 `expose`로 내놓은 함수를 부르게 하세요.

## 어댑터를 직접 만들기

다른 툴킷에 붙이려면 어댑터를 만듭니다. **필수**는 다음 일곱 개입니다.

| 메서드 | 뜻 |
| --- | --- |
| `view_size()` | 뷰의 `(너비, 높이)` (논리 픽셀) |
| `scale()` | 논리 픽셀당 장치 픽셀 수 |
| `screen_origin()` | 뷰의 왼쪽 위 모서리의 화면 좌표 |
| `screen_size()` | 화면의 `(너비, 높이)` |
| `present(frame)` | CEF가 그린 `ui.Frame`을 그립니다. `frame.buffer`(BGRA)는 이 호출 동안만 유효합니다 |
| `post(함수)` | 메인 스레드에서 실행합니다 |
| `call_later(초, 함수)` | 메인 스레드에서 나중에 실행합니다 |

**선택**(있으면 그 기능이 켜집니다):

| 메서드 | 기능 |
| --- | --- |
| `set_cursor(cursor)` | CEF가 원하는 커서를 보입니다 |
| `clipboard_get()`, `clipboard_set(text)` | 복사, 잘라내기, 붙여넣기(키와 컨텍스트 메뉴 모두)를 툴킷의 클립보드로 처리합니다 |
| `set_ime_rect(x, y, w, h)` | 입력기의 후보 창 위치 |
| `start_drag_out(payload, allowed)` | 페이지에서 끌어 낸 것을 툴킷의 끌어서 놓기로 보냅니다 |
| `audio_sink()` | 페이지의 소리를 재생할 싱크를 줍니다([소리, 마이크, 카메라](media.md)) |
| `show_menu(items, x, y, done)` | 컨텍스트 메뉴를 보입니다([컨텍스트 메뉴](context-menu.md)) |
| `release()` | 세션이 끝날 때 루프가 놓을 것이 있으면 놓습니다 |

화면이 없는 환경에서 시험하려면 `ui.headless.HeadlessAdapter`를 쓸 수 있습니다. 그림을 메모리에 받아 두고 `save_png(경로)`로 PNG로 저장하며, 이벤트 루프(`run_until`, `run_for`)도 스스로 돕니다. 위젯의 `snapshot(경로)`는 뷰가 가진 그림을 PNG로 저장합니다.
