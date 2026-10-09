---
title: 시작하기
---

# 시작하기

두 가지 방식이 있습니다. GUI 툴킷의 창 안에 브라우저를 넣는 방식(`cefweaver.ui`)이 일반적인 쓰임이고, CEF가 만든 창을 그대로 쓰는 방식(`cefweaver.CefApp`)도 있습니다.

## GUI 툴킷의 위젯 안에 넣기

Tk에 페이지를 띄우는 가장 작은 프로그램입니다.

```python
import sys
import tkinter

from cefweaver import ui
from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

root = tkinter.Tk()
session = ui.Session(TkLoop(root))                    # CEF, run by the Tk loop
canvas = CefCanvas(root, session, width=900, height=640)   # the browser, a Canvas (the size of the window)
canvas.pack(fill="both", expand=True)
canvas.on_ready = lambda: canvas.load_url(URL)        # the browser exists
canvas.on_title = lambda title: print("title:", title, flush=True)
root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(root.destroy))   # close the browser, then the window
root.after(0, lambda: session.start(canvas))
root.mainloop()
```

이 코드는 `examples/tk/quickstart.py`와 같습니다. 다른 툴킷도 `examples/<툴킷>/quickstart.py`가 같은 모양입니다.

| 줄 | 하는 일 |
| --- | --- |
| `ui.Session(TkLoop(root))` | CEF를 Tk의 이벤트 루프가 돌립니다. 별도 스레드나 폴링이 없습니다 |
| `CefCanvas(root, session, ...)` | 브라우저를 그리는 위젯입니다. 크기는 일반 Tk 위젯처럼 정합니다 |
| `canvas.on_ready` | 브라우저가 만들어진 뒤에 불립니다. 이때부터 `load_url()`이 됩니다 |
| `canvas.on_title` | 페이지 제목이 바뀔 때 불립니다. `on_address`, `on_loading`도 있습니다 |
| `session.shutdown(root.destroy)` | 창을 닫을 때 브라우저를 먼저 닫고, 끝나면 창을 없앱니다 |

어떤 툴킷이든 세 가지는 같습니다. 세션을 만들고, 위젯을 만들고, `session.start(위젯)`을 부릅니다. 자세한 구조는 [GUI 툴킷에 넣기](ui.md)에 있습니다.

## CEF의 창을 그대로 쓰기

```python
import cefweaver

app = cefweaver.CefApp()
app.add_javascript_binding("hello", print)    # 페이지에서 window.hello(...)로 Python을 부릅니다
app.initialize("https://example.com")
while app.is_running:                         # 창을 닫으면 False가 됩니다
    app.do_message_loop_work()
app.shutdown()
```

네트워크 없이 메모리에서 페이지를 줄 수도 있습니다.

```python
app.add_resource("http://app.test/index.html", "<h1>hello</h1>")
app.load_url("http://app.test/index.html")
```

브라우저 이벤트(로드, 생명 주기, 표시)는 `Client`의 핸들러로 받습니다. `initialize()` 전에 줍니다.

```python
class Load(cefweaver.LoadHandler):
    def on_load_end(self, browser, frame, http_status_code):
        print("loaded", frame.get_url())

class MyClient(cefweaver.Client):
    def __init__(self):
        self.load = Load()

    def get_load_handler(self):
        return self.load

app.set_client(MyClient())
```

창 모드에서는 Linux에서 X11(Wayland 데스크톱에서는 XWayland)을 씁니다. 이유는 [Wayland와 GPU](wayland-gpu.md)에 있습니다.

CEF 클래스는 생성된 PEP 8 스타일 래퍼로 제공됩니다(`cefweaver.Request`, `cefweaver.ResourceHandler` 등). 열거형과 값 타입은 `cefweaver.types`에 있습니다(`types.MouseButtonType.LEFT`, `types.Rect(0, 0, 640, 480)`). 정수와 튜플도 그 자리에 받습니다.
