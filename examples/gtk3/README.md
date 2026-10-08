# GTK 3에 붙이는 cefweaver (오프스크린 위젯)

`Gtk.DrawingArea`에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. 창을 심는 방식(`SetAsChild`)이 아니라 CEF가 준 픽셀을 cairo로 그리므로 Wayland에서도 같은 방식으로 동작합니다.

| 파일 | 내용 |
| --- | --- |
| `cefgtk.py` | `CefWidget`(그리기, 마우스, 휠, 키, 입력기), `Runtime`(`MessagePump`를 GLib 메인 루프에 연결) |
| `browser.py` | 툴바와 주소창이 있는 작은 브라우저, 데모 페이지, `JavascriptBridge` 함수 |
| `smoke.py` | 실제 X 이벤트(xdotool)로 위젯을 구동해 점검하는 스크립트 |

## 환경 (uv)

Ubuntu에서 PyGObject를 소스에서 빌드하므로 개발 패키지가 필요합니다.

```sh
sudo apt install libgirepository-2.0-dev libcairo2-dev gir1.2-gtk-3.0 pkg-config xdotool xvfb   # xdotool, xvfb는 smoke.py용

# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/gtk3
uv sync --python 3.13
```

`pyproject.toml`이 `../../dist/` 의 wheel을 가리킵니다. **wheel을 다시 만들었으면** `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오(`uv.lock`에 이전 wheel의 해시가 있어 그냥 `uv sync`는 "Hash mismatch"로 멈춥니다. `uv.lock`은 기기마다 다르므로 저장소에 넣지 않습니다).

## 실행

```sh
uv run python browser.py                    # 데모 페이지 (주소창에 demo)
uv run python browser.py https://example.org/
CEFGTK_SWITCHES="name=value;name=value" uv run python browser.py   # Chromium 스위치
```

## 점검

```sh
env -u WAYLAND_DISPLAY xvfb-run -a -s "-screen 0 1280x1024x24" uv run python smoke.py [스크린샷 디렉터리]
GDK_SCALE=2 env -u WAYLAND_DISPLAY xvfb-run -a -s "-screen 0 2560x2048x24" uv run python smoke.py   # HiDPI
```

화면에 창을 열지 않고 가상 X 서버에서만 돕니다. 끝에 `ALL OK`가 나오고 종료 코드가 0이면 통과입니다.

## 입력기와 한글

`Gtk.IMMulticontext`의 `commit`과 `preedit-changed`가 `ime_commit_text`와 `ime_set_composition`으로 이어집니다. 실제 한글 입력기(ibus, fcitx)가 있는 데스크톱에서 그대로 동작하도록 만들었으나, 가상 X 서버에는 입력기가 없어서 점검 스크립트는 같은 호출(`set_preedit`, `commit_text`)을 직접 부릅니다.

## 한계

- 위젯 하나에 브라우저 하나(`initialize()`가 만드는 것)입니다. 더 필요하면 `CefApp.create_browser()`와 위젯을 늘립니다.
- 복사, 붙여넣기와 드래그 앤 드롭은 GTK 클립보드와 잇지 않았습니다.
- GPU 가속(공유 텍스처)은 쓰지 않고 CPU 버퍼(`on_paint`)를 cairo에 복사합니다.
