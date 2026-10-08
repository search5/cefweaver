---
title: 툴킷 예제 (Qt, Tkinter, SDL2, wxPython, Kivy)
type: reference
sources:
  - examples/common/demo.py
  - examples/common/checks.py
  - examples/qt/cefqt.py
  - examples/qt/smoke.py
  - examples/tk/ceftk.py
  - examples/tk/smoke.py
  - examples/sdl2/cefsdl.py
  - examples/sdl2/smoke.py
  - examples/wx/cefwx.py
  - examples/wx/smoke.py
  - examples/kivy/cefkivy.py
  - examples/kivy/smoke.py
updated: 2026-10-08
---

# 툴킷 예제

[GTK 3 예제](gtk3-example.md)에 이어 같은 방식(오프스크린 위젯)으로 다섯 툴킷의 예제를 `examples/`에 두었습니다. 환경 구성(uv)과 실행은 각 디렉터리의 `README.md`에 있고, 여기에는 공통 구조와 실제로 돌려서 확인한 것을 적습니다([F69](verified-findings-handlers.md)). 모두 가상 X 서버(`xvfb-run`)에서 X11을 강제하고 실행합니다(툴킷이 실행 중인 Wayland 세션에 창을 여는 일을 막기 위해서입니다).

## 공통 구조

- **`examples/common/demo.py`**: 모든 예제가 보여 주는 같은 데모 페이지(입력란, 버튼, `<select>`, 링크, 문단, 텍스트 영역, 끌 수 있는 요소와 드롭 영역)와 Python 함수 `add`, `appReady`.
- **`examples/common/checks.py`**: 툴킷에 상관없이 같은 점검 22개(그림, 배율, 제목, 입력, 한글 조합, 브리지, 팝업, 휠, 이동과 뒤로 가기, 크기 변경, 복사와 붙여넣기)와 종료 점검을 실행하는 `Checks`. 툴킷마다 `Adapter`(창을 돌리는 방법, 좌표, 제목, 클립보드 등)만 쓰고, 실제 X 이벤트는 xdotool로 보냅니다. 툴킷별 추가 점검(`extra_checks`)이 드래그 앤 드롭을 맡습니다.
- 위젯은 모두 같은 구조입니다: `Runtime`(`CefApp`, `JavascriptBridge`, `MessagePump`)이 CEF의 깨움을 툴킷의 안전한 방법으로 메인 스레드에 옮기고, 위젯이 `on_paint`의 BGRA 버퍼를 그리며 마우스, 휠, 키, 입력기를 CEF 이벤트로 바꿉니다. 로딩이 끝날 때 `notify_screen_info_changed()`를 부르는 것도 같습니다([GTK 3 예제](gtk3-example.md)의 뒤로 가기 캐시 항목).

## 툴킷별 차이 (모두 점검이 전부 통과함)

| 예제 | 깨움 | 한글 조합 | 다른 프로그램과의 드래그 앤 드롭 | 점검 수 |
| --- | --- | --- | --- | --- |
| `qt` (PyQt6와 PySide6, 같은 코드) | 시그널 | Qt 입력기 이벤트 | 양방향 실제 드래그 | 27 |
| `tk` | 파이프와 `createfilehandler` | 확정된 글자만 | 없음(페이지 안의 드래그만) | 24 |
| `sdl2` | `SDL_PushEvent` | `SDL_TEXTEDITING`, `SDL_TEXTINPUT` | 들어오는 드롭만(텍스트, 파일) | 25 |
| `wx` | `wx.CallAfter` | 확정된 글자만 | 양방향 실제 드래그 | 27 |
| `kivy` | `Clock.schedule_once` | `on_textedit`, `on_textinput` | 들어오는 드롭만(텍스트, 파일) | 26 |

점검 수는 실행 출력의 `ok` 줄 수입니다. Qt는 `QT_SCALE_FACTOR=2`에서도 통과했습니다. Tk, SDL2, wx, Kivy는 1배만 확인했습니다.

## 툴킷이 가르쳐 준 것 (공통)

1. **복사와 붙여넣기는 위젯이 직접 처리해야 하는 툴킷이 있습니다.** Qt와 Tk는 같은 프로세스의 X 선택을 툴킷이 소유하거나 읽는데, CEF(같은 스레드)가 선택을 읽으면 아무도 답할 수 없어 페이지가 멈추거나 값이 비었습니다(Qt와 Tk에서 확인. SDL2, wx, Kivy는 처음부터 위젯이 처리해서 CEF에 맡겼을 때의 동작은 확인하지 않았습니다). 그래서 `Ctrl+C`/`Ctrl+X`는 `on_text_selection_changed`의 텍스트를 툴킷의 클립보드에 넣고(잘라내기는 `frame.delete()`), `Ctrl+V`는 클립보드의 텍스트를 `ime_commit_text`로 넣습니다. GTK 3 예제는 CEF에 맡겨서 통과했으므로 **툴킷에 따라 다릅니다.**
2. **드래그를 시작하는 수단이 없는 툴킷은 위젯이 중계합니다**(Tk, SDL2, Kivy): `start_dragging`이 `True`를 돌려준 뒤 마우스 이동을 `drag_target_drag_over`로, 놓기를 `drag_target_drop`으로 보냅니다.
3. **CEF의 포커스**: `on_after_created`에서 준 `set_focus(True)`만으로는 SDL2 예제에서 한글 조합과 `<select>` 팝업이 동작하지 않았고, 클릭에서 다시 주니 동작했습니다. 원인은 조사하지 않았습니다.
4. **열거형 인자의 폭**: Tk 예제가 `DragOperationsMask.EVERY`가 넘치는 결함을 드러냈고 고쳤습니다([F68](verified-findings-handlers.md)).
5. **wx의 세부**(드래그를 마우스 핸들러 안에서만 시작, `DropSource`가 데이터를 소유하지 않음, 드롭의 `dragover` 답을 기다림)와 **Kivy의 세부**(Esc가 앱을 끝냄, 휠 이름이 반대)는 각 `README.md`와 [F69](verified-findings-handlers.md)에 있습니다.

## 확인하지 못한 것

- 실제 입력기(ibus, fcitx)로 하는 조합(가상 X 서버에 없음). 점검은 `set_preedit`와 `commit_text`를 직접 부릅니다.
- SDL2와 Kivy가 받는 드롭은 창이 줄 이벤트를 같은 처리 함수에 넣어 확인했고, 다른 프로그램의 실제 XDND 드래그로는 확인하지 않았습니다.
- Tk에서 `tkinterdnd2`(tkdnd 확장)로 만든 루트는 CEF를 시작할 때 `xcb_io.c: Unknown sequence number`로 프로세스가 중단되었습니다. 일반 `tkinter.Tk()`는 괜찮습니다. **원인은 찾지 못했습니다**([알려진 제약](known-constraints.md)).
- HiDPI(Qt 외), Wayland 네이티브, 서식이 있는(HTML) 클립보드, 이미지.
- `README.rst`가 말하는 PyGame/PyOpenGL, PyWin32, Panda3D의 예제는 만들지 않았습니다.

## 관련 페이지

- [GTK 3 예제](gtk3-example.md)와 [오프스크린 렌더링](offscreen-rendering.md)
- [메시지 펌프](verified-findings-handlers.md)(F62)와 [JavascriptBridge](javascript-bridge.md)
