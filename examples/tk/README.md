# Tkinter에 붙이는 cefweaver (오프스크린 캔버스)

`tkinter.Canvas`에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. 그림은 Pillow(`ImageTk`)로 바꾸어 그립니다.

| 파일 | 내용 |
| --- | --- |
| `ceftk.py` | `CefCanvas`(그리기, 마우스, 휠, 키, 클립보드, 페이지 안의 드래그), `Runtime`(`MessagePump`을 Tk 루프에 연결) |
| `browser.py` | 툴바와 주소창이 있는 작은 브라우저와 데모 페이지(`../common/demo.py`) |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(`../common/checks.py`) |

## 환경 (uv)

uv가 내려받는 CPython 3.13에는 Tk 8.6이 들어 있어 따로 설치할 것이 없습니다.

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/tk
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오.

## 실행과 점검

```sh
uv run python browser.py [주소 | demo]
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
```

## 알아 둘 것

- **CEF의 깨움은 파이프로 Tk에 전달합니다.** `MessagePump`의 `wake`는 CEF의 어느 스레드에서나 불리는데 Tk는 다른 스레드에서 부르는 것이 안전하지 않으므로, 파이프에 한 바이트를 쓰고 `createfilehandler`(Unix)가 Tk 스레드에서 깨어나 `after`로 기한을 잡습니다.
- **복사, 잘라내기, 붙여넣기는 위젯이 직접 처리합니다.** CEF가 하면 Tk 프로세스가 X 선택을 소유한 채 같은 스레드의 CEF가 그 선택을 동기로 읽으려 해서 페이지가 멈춥니다(확인함). `Ctrl+C`/`Ctrl+X`는 `on_text_selection_changed`의 텍스트를 Tk 클립보드에 넣고(잘라내기는 `frame.delete()`), `Ctrl+V`는 Tk 클립보드의 텍스트를 `ime_commit_text`로 넣습니다. 일반 텍스트만 다룹니다.
- **페이지 안의 드래그**(요소를 다른 곳에 놓기)는 위젯이 직접 중계합니다. Tk에는 CEF의 `start_dragging`에 대응하는 시작 수단이 없으므로, `start_dragging`이 `True`를 돌려준 뒤 마우스 이동을 `drag_target_drag_over`로, 놓기를 `drag_target_drop`으로 보냅니다.
- **한계: 다른 프로그램과의 드래그 앤 드롭은 없습니다.** Tk에는 기본 드래그 앤 드롭이 없고 `tkinterdnd2`(tkdnd 확장)로 `TkinterDnD.Tk()`를 만들면 CEF를 시작할 때 `xcb_io.c: Unknown sequence number ... You called XInitThreads`로 프로세스가 중단됩니다(최소 스크립트로 재현: 일반 `tkinter.Tk()`는 괜찮음). 원인은 찾지 못했습니다(확장이 시스템 `libX11`, `libxcb`를 링크하고 있다는 것까지만 확인). 페이지의 요소를 Tk 위젯으로 끄는 것도 지원하지 않습니다.
- **한계: 입력기의 미리보기(preedit)를 Tk가 주지 않습니다.** XIM이 조합을 끝낸 글자는 키 이벤트의 `char`로 오므로 그것은 `ime_commit_text`로 넣지만, 조합 중인 글자는 볼 수 없습니다. 점검 스크립트는 위젯의 `set_preedit`와 `commit_text`를 직접 불러 CEF 쪽만 확인합니다.
- **HiDPI**: Tk는 배율을 주지 않아 1배로 그립니다.
- 위젯 하나에 브라우저 하나입니다.
