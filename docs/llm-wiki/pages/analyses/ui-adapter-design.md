---
title: UI 어댑터 설계 (여섯 예제의 비교와 인터페이스 초안)
type: analysis
sources:
  - cefweaver/ui/toolkits/gtk3.py
  - cefweaver/ui/toolkits/qt.py
  - cefweaver/ui/toolkits/tk.py
  - cefweaver/ui/toolkits/sdl2.py
  - cefweaver/ui/toolkits/wx.py
  - cefweaver/ui/toolkits/kivy.py
  - examples/common/checks.py
updated: 2026-10-08
---

# UI 어댑터 설계

여섯 예제(GTK 3, Qt, Tk, SDL2, wx, Kivy)의 위젯 파일은 합쳐서 약 3,300줄이고, 모두 같은 핸들러 클래스 다섯 개(`_Handlers`, `_Render`, `_Life`, `_Display`, `_Load`)를 따로 복사해 갖고 있습니다. 사용자가 새 툴킷에 붙일 때 이 코드를 베끼지 않고 **툴킷이 해야 하는 일만** 구현하게 하려는 계획의 1단계(비교와 인터페이스 초안)입니다. 합의한 방침: 처음에는 공통 본체 `BrowserView`와 어댑터 인터페이스만 `cefweaver.ui`로 제공하고 툴킷별 어댑터는 `examples/`에 두며, 드래그 앤 드롭은 어댑터가 능력을 선언합니다.

## 공통인 것 (라이브러리가 맡을 것)

여섯 예제가 같은 모양으로 구현한 부분입니다. 값이나 순서도 같습니다.

- 핸들러 5종의 연결과 `browser` 보관, `on_after_created`에서의 시작, `on_before_close`에서의 해제.
- `get_view_rect`, `get_screen_info`(배율), `get_screen_point`, `on_popup_show`, `on_popup_size`, `on_text_selection_changed`.
- 로딩이 끝날 때 `notify_screen_info_changed()`(뒤로 가기 캐시 복원 우회, [F67](../reference/verified-findings-handlers.md)).
- 마우스 이벤트 조립(`MouseEvent`, 단추 종류, 클릭 횟수), 키 이벤트 조립(`RAWKEYDOWN`, `CHAR`, `KEYUP`, 수정 키 규칙: Ctrl이나 Alt가 눌리면 `CHAR`를 보내지 않음), 한글 조합(`ime_set_composition`, `ime_commit_text`, `ime_cancel_composition`).
- 복사, 잘라내기, 붙여넣기의 키 처리(선택 텍스트를 보관하고 `frame.delete()`, 붙여넣을 때 `ime_commit_text`).
- 드래그의 상태 기계: 들어오는 드롭의 `enter`, `over`, `leave`, `drop` 순서, `drag_operation`의 비동기 답(`update_drag_cursor`)을 기다린 뒤 `drop`([F69](../reference/verified-findings-handlers.md)), `leave`를 한 박자 미루기, 나가는 드래그의 시작과 끝 알림(`drag_source_ended_at`, `drag_source_system_drag_ended`), 시작 수단이 없는 툴킷을 위한 페이지 안의 중계.
- `MessagePump`의 일정 잡기(깨움은 `post`, 기한은 `call_later`로 어댑터에 위임).
- 종료 순서(`close_browser`, `is_running` 확인, `shutdown`).

## 툴킷마다 다른 것 (어댑터가 맡을 것)

| 항목 | GTK 3 | Qt | Tk | SDL2 | wx | Kivy |
| --- | --- | --- | --- | --- | --- | --- |
| 깨움(어느 스레드에서나) | `GLib.idle_add` | 시그널 | 파이프, `createfilehandler` | `SDL_PushEvent` | `wx.CallAfter` | `Clock.schedule_once` |
| 기한 | `timeout_add` | `QTimer` | `after` | `SDL_WaitEventTimeout` | `wx.Timer` | `Clock.schedule_once` |
| 그리기 | cairo, 더러운 행만 복사 | `QImage` | Pillow, 통째로 | 텍스처 부분 갱신 | `wx.Bitmap` 통째로 | `Texture` 통째로, 상하 반전 |
| 클릭 횟수 | 이벤트 종류 | Qt가 줌 | 직접 셈 | `clicks` | 직접 셈 | `is_double_tap` |
| 휠 | 부드러운 델타 | `angleDelta` | 버튼 4, 5 | 휠 이벤트 | 회전량 | 버튼(이름이 반대) |
| 한글 조합 | `IMContext` | `inputMethodEvent` | 확정 글자만 | `TEXTEDITING` | 확정 글자만 | `on_textedit` |
| 클립보드 | **CEF에 맡겨도 됨** | 위젯이 처리 | 위젯이 처리 | 위젯이 처리 | 위젯이 처리 | 위젯이 처리 |
| 들어오는 드롭 | 데이터를 먼저 요청 | 이벤트에 데이터 | 없음 | 텍스트와 파일, 위치 없음 | 놓을 때만 데이터 | 텍스트와 파일, 위치 있음 |
| 나가는 드래그 | `drag_begin` | `QDrag.exec` | 중계 | 중계 | `DropSource`(다음 이동에서) | 중계 |
| 화면 좌표 | 창 원점 | `mapToGlobal` | `winfo_rootx` | `SDL_GetWindowPosition` | `ClientToScreen` | `Window.left`, `Window.top` |

차이의 대부분은 **입력과 출력의 번역**(툴킷 값을 CEF 값으로)이고, 규칙은 같습니다.

## 인터페이스 초안

```python
# cefweaver/ui/adapter.py  (실험적: 0.x)
class ToolkitAdapter(Protocol):
    # 필수: 이것만 구현하면 보이고 입력을 받습니다
    def view_size(self) -> tuple[int, int]: ...           # 논리 픽셀
    def scale(self) -> float: ...
    def screen_origin(self) -> tuple[int, int]: ...       # 뷰의 왼쪽 위, 화면 좌표
    def screen_size(self) -> tuple[int, int]: ...
    def present(self, frame: Frame) -> None: ...          # Frame: kind(VIEW/POPUP), width, height, buffer(BGRA, 이 호출 동안만 유효), dirty_rects
    def post(self, function) -> None: ...                 # 어느 스레드에서나 부름: 메인 스레드에서 실행
    def call_later(self, seconds, function) -> Cancel: ...

    # 선택: 없으면 그 기능이 꺼집니다 (속성 capabilities로 선언)
    def set_cursor(self, name) -> None: ...
    def clipboard_get(self) -> str | None: ...
    def clipboard_set(self, text) -> None: ...
    def set_ime_rect(self, x, y, w, h) -> None: ...
    def start_drag_out(self, data: DragPayload, allowed) -> bool: ...   # 없으면 페이지 안의 중계
    def on_title(self, title) / on_address(self, url) / on_loading(self, loading, back, forward)
```

`BrowserView`는 툴킷 위젯이 부르는 **중립 입력**을 받습니다: `resized()`, `focus(bool)`, `shown(bool)`, `mouse_move(x, y, mods, leave=False)`, `mouse_button(x, y, button, pressed, mods, clicks=None)`, `wheel(x, y, dx, dy, mods)`, `key(down, windows_key_code, native_code, mods, char=None)`, `text(str)`, `preedit(str, cursor)`, `drop(x, y, text=None, files=None, html=None)`와 드래그 상태 알림. 키 코드 표는 툴킷마다 달라서 어댑터가 가지고, 공통 부분(`ord(c.upper())`, 기능 키 112+n)은 `cefweaver.ui.keys`에 둡니다.

**능력 선언**: 어댑터가 `capabilities = {"drag_in", "drag_out", "preedit", "native_clipboard"}`처럼 선언하고, `BrowserView`는 이에 따라 행동을 고릅니다(예: `drag_out`이 없으면 중계, `native_clipboard`가 없으면 위젯 쪽 처리).

## 이식으로 검증할 것

- GTK 3를 먼저 이식해서 기존 점검(27개)이 그대로 통과하고 위젯 파일이 얼마나 줄어드는지 봅니다. 통과하지 못하는 부분이 인터페이스의 결함입니다.
- 클립보드는 GTK 3만 CEF에 맡겨도 통과했습니다. 나머지는 같은 스레드의 교착 때문에 위젯이 처리해야 했으므로 `native_clipboard` 능력이 갈립니다([툴킷 예제](../reference/toolkit-examples.md)).
- 확인하지 못한 것은 이식으로도 달라지지 않습니다: 실제 입력기, HiDPI(Qt 외), Wayland 네이티브.

## 구현 상태 (2단계)

`cefweaver.ui`로 구현했습니다([UI 어댑터 API](../reference/ui-api.md)). 초안에서 바뀐 것: 키 입력은 `key()`가 클립보드 키를 처리하면 True를 돌려줍니다. 놓는 순간만 아는 툴킷을 위해 `drop()`(한꺼번에)을 따로 두었고, 단계별 `drag_enter` 등과 나눴습니다. 나가는 드래그는 `begin_drag`가 능력(`drag_out`)에 따라 갈립니다. 툴킷 없이 시험하고 스크립트에 쓰도록 `HeadlessAdapter`를 더했습니다.

여섯 예제를 모두 이식했고(GTK 3, Tk, SDL2, Kivy, wx, Qt) 점검이 하나도 바뀌지 않고 통과했습니다. 상세는 [UI 어댑터 API](../reference/ui-api.md)에 있습니다.

## 관련 페이지

- [UI 어댑터 API](../reference/ui-api.md)
- [툴킷 예제](../reference/toolkit-examples.md)와 [GTK 3 예제](../reference/gtk3-example.md)
- [오프스크린 렌더링](../reference/offscreen-rendering.md)
