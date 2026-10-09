---
title: 툴킷별 상태
---

# 툴킷별 상태

여섯 툴킷에 어댑터가 있습니다. 아래는 2026-10-09 기준으로 확인한 것입니다.

**확인 방법**은 두 가지입니다.

- **점검(smoke)**: 가상 X 서버(Xvfb)에서 예제 앱을 띄우고 실제 X 이벤트(`xdotool`)로 마우스, 키, 끌어서 놓기, 클립보드, 오른쪽 클릭 메뉴 등을 조작해 결과를 봅니다. 각 예제의 `smoke.py`입니다. 괄호는 항목 수입니다.
- **실제 화면**: 개발자가 실제 데스크톱에서 직접 써 보았습니다. 이때 툴킷의 창은 X11이었고 CEF만 Wayland였습니다. 툴킷 자체를 네이티브 Wayland로 쓰는 경우는 시험하지 못했습니다.

## 한눈에 보기

| 모듈 | 위젯 | 소리 | 오른쪽 클릭 메뉴 | 점검 | 실제 화면 |
| --- | --- | --- | --- | --- | --- |
| `cefweaver.ui.toolkits.gtk3` | `CefWidget` (`Gtk.DrawingArea`) | pygame | `Gtk.Menu` | 통과 (39) | 확인함 |
| `cefweaver.ui.toolkits.qt` | `CefWidget` (`QWidget`) | `QtSink` (QtMultimedia) | `QMenu` | PyQt6, PySide6 통과 (각 35) | 두 바인딩 모두 확인함 |
| `cefweaver.ui.toolkits.tk` | `CefCanvas` (`tkinter.Canvas`) | pygame | `tkinter.Menu` | 통과 (30) | 확인함 (한영 전환 제외) |
| `cefweaver.ui.toolkits.sdl2` | `SdlBrowser` (창과 루프 포함) | `SdlSink` | 없음 | 통과 (28) | 소리 확인함 |
| `cefweaver.ui.toolkits.wx` | `CefPanel` (`wx.Panel`) | pygame | `wx.Menu` | 통과 (33) | 확인함 |
| `cefweaver.ui.toolkits.kivy` | `CefView` (`Widget`) | pygame | 없음 | 통과 (27) | 소리 확인함 |

"소리"는 페이지의 소리를 재생하는 방법입니다. 툴킷에 재생 API가 있으면 그것을, 없으면 pygame을 씁니다([소리, 마이크, 카메라](media.md)). 영상과 소리는 여섯 툴킷(Qt는 두 바인딩) 모두에서 YouTube 영상을 재생해 들어 보았습니다.

## 툴킷별 메모

### GTK 3

`GlibLoop`, `GtkAdapter`, `CefWidget`. 실제 화면에서 한글 입력(입력기), 복사와 붙여넣기, 끌어서 놓기를 확인했고 배율 2(HiDPI)는 점검으로 확인했습니다. 메뉴는 CEF가 오른쪽 버튼을 누르는 순간 요청하므로, 위젯이 받은 실제 버튼 이벤트로 메뉴를 띄웁니다.

### Qt

`QtLoop`, `QtAdapter`, `CefWidget`, `QtSink`. PyQt6가 기본이고 PySide6는 환경 변수 `CEFQT_BINDING=pyside6`으로 고릅니다. 배율 2는 점검으로 확인했습니다. 실제 입력기로 한글을 입력해 본 것은 아닙니다(점검은 입력기가 확정한 글자를 어댑터로 흉내 냅니다).

### Tk

`TkLoop`, `TkAdapter`, `CefCanvas`. 그림은 Pillow로 바꿔 그립니다. **한영 전환이 되지 않습니다**(Tk가 입력기의 조합 중 글자를 주지 않고, 원인은 확인하지 못했습니다). 실제 입력기로 한글 입력을 확인한 툴킷은 GTK 3입니다.

### SDL2

`SdlBrowser` 하나가 창, 브라우저, 이벤트 루프를 모두 가집니다. 오른쪽 클릭 메뉴는 없습니다: SDL2에는 메뉴를 만드는 함수가 없고(`SDL_ShowMessageBox` 같은 메시지 상자뿐), 창 종류를 알리는 플래그(`SDL_WINDOW_POPUP_MENU` 등)만 있습니다. 이 툴킷에서는 `view.on_context_menu`도 불리지 않습니다. 메뉴가 필요하면 어댑터에 `show_menu`를 직접 구현하세요([컨텍스트 메뉴](context-menu.md)).

### wxPython

`WxLoop`, `WxAdapter`, `CefPanel`. wx의 메뉴는 메뉴가 닫힐 때까지 자체 이벤트 루프를 돌아서, CEF의 응답이 끝난 뒤, 그리고 오른쪽 버튼이 떨어진 뒤에 엽니다. 실제 입력기로 한글을 입력해 본 것은 아닙니다.

### Kivy

`KivyLoop`, `KivyAdapter`, `CefView`. 오른쪽 클릭 메뉴는 없습니다: Kivy에는 네이티브 컨텍스트 메뉴 위젯이 없고 `DropDown`은 특정 위젯에 붙여 여는 것이라 클릭 위치에 맞지 않습니다. 같은 이유로 이 툴킷에서도 `view.on_context_menu`가 불리지 않습니다.
