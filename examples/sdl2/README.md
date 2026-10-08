# SDL2에 붙이는 cefweaver (PySDL2)

SDL2 창에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. SDL은 창, 이벤트, 텍스처만 주고 위젯이 없으므로 `SdlBrowser`가 뷰이면서 이벤트 루프입니다(툴바 없음).

| 파일 | 내용 |
| --- | --- |
| `cefweaver.ui.toolkits.sdl2` (패키지) | `cefweaver.ui` 위의 `SdlBrowser`: 어댑터(그리기, 위치, 커서, 클립보드, `post`와 `call_later`)이자 이벤트 루프이고 SDL 이벤트를 `BrowserView`에 전합니다 |
| `browser.py` | 데모 페이지가 있는 브라우저. `Alt+←`, `Alt+→`는 뒤로와 앞으로, `F5`는 새로 고침 |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(`../common/checks.py`) |

## 환경 (uv)

`pysdl2-dll`이 SDL2와 SDL2_image를 가져오므로 시스템 패키지가 필요 없습니다.

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/sdl2
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오.

## 실행과 점검

```sh
uv run python browser.py [주소 | demo]
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE SDL_VIDEODRIVER=x11 xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
```

`SDL_VIDEODRIVER=x11`로 고정합니다(점검 스크립트는 실행한 드라이버가 `x11`인지 확인합니다).

## 알아 둘 것

- **CEF의 깨움은 `SDL_PushEvent`로 전달합니다.** 이것은 어느 스레드에서나 안전합니다. 루프는 `SDL_WaitEventTimeout`으로 이벤트나 CEF가 요청한 시각까지 기다립니다(폴링 없음).
- **입력기는 실제로 이어집니다.** SDL이 조합 중인 글자(`SDL_TEXTEDITING`)와 확정한 글자(`SDL_TEXTINPUT`)를 따로 주므로 `ime_set_composition`과 `ime_commit_text`에 그대로 대응합니다. 실제 입력기(ibus, fcitx)로는 확인하지 못했고(가상 X 서버에 없음) 점검 스크립트는 같은 호출을 직접 부릅니다.
- **CEF의 포커스는 클릭할 때 다시 줍니다.** `on_after_created` 안에서 준 `set_focus(True)`만으로는 한글 조합과 `<select>` 팝업이 동작하지 않았고(확인함), 클릭에서 `set_focus(True)`를 주니 동작했습니다. 원인은 조사하지 않았습니다.
- **복사, 잘라내기, 붙여넣기는 루프가 직접 처리합니다.** SDL이 X 선택 요청에 답하는 것도 이 스레드라서, CEF가 같은 프로세스의 선택을 읽으면 아무도 답할 수 없습니다(Tk에서 확인한 것과 같은 종류). `Ctrl+C`/`Ctrl+X`는 `on_text_selection_changed`의 텍스트를 `SDL_SetClipboardText`로 넣고, `Ctrl+V`는 `SDL_GetClipboardText`를 `ime_commit_text`로 넣습니다. 일반 텍스트만 다룹니다.
- **드롭**: 다른 프로그램의 텍스트와 파일은 `SDL_DROPTEXT`, `SDL_DROPFILE`로 옵니다. SDL은 놓은 **위치를 주지 않으므로** 그때의 포인터 위치를 씁니다. `BrowserView.drop()`이 `dragover`의 답을 기다린 뒤 놓습니다. 점검 스크립트는 텍스트 드롭을 같은 처리 함수에 직접 넣어 확인하고, 다른 프로그램의 실제 XDND 드래그로는 확인하지 않았습니다.
- **드래그**: SDL은 드래그를 시작할 수 없으므로 페이지 안의 드래그는 루프가 직접 중계합니다(Tk 예제와 같음). 페이지의 요소를 다른 프로그램으로 끄는 것은 지원하지 않습니다.
- **그리기**: 소프트웨어 렌더러(`SDL_RENDERER_SOFTWARE`)와 `SDL_UpdateTexture`로 dirty rect만 올립니다. HiDPI는 렌더러 출력 크기와 창 크기의 비로 배율을 정하지만 X11에서는 SDL이 배율을 주지 않아 1배만 확인했습니다.
