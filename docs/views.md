---
title: Views (툴킷 없이)
---

# Views (툴킷 없이)

GUI 툴킷 없이 CEF만으로 창을 만들 수 있습니다. CEF의 **Views 프레임워크**가 창, 도구 모음, 단추, 텍스트 입력칸, 레이아웃, 브라우저를 직접 그리고 마우스와 키 입력도 처리합니다. 프로그램은 뷰를 조립하고 델리게이트(콜백)로 반응합니다. [GUI 툴킷에 넣기](ui.md)가 툴킷의 위젯에 오프스크린 그림을 그리는 것과 달리, 이 방식의 브라우저는 CEF 자신의 창에 그려집니다.

> 이 쪽의 내용은 Linux x86_64(X11)에서 확인했습니다. Windows, macOS, Wayland는 확인하지 못했습니다.

## 클래스

CEF의 상속을 그대로 따릅니다. `Window`는 `Panel`의 하위 클래스이고 `Panel`은 `View`의 하위 클래스입니다. `BrowserView`, `Button`(`LabelButton`, `MenuButton`), `Textfield`, `ScrollView`도 `View`의 하위 클래스입니다. 하위 클래스의 객체는 상위 클래스를 받는 자리에 그대로 넘길 수 있습니다. 반대로 CEF가 `View`로 돌려주는 객체는 실제 종류의 클래스로 옵니다(`Window`면 `Window`, `LabelButton`이면 `LabelButton`).

## 시작

`initialize(None)`로 **첫 브라우저 없이** CEF만 시작하고, `BrowserView`와 `Window`를 만듭니다. 창이 만들어지면 `WindowDelegate.on_window_created`가 불리므로 거기서 뷰를 붙입니다.

```python
import cefweaver as cef
from cefweaver import types

class Window(cef.WindowDelegate):
    def __init__(self, browser_view):
        super().__init__()
        self.browser_view = browser_view
    def on_window_created(self, window):
        window.add_child_view(self.browser_view)
        window.show()
    def on_window_destroyed(self, window):
        global done
        done = True
    def can_close(self, window):
        return True

app = cef.CefApp()
app.initialize(None)
view = cef.BrowserView.create_browser_view(cef.Client(), "https://example.org/", types.BrowserSettings(), None, None, cef.BrowserViewDelegate())
cef.Window.create_top_level_window(Window(view))
done = False
while not done:
    app.do_message_loop_work()
app.shutdown()
```

도구 모음(단추와 주소 입력칸)을 단 전체 예제는 `examples/views/`에 있습니다(`quickstart.py`, 실제 X 이벤트로 점검하는 `smoke.py`).

## 알아 둘 것

- **루프는 `do_message_loop_work()`를 자주 부르는 폴링이어야 합니다.** 창을 CEF가 소유하므로 창 시스템의 이벤트를 CEF가 직접 처리해야 합니다. `MessagePump`(`external_message_pump`)를 쓰면 CEF가 알린 작업만 하고 자기 창의 X11 이벤트를 처리하지 않아서, 단추를 눌러도 `on_button_pressed`가 오지 않았습니다.
- **창이 열린 채로 `shutdown()`을 불러도 됩니다.** `shutdown()`이 남아 있는 브라우저를 먼저 닫고 CEF를 종료합니다(예전에는 세그멘테이션 오류가 났습니다). 그래도 창의 닫힘은 `on_window_destroyed`로 확인하는 편이 분명합니다.
- **같은 CEF 뷰라도 Python 객체는 매번 다릅니다.** 델리게이트가 받은 단추를 구분하려면 `set_id`로 번호를 주고 `get_id()`로 비교하십시오.
- `initialize(None)` 뒤에는 `app.create_browser()`를 쓸 수 없습니다(첫 브라우저가 있어야 해서 `RuntimeError`). `app.load_url()`과 `app.execute_javascript()`는 `initialize(None)`로 시작했을 때와 Views의 브라우저에는 적용되지 않고 `False`를 돌려줍니다. 그 브라우저에서는 `view.get_browser().get_main_frame().load_url(...)`처럼 프레임을 직접 씁니다.
- `View.get_delegate()`, `BrowserHost.get_client()`, `RequestContext.get_handler()`는 CEF에 준 Python 객체를 그대로 돌려줍니다(CEF가 만든 것은 `None`). `BrowserViewDelegate.get_delegate_for_popup_browser_view`는 팝업을 여는 뷰의 클라이언트에 `LifeSpanHandler`가 있을 때 불렸고, `WindowDelegate.get_parent_window`도 쓸 수 있습니다. 자세한 것은 [한계와 알려진 제약](limitations.md)에 있습니다.
