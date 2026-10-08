# wxPython에 붙이는 cefweaver (오프스크린 패널)

`wx.Panel`에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. 그림은 `wx.Bitmap`으로 옮겨 `wx.AutoBufferedPaintDC`로 그립니다.

| 파일 | 내용 |
| --- | --- |
| `cefweaver.ui.toolkits.wx` (패키지) | `cefweaver.ui` 위의 어댑터: `WxAdapter`(그리기, 위치, 커서, 클립보드, 드래그 시작), `WxLoop`(`post`, `call_later`), `CefPanel`(wx 이벤트와 드롭 대상을 `BrowserView`에 전함) |
| `browser.py` | 툴바와 주소창이 있는 작은 브라우저와 데모 페이지(`../common/demo.py`) |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(`../common/checks.py`) |

## 환경 (uv)

wxPython은 PyPI에 Linux wheel이 없어서 wxPython 사이트의 인덱스(`find-links`)를 `pyproject.toml`에 적었습니다. 이 인덱스는 응답이 느려서(요청 하나에 20초 이상) 첫 `uv sync`에 몇 분이 걸립니다. 주소의 `ubuntu-24.04`는 배포판에 맞게 바꾸십시오.

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/wx
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오.

## 실행과 점검

```sh
GDK_BACKEND=x11 uv run python browser.py [주소 | demo]
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE GDK_BACKEND=x11 xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
```

## 알아 둘 것

- **CEF의 깨움은 `wx.CallAfter`로 전달합니다.** 이것은 어느 스레드에서나 안전합니다. 기한은 `wx.Timer`가 맡습니다.
- **복사, 잘라내기, 붙여넣기는 위젯이 직접 처리합니다.** 같은 프로세스의 X 선택을 CEF가 읽으면 이 스레드가 답해야 해서 멈춥니다(Tk, SDL2 예제와 같은 종류). `Ctrl+C`/`Ctrl+X`는 `on_text_selection_changed`의 텍스트를 `wx.TheClipboard`에 넣고, `Ctrl+V`는 클립보드의 텍스트를 `ime_commit_text`로 넣습니다. 일반 텍스트만 다룹니다.
- **드래그 앤 드롭은 wx의 것입니다.** 패널에 `wx.DropTarget`(텍스트와 파일)이 있고, 페이지가 시작한 드래그는 `wx.DropSource`로 실행합니다(`start_dragging` 안이 아니라 `wx.CallAfter`로 이벤트 루프에서 시작합니다. `DoDragDrop()`이 자체 루프를 돌기 때문입니다).
- **wx(GTK)는 마우스 이벤트 핸들러 안에서만 드래그를 시작합니다.** `wx.CallAfter`로 시작하면 `DoDragDrop()`이 곧바로 `DragNone`으로 돌아옵니다(확인함). 그래서 `start_dragging`은 드래그를 예약만 하고 다음 포인터 이동 이벤트에서 시작합니다. 이동하기 전에 버튼을 놓으면 CEF에 드래그가 끝났다고(`NONE`) 알립니다.
- **GTK는 놓기 직전에 `leave`를 먼저 알립니다.** 이를 바로 CEF에 전하면 페이지가 드래그를 접은 뒤에 `drop`이 오므로 한 박자 미룹니다(지금은 `BrowserView.drag_leave()`가 합니다).
- **다른 프로그램의 드롭은 `dragover`의 답을 기다린 뒤 놓습니다(지금은 `BrowserView.drop()`이 합니다).** `enter`, `over`, `drop`을 한 번에 보냈을 때 첫 드롭이 페이지에 `drop` 대신 `dragleave`로 닿았고(확인함), `update_drag_cursor`(렌더러의 답)를 기다린 뒤 `drop`을 보내니 닿았습니다. 렌더러가 답하기 전에 놓기가 처리되는 경합으로 추정하지만 CEF 소스에서 확인하지는 않았습니다. 다른 예제(SDL2 등)는 한꺼번에 보내는 방식이며 점검은 통과했지만, 같은 경합이 있을 수 있습니다.
- **한계: 다른 프로그램에서 오는 드롭은 놓는 순간에야 페이지에 알립니다.** wx는 놓기 전에는 데이터를 주지 않아서(`GetData()`는 `OnData`에서만 됩니다) 페이지는 `dragenter`, `dragover`, `drop`을 한꺼번에 받습니다. 페이지가 시작한 드래그는 데이터를 알고 있으므로 모든 단계가 전달됩니다.
- **한계: 입력기의 미리보기(preedit)를 wx가 주지 않습니다.** 입력기가 확정한 글자는 `EVT_CHAR`로 오므로 `ime_commit_text`로 넣지만 조합 중인 글자는 볼 수 없습니다. 점검 스크립트는 `set_preedit`와 `commit_text`를 직접 불러 CEF 쪽만 확인합니다.
- **`DropSource`는 데이터 객체를 소유하지 않습니다.** 임시 객체를 넘기면 해제된 메모리를 읽어 프로세스가 죽습니다(`DoDragDrop` 안에서 SIGSEGV, gdb로 확인함). 드래그가 끝날 때까지 참조를 유지하십시오.
- **GTK의 `wx.StaticText`는 마우스 이벤트를 받지 못합니다**(자체 창이 없음). 점검 스크립트의 원본 위젯은 직접 그리는 `wx.Panel`입니다.
- **창 번호**: wx는 X 창이 아니라 GtkWidget을 주므로 점검 스크립트는 `xdotool windowfocus`를 쓰지 않습니다.
- **GTK에서 실행하므로 Wayland 세션에서는 `GDK_BACKEND=x11`이 필요합니다.** 실제 화면에 창이 열리는 것을 피하는 용도이기도 합니다.
- 위젯 하나에 브라우저 하나입니다.
