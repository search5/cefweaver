# Qt에 붙이는 cefweaver (PyQt6와 PySide6)

`QWidget`에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. **같은 코드가 PyQt6와 PySide6에서 모두 동작**합니다(`cefqt.py`가 두 바인딩의 import만 가립니다).

| 파일 | 내용 |
| --- | --- |
| `cefqt.py` | `cefweaver.ui` 위의 어댑터: `QtAdapter`(그리기, 위치, 커서, 클립보드, 후보 창, `QDrag` 시작), `QtLoop`(`post`, `call_later`), `CefWidget`(Qt 이벤트를 `BrowserView`에 전함), `Runtime`(`ui.Session`) |
| `browser.py` | 툴바와 주소창이 있는 작은 브라우저와 데모 페이지(`../common/demo.py`) |
| `smoke.py` | 실제 X 이벤트(xdotool)로 구동해 점검하는 스크립트(`../common/checks.py`) |

## 환경 (uv)

```sh
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/qt
uv sync --python 3.13 --extra pyqt                                            # PyQt6
UV_PROJECT_ENVIRONMENT=.venv-pyside uv sync --python 3.13 --extra pyside      # PySide6 (환경을 따로 둡니다)
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver ...`를 실행하십시오(`uv.lock`에 이전 wheel의 해시가 있습니다. `uv.lock`은 저장소에 넣지 않습니다).

## 실행

```sh
uv run python browser.py                                       # PyQt6, 데모 페이지
CEFQT_BINDING=pyside6 .venv-pyside/bin/python browser.py       # PySide6
```

## 점검

```sh
CEFQT_BINDING=pyqt6   env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE QT_QPA_PLATFORM=xcb xvfb-run -a -s "-screen 0 1280x1024x24" .venv/bin/python smoke.py [스크린샷 디렉터리]
CEFQT_BINDING=pyside6 env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE QT_QPA_PLATFORM=xcb xvfb-run -a -s "-screen 0 1280x1024x24" .venv-pyside/bin/python smoke.py
QT_SCALE_FACTOR=2 ...   # HiDPI
```

**`QT_QPA_PLATFORM=xcb`를 꼭 주십시오.** Qt는 `xvfb-run` 안에서도 `WAYLAND_DISPLAY`를 지우는 것만으로는 실행 중인 Wayland 세션에 연결해 실제 화면에 창을 엽니다(이 기기에서 확인함).

## 알아 둘 것

- **복사와 잘라내기는 위젯이 직접 처리합니다.** CEF가 처리하면 CEF가 X 선택의 소유자가 되는데, Qt는 선택을 동기로 읽어서 같은 프로세스의 CEF가 응답할 틈이 없어 막힙니다(GTK는 대기 중에도 메인 루프를 돌려 괜찮았습니다). 그래서 `BrowserView`가 `Ctrl+C`와 `Ctrl+X`를 `on_text_selection_changed`의 텍스트로 Qt 클립보드에 넣고(잘라내기는 `frame.delete()`), `Ctrl+V`는 Qt 클립보드의 텍스트를 `ime_commit_text`로 넣습니다. `cefweaver.ui`로 옮기기 전에는 붙여넣기를 CEF에 맡겼으므로, 이제 붙여넣기는 일반 텍스트만 다룹니다.
- **드래그 앤 드롭**: Qt는 드롭 대상에 데이터를 바로 줍니다(`QMimeData`). `QDrag.exec()`는 드래그가 끝날 때까지 이벤트 루프를 막으므로 `start_dragging`에서는 타이머로 미루어 CEF의 호출 밖에서 시작합니다. 점검 스크립트도 마우스를 놓는 `xdotool`을 별도 스레드에서 보냅니다.
- **HiDPI**: `devicePixelRatioF()`를 CEF의 화면 정보로 주고 `QImage.setDevicePixelRatio`로 그립니다.
- 실제 입력기(ibus, fcitx)로는 확인하지 않았습니다(가상 X 서버에 없음). `inputMethodEvent`의 `commitString`과 `preeditString`을 `ime_commit_text`와 `ime_set_composition`으로 잇습니다.
