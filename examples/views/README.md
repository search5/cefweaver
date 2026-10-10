# Views (툴킷 없이 CEF만으로 만드는 창)

CEF의 **Views 프레임워크**로 창, 도구 모음(단추와 주소 입력칸), 브라우저를 구성하는 예제입니다. GUI 툴킷이 필요 없습니다. 창과 단추와 입력칸은 CEF가 그리고 마우스와 키 입력도 CEF가 처리하며, 프로그램은 뷰를 조립하고 델리게이트(콜백)로 반응합니다. 다른 예제들은 툴킷의 위젯에 오프스크린 그림을 그리지만, 이 예제의 브라우저는 CEF 자신의 창에 직접 그려집니다.

| 파일 | 내용 |
| --- | --- |
| `browser.py` | `ViewsBrowser`: 창 델리게이트, 도구 모음(`Panel`, `LabelButton` 3개, `Textfield`), `BrowserView`, 상자 배치(`BoxLayout`), 단추와 주소칸의 델리게이트, 제목과 주소 갱신 |
| `quickstart.py` | 가장 작은 프로그램: 페이지를 띄우고 창을 닫으면 정상 종료 |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(13개) |

## quickstart

Views 창에 페이지를 띄우는 가장 작은 프로그램입니다(`quickstart.py`). 주소를 인자로 줄 수 있고, 창을 닫으면 CEF를 종료하고 끝납니다.

```python
import sys

from browser import ViewsBrowser

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

app = ViewsBrowser(URL, title_changed=lambda title: print("title:", title, flush=True))
app.start()
app.run()                                       # until the window is closed
```

## 환경 (uv)

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/views
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오. 툴킷도 별도의 패키지도 필요 없습니다.

## 실행과 점검

```sh
uv run python quickstart.py [주소]
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
```

`smoke.py`가 점검하는 것: 창과 제목, 단추와 주소칸이 한 줄에 왼쪽부터 놓이는지, 브라우저가 도구 모음 아래에서 남는 높이를 차지하는지, 주소칸이 남는 너비를 차지하는지, 주소칸을 클릭하고 주소를 입력하면 글자가 들어가는지(실제 마우스와 키 이벤트), Return으로 페이지가 열리는지, Back과 Forward와 Reload 단추, 창을 닫을 때 정상 종료.

## 알아 둘 것

- **`CefApp.initialize(None)`로 시작합니다.** 첫 브라우저를 만들지 않고 CEF만 초기화합니다. 브라우저는 `BrowserView.create_browser_view()`가 만들고, 창에 붙인 뒤에야 `get_browser()`가 값을 줍니다. 이때 `is_running`은 `shutdown()`까지 계속 `True`이므로, 창이 닫힌 것은 `WindowDelegate.on_window_destroyed`로 알립니다.
- **루프는 폴링(`do_message_loop_work()`을 자주 부름)이어야 합니다.** 이 예제의 창은 CEF가 소유하므로 창 시스템의 이벤트를 CEF가 직접 처리해야 합니다. **`MessagePump`(`external_message_pump`)를 쓰면 CEF가 알린 작업만 하고 자기 창의 X11 이벤트를 처리하지 않아서** 단추를 눌러도 `on_button_pressed`가 오지 않았습니다(확인함). 툴킷 어댑터가 `MessagePump`를 쓰는 것은 그 입력을 툴킷의 창이 받기 때문입니다.
- **`shutdown()` 전에 창을 먼저 닫으십시오.** 창이 열린 채로 `app.shutdown()`을 부르면 세그멘테이션 오류가 났습니다(원인은 조사하지 않음). 이 예제는 `on_window_destroyed` 뒤에 `shutdown()`을 부릅니다.
- **델리게이트가 받는 객체는 같은 CEF 뷰라도 같은 Python 객체가 아닙니다.** 단추는 `set_id`로 번호를 주고 `get_id()`로 구분하십시오. 반대로 CEF가 돌려주는 뷰는 **실제 종류의 클래스**로 옵니다(`Window`가 `View` 자리에 오면 `Window`, `LabelButton`이 `View`로 오면 `LabelButton`).
- 뷰의 클래스는 CEF의 상속을 그대로 따릅니다: `Window`는 `Panel`의 하위 클래스이고 `Panel`은 `View`의 하위 클래스입니다. `Window`를 `View`를 받는 자리에 그대로 넘길 수 있고, 각 클래스는 자기 메서드만 갖고 나머지는 상속합니다.
- 창 관리자가 없는 가상 화면에서도 위 점검이 통과합니다(`windowfocus`를 줄 필요도 없었음).
- 확인한 환경은 Linux x86_64, CPython 3.13, CEF 154, X11(`ozone-platform=x11`)입니다. **Windows와 macOS, Wayland는 확인하지 못했습니다.**
- 아직 열지 못한 것: 팝업 창을 위한 `BrowserViewDelegate.get_delegate_for_popup_browser_view`, `WindowDelegate.get_parent_window`, 각 뷰의 `get_delegate()`([알려진 제약](../../llm-wiki/pages/reference/known-constraints.md)).
