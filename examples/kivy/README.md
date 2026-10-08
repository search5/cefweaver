# Kivy에 붙이는 cefweaver (오프스크린 위젯)

Kivy `Widget`에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. 그림은 `Texture`(`bgra`)로 올려 `Rectangle`로 그립니다.

| 파일 | 내용 |
| --- | --- |
| `cefweaver.ui.toolkits.kivy` (패키지) | `cefweaver.ui` 위의 어댑터: `KivyAdapter`(그리기, 위치, 커서, 클립보드), `KivyLoop`(`post`, `call_later`), `CefView`(Kivy 창의 이벤트를 `BrowserView`에 전함) |
| `browser.py` | 툴바와 주소창이 있는 작은 브라우저와 데모 페이지(`../common/demo.py`), `App` |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(`../common/checks.py`). Kivy의 루프를 한 번씩 직접 돌립니다 |

## 환경 (uv)

Kivy wheel이 SDL2를 가져오므로 시스템 패키지가 필요 없습니다(클립보드는 Kivy가 `xsel`을 찾아 씁니다).

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/kivy
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오.

## 실행과 점검

```sh
SDL_VIDEODRIVER=x11 uv run python browser.py [주소 | demo]
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE SDL_VIDEODRIVER=x11 xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
```

## 알아 둘 것

- **CEF의 깨움은 `Clock.schedule_once`로 전달합니다.** `@mainthread`가 쓰는 호출과 같아서 어느 스레드에서나 부를 수 있습니다. 기한도 같은 시계로 잡습니다.
- **Esc는 `exit_on_escape = 0`으로 꺼야 합니다.** Kivy는 기본으로 Esc에서 앱을 끝내는데, Esc는 페이지의 키입니다(`<select>` 팝업을 닫음). `browser.py`가 설정합니다(점검에서 확인함).
- **휠의 이름이 반대입니다.** Kivy의 `scrollup`은 X의 버튼 5(휠을 사용자 쪽으로, 페이지는 아래로)입니다(xdotool로 확인함). 위젯이 부호를 뒤집습니다.
- **입력기는 실제로 이어집니다.** Kivy의 창(SDL2)이 조합 중인 글자(`on_textedit`)와 확정한 글자(`on_textinput`)를 따로 주므로 `ime_set_composition`과 `ime_commit_text`에 대응합니다. 실제 입력기(ibus, fcitx)로는 확인하지 못했고 점검 스크립트는 같은 호출을 직접 부릅니다.
- **복사, 잘라내기, 붙여넣기는 위젯이 직접 처리합니다.** `Ctrl+C`/`Ctrl+X`는 `on_text_selection_changed`의 텍스트를 `Clipboard.copy`로 넣고(잘라내기는 `frame.delete()`), `Ctrl+V`는 `Clipboard.paste`의 텍스트를 `ime_commit_text`로 넣습니다. 일반 텍스트만 다룹니다.
- **드롭**: 다른 프로그램의 텍스트와 파일은 `on_drop_text`, `on_drop_file`로 오고 위치(`x`, `y`, 창 안의 화소, 아래쪽이 +)를 줍니다. `enter`와 `over`를 먼저 보내고 `update_drag_cursor`의 답이 오면 `drop`을 보냅니다(wx 예제에서 한꺼번에 보내면 첫 드롭이 사라진 일이 있어서). 점검 스크립트는 창이 줄 이벤트를 같은 처리 함수에 직접 넣어 확인하고, 다른 프로그램의 실제 XDND 드래그로는 확인하지 않았습니다.
- **드래그**: Kivy에는 드래그를 시작하는 수단이 없으므로 페이지 안의 드래그는 위젯이 직접 중계합니다(Tk, SDL2 예제와 같음). 페이지의 요소를 다른 프로그램으로 끄는 것은 지원하지 않습니다.
- **그리기**: 더러운 사각형을 쓰지 않고 한 프레임을 통째로 올립니다(`blit_buffer`). 텍스처는 `flip_vertical()`로 위아래를 맞춥니다.
- **HiDPI**: `Metrics.density`를 화면 배율로 전하지만 1배만 확인했습니다.
- 마우스 설정 `mouse,disable_multitouch`는 오른쪽 클릭이 붉은 점(다중 터치)이 되지 않게 합니다.
