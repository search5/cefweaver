---
title: 앱을 PyInstaller와 cx_Freeze로 묶기
type: procedure
sources:
  - cefweaver/__init__.py
  - native/cefwrapper/library.cpp
  - pyproject.toml
  - setup.py
  - cefweaver/ui/toolkits/tk.py
  - cefweaver/ui/toolkits/qt.py
  - cefweaver/ui/toolkits/gtk3.py
  - cefweaver/ui/toolkits/sdl2.py
  - cefweaver/ui/toolkits/wx.py
updated: 2026-10-09
---

# 앱을 PyInstaller와 cx_Freeze로 묶기

cefweaver로 만든 앱을 파이썬이 없는 기계에 배포하려고 동결 도구로 묶을 수 있는지 실험했습니다. 결과는 [F93](../reference/verified-findings-handlers.md)에 있고, 이 페이지는 재현하는 방법과 도구별 차이를 정리합니다. 실험한 환경은 Linux x86_64, Python 3.13.11, CEF 154, PyInstaller 6.22.3, cx_Freeze 8.7.1입니다. **py2exe와 Windows는 실험하지 못했습니다**([알려진 제약](../reference/known-constraints.md)).

## 왜 그냥 되지 않는가

[런타임 파일 배치](../concepts/runtime-layout.md)의 조건이 동결본에서도 그대로 필요합니다. `libcef.so`, `icudtl.dat`, `.pak` 파일, `locales/`, `cefsubprocess`가 확장 모듈과 **같은 디렉터리**(동결본의 `cefweaver/`)에 있어야 합니다. 동결 도구는 파이썬 모듈과 `.so` 의존성만 자동으로 따라가므로, 자동 수집에 맡기면 이 조건을 채우지 못합니다.

## PyInstaller

설정 없이 `pyinstaller app.py`만 실행하면 **실행할 때 죽습니다.** 확장 모듈의 의존성인 `libcef.so`만 수집하고(시스템 라이브러리 79개도 함께 `_internal/`에 묶임) `libvk_swiftshader.so`, `libvulkan.so.1`, `icudtl.dat`, `.pak`, `locales/`, `cefsubprocess`는 빠져서, CEF 초기화 중에 `Invalid file descriptor to ICU data received`를 내고 `Trace/breakpoint trap`(종료 코드 133)으로 끝났습니다.

`--collect-all cefweaver`를 주면 해결됩니다.

```sh
pyinstaller --noconfirm --collect-all cefweaver app.py                # onedir, 약 451MB
pyinstaller --noconfirm --onefile --collect-all cefweaver app.py      # onefile, 약 188MB(실행 파일 하나)
```

- 수집된 `_internal/cefweaver/`에 CEF 파일 11개와 `cefsubprocess`(실행 권한 유지)가 모두 들어갑니다. `.pyx`, `.pxd`, `.pyi` 같은 원본도 함께 들어가지만 동작에는 필요하지 않습니다.
- `_internal/libcef.so`는 `cefweaver/libcef.so`로 가는 심볼릭 링크이고 파일은 하나입니다.
- onefile은 실행할 때마다 `/tmp/_MEIxxxx`에 풀고 끝나면 지웁니다(5회 실행 뒤 남은 `_MEI*` 디렉터리 없음). 실행당 약 1.9초가 걸렸고, 이 시간에는 풀어내는 시간이 포함됩니다.
- **Tk 어댑터(`cefweaver.ui.toolkits.tk`)는 `--hidden-import PIL._tkinter_finder`가 더 필요합니다.** 없으면 `ModuleNotFoundError: No module named 'PIL._tkinter_finder'`가 Tk 콜백 안에서 나서 페이지가 그려지지 않고, 창은 뜨지만 아무 일도 일어나지 않다가 제한 시간에 끝납니다. 이는 Pillow와 PyInstaller의 알려진 조합 문제이며 cefweaver와는 무관합니다.

## cx_Freeze

**설정 없이** 됩니다.

```sh
cxfreeze --script app.py --target-dir out      # 약 402MB
```

`lib/cefweaver/`에 CEF 파일 11개와 `cefsubprocess`가 모두 들어가고 `locales/`(220개 파일)도 따라옵니다. 모듈은 `.pyc`로 들어갑니다. Tk 예제도 추가 설정 없이 동작했습니다(Pillow를 설치했다면).

## 공통

- 동결 여부와 무관하게 `cefweaver.__file__`을 기준으로 한 모듈 디렉터리 찾기(`__init__.py`의 `_package_dir`, `library.cpp`의 `ModuleDir()`)가 맞게 동작했습니다. 그래서 `set_subprocess_path()`를 따로 부를 필요가 없었습니다.
- 현재 작업 디렉터리와 상관없이 동작합니다(`/`에서 실행). 빌드 결과를 다른 경로로 복사해도 동작합니다.
- Python이 없는 기계에서의 동작은 **확인하지 못했습니다.** 실험은 빌드한 기계에서 했고, 두 도구 모두 해당 파이썬의 표준 라이브러리를 묶어 넣으므로 가능할 것으로 보이지만 시험하지 않았습니다.

## 동결본에서 예제의 점검(`smoke.py`) 돌리기

각 `examples/<툴킷>/smoke.py`는 가상 X 서버에서 xdotool로 실제 X 이벤트를 보내 입력, 클립보드, 드래그 앤 드롭, 한글 조합(IME 호출), 메뉴, 소리, 종료를 점검합니다(28~39개). 이것 자체를 두 도구로 묶어 실행했습니다.

```sh
E=examples
PYTHONPATH=$E/common:$E/<툴킷>:$E/<툴킷>/.venv/lib/python3.13/site-packages \
  pyinstaller --noconfirm --collect-all cefweaver $E/<툴킷>/smoke.py      # 또는 cxfreeze --script ... --target-dir out
cd $E/<툴킷> && env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE <툴킷 환경 변수> \
  xvfb-run -a -s "-screen 0 1280x1024x24" <동결된 smoke>
```

- `smoke.py`는 `sys.path`에 `../common`을 넣고 `browser`, `checks`를 가져오는데, 두 도구 모두 `PYTHONPATH`로 그 폴더를 알려 주면 정적으로 찾아 묶습니다(`HERE` 기준 경로는 동결본에서 없어도 영향이 없었습니다). 일반 실행도 README처럼 `-P` **없이** 해야 합니다(`-P`는 스크립트 폴더를 경로에서 빼서 `browser`를 찾지 못합니다).
- **xdotool은 시스템 프로그램이라 묶이지 않습니다.** 실행하는 기계에 있어야 합니다.
- 합격 기준: 종료 코드 0, `ALL OK`, 통과한 점검(`ok` 줄) 수가 동결하지 않은 실행과 같음, `stack smashing` 없음.

| 툴킷 | 점검 수 | cx_Freeze | PyInstaller |
| --- | --- | --- | --- |
| Tk | 30 | 통과 | 통과 |
| SDL2 | 28 | 통과 | 통과 |
| GTK 3 | 39 | 통과 | 통과 |
| Qt (PyQt6) | 35 | 통과 | 통과 |
| Qt (PySide6) | 35 | 6회 중 1회 실패(아래) | 통과 |
| wxPython | 33 | 통과 | **8회 중 2회 실패(아래)** |

위 표는 한 번씩 돌린 결과이고, 실패한 조합은 반복했습니다. 클립보드, 드래그, 메뉴, 소리, 한글 조합 호출을 포함한 점검이 동결본에서도 그대로 통과했습니다. 단 한글 조합은 실제 입력기가 아니라 `ime_*` 호출을 직접 부르는 점검이고, 이는 동결하지 않았을 때와 같습니다.

**간헐적 실패 두 건 (원인 조사하지 않음)**

- wxPython + PyInstaller: `the menu stays open after the button was released`가 8회 중 2회 실패했습니다(값 `[True, True, False]`). 같은 점검이 동결하지 않은 실행에서는 8회 모두 통과했고, wxPython + cx_Freeze는 1회 통과했습니다.
- Qt(PySide6) + cx_Freeze: `the device plays it as fast as it comes`가 6회 중 1회 실패했습니다(`underruns: 4`, `dropped: 0`). 동결하지 않은 실행은 6회 모두 통과했습니다. 소리 장치의 타이밍에 민감한 점검입니다.
- 표본이 작아서 동결이 원인인지, 원래 있던 드문 경합이 동결로 드러난 것인지 가를 수 없습니다. 위키에 이전의 실패 기록은 없었습니다.

## 오프스크린, MessagePump, JavascriptBridge (툴킷 없이)

창이 없는 `CefApp` 사용도 묶었습니다. 앱은 `app.offscreen = True`와 `RenderHandler.on_paint`, `MessagePump`(직접 만든 루프에서 `pump.run()`), `JavascriptBridge`(`expose`한 함수를 페이지가 `await`로 부름, `bridge.evaluate`로 `6*7` 계산)를 모두 쓰고, 빨간 배경 페이지의 첫 픽셀(BGRA `0,0,255,255`), 브리지 호출 결과 3, `evaluate` 결과 42를 받으면 종료 코드 0으로 끝납니다. 일반 `python`, PyInstaller onedir(509MB)와 onefile(201MB), cx_Freeze(402MB)가 모두 **5회 중 5회** 같은 결과를 냈고 `stack smashing`은 없었습니다. 옵션은 앞서와 같습니다(PyInstaller는 `--collect-all cefweaver`, cx_Freeze는 없음).

## 새 빌드에서 다시 확인 (setup.py 기반, macOS 지원 병합 뒤)

`2a2f4d2`(macOS arm64 지원, 확장 모듈 선언을 `setup.py`로 이동, 네이티브 코드 변경)를 병합한 뒤 `prepare.py`와 `uv build --wheel --python 3.13`으로 wheel을 새로 만들고(빌드 성공), 그 wheel만 담은 새 환경에서 같은 실험을 반복했습니다(2026-10-10). 새 코드임은 `CefApp.parent_view`가 있는 것으로 확인했습니다.

- **툴킷 없는 CEF**: 최소 앱과 오프스크린, `MessagePump`, `JavascriptBridge` 앱이 PyInstaller onedir, onefile, cx_Freeze 모두 **5회 중 5회**, 이전과 같은 값으로 통과했습니다. 크기도 비슷했습니다(onedir 452MB, onefile 180MB, cx_Freeze 403MB).
- **옵션 없는 PyInstaller는 여전히 실패합니다.** 같은 `Invalid file descriptor to ICU data received`, 종료 코드 133. `--collect-all cefweaver`가 필요한 것도 같습니다.
- **툴킷 다섯 개(GTK 3, PyQt6, PySide6, SDL2, wxPython)와 Tk**: PyInstaller(`--collect-all cefweaver`)와 cx_Freeze(옵션 없음) 모두 **3회 중 3회** 창을 열고 제목을 받고 정상 종료했습니다. Tk의 PyInstaller만 `--hidden-import PIL._tkinter_finder` 없이는 실패하고(`No module named 'PIL._tkinter_finder'`), 추가하면 3회 통과합니다. 이전 기록과 같습니다.
- **다시 하지 않은 것**: 예제의 `smoke.py` 점검, onefile의 툴킷 조합, macOS. 크기는 일부 툴킷의 PyInstaller 결과가 이전보다 작게 나왔는데(예: PyQt6 960MB에서 632MB), 이번에는 예제 환경의 패키지를 옛 `cefweaver`만 뺀 링크 디렉터리로 넘겼기 때문일 수 있고 원인은 조사하지 않았습니다.

## 툴킷별 결과

`cefweaver.ui`의 다섯 어댑터를 각각의 예제 환경(`examples/<툴킷>/.venv`)으로 묶어 실행했습니다. 앱은 `examples/<툴킷>/quickstart.py`와 같은 구조에서 `data:` 페이지의 제목(`frozen-ok`)을 받으면 0.3초 뒤 정상 종료하게 한 것입니다. 모든 조합이 **3회 중 3회**, 종료 코드 0과 `stack smashing` 없이 통과했습니다. PyInstaller는 `--collect-all cefweaver`만, cx_Freeze는 **옵션 없이** 묶었습니다(Tk의 `PIL._tkinter_finder` 같은 추가 설정이 필요한 곳은 없었습니다).

| 툴킷 | PyInstaller (onedir) | cx_Freeze | 비고 |
| --- | --- | --- | --- |
| Tk (Pillow) | 509MB, `--hidden-import PIL._tkinter_finder` 필요 | 500MB | |
| GTK 3 (PyGObject) | 1.2GB | 528MB | PyInstaller는 `gi_typelibs`(15개)와 GTK 라이브러리를 묶음. cx_Freeze는 typelib과 GTK를 묶지 않고 **시스템의 GTK 3를 씀** |
| Qt (PyQt6) | 960MB | 544MB | |
| Qt (PySide6) | 962MB | 549MB | |
| SDL2 (pysdl2-dll) | 787MB | 417MB | SDL2 라이브러리는 `pysdl2-dll`이 주므로 두 도구 모두 함께 묶임 |
| wxPython | 1.1GB | 858MB | PyInstaller는 `libgtk-3.so.0`을 묶고 cx_Freeze는 묶지 않음 |

- **cx_Freeze가 더 작고 옵션이 필요 없지만, GTK 3와 wxPython에서는 시스템의 GTK 3에 기대므로** 설치되지 않은 기계에서는 동작하지 않을 수 있습니다(시험하지 않음). PyInstaller는 빌드한 기계의 라이브러리를 묶어서 그 점에서는 더 독립적이지만 크기가 큽니다.
- Qt는 어느 바인딩이든 어댑터가 `BINDING`으로 고른 값(`pyqt6`, `pyside6`)이 동결본에서도 같았습니다. 한 환경에 두 바인딩이 함께 있을 때의 선택은 시험하지 않았습니다.
- 실행 환경 변수는 동결하지 않았을 때와 같습니다(`QT_QPA_PLATFORM=xcb`, `GDK_BACKEND=x11`, `SDL_VIDEODRIVER=x11`). 동결본이 이 값을 대신 정해 주지는 않습니다.
- 위 표는 창을 열고 제목을 받고 종료하는 데까지의 확인입니다. 입력과 클립보드 같은 동작은 아래 "동결본에서 예제의 점검 돌리기"에서 따로 확인했습니다.
- 이 빌드는 예제 환경의 `site-packages`를 `PYTHONPATH`로 준 별도 환경의 도구로 만들었습니다(예제 환경에는 도구를 설치하지 않음).

## 점검에 쓴 최소 앱

페이지를 `add_resource`로 제공하고, 로드 이벤트와 JavaScript 바인딩 호출을 받으면 종료 코드 0으로 끝납니다.

```python
import sys, tempfile, time
import cefweaver

got = []
class Load(cefweaver.LoadHandler):
    def on_load_end(self, browser, frame, http_status_code):
        if frame.is_main():
            got.append(("loaded", http_status_code))

class MyClient(cefweaver.Client):
    def __init__(self):
        self.load = Load()
    def get_load_handler(self):
        return self.load

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp(prefix="frz-"))
app.add_command_line_switch("ozone-platform", "x11")
app.add_javascript_binding("report", lambda *a: got.append(("js", a)))
app.set_client(MyClient())
app.initialize("about:blank")
app.add_resource("http://app.test/index.html",
    "<html><body><script>window.report('hello', 1+2)</script>ok</body></html>")
app.load_url("http://app.test/index.html")
end = time.time() + 30
while time.time() < end and not (("loaded", 200) in got and any(g[0] == "js" for g in got)):
    app.do_message_loop_work(); time.sleep(0.005)
app.shutdown()
sys.exit(0 if ("loaded", 200) in got and any(g[0] == "js" for g in got) else 1)
```

실행은 `env -u WAYLAND_DISPLAY xvfb-run -a <실행 파일>`로 하고, 합격 기준은 종료 코드 0, `loaded 200`과 `js ('hello', 3)`, stderr에 `stack smashing`이 없는 것입니다. 일반 `python`으로 실행한 결과와 같은 값이 나와야 합니다.

## 한계

- **디스크 용량**: 결과물이 0.4~1.2GB이므로 여러 번 빌드하면 용량 한도에 걸립니다. 빌드 도중 `Disk quota exceeded`로 cx_Freeze가 **오류 메시지만 남기고 종료 코드 0으로 끝나** 불완전한 결과물(200MB, 실행 실패)을 만든 적이 있습니다. 빌드 로그의 `error:`와 결과물 크기를 확인하십시오.
- 크기: 어떤 방식이든 CEF가 약 340MB를 차지해서 onedir는 400~500MB입니다. onefile은 압축되어 약 188MB이지만 매번 풀어냅니다.
- 이 실험은 Linux x86_64에서 한 것이고 빌드한 기계에서 실행했습니다. 다른 배포판(glibc 버전)에서의 동작은 확인하지 못했습니다. PyInstaller는 빌드한 기계의 시스템 라이브러리(`libX11`, `libasound` 등 79개)를 `_internal/`에 함께 묶고, cx_Freeze는 묶지 않으므로(`libX11`, `libgtk`, `libasound`가 결과에 없음) 두 도구의 이식성은 다를 수 있습니다.

## 관련 페이지

- [런타임 파일 배치](../concepts/runtime-layout.md)
- [패키징](../components/packaging.md)
- [빌드와 설치](build-and-install.md)
- [플랫폼 지원 현황](../concepts/platform-support.md)
