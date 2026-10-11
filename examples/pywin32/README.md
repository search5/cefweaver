# Win32 창에 붙이는 cefweaver (pywin32)

Windows의 Win32 창에 cefweaver의 오프스크린 브라우저를 그리는 예제입니다. Win32에는 위젯이 없으므로 `Win32Browser`가 뷰이면서 메시지 루프입니다(툴바 없음). 창과 메시지는 pywin32(`win32gui`, `win32api`, `win32con`, `win32clipboard`)가 맡고, pywin32에 없는 호출 몇 개(`StretchDIBits`, `SetTimer`, `AdjustWindowRectEx`, IME)는 `ctypes`가 맡습니다.

| 파일 | 내용 |
| --- | --- |
| `cefweaver.ui.toolkits.pywin32` (패키지) | `cefweaver.ui` 위의 `Win32Browser`: 어댑터(그리기, 위치, 커서, 클립보드, 컨텍스트 메뉴, `post`와 `call_later`)이자 메시지 루프이고 Win32 메시지를 `BrowserView`에 전합니다 |
| `browser.py` | 데모 페이지가 있는 브라우저. `Alt+←`, `Alt+→`는 뒤로와 앞으로, `F5`는 새로 고침 |
| `smoke.py` | 실제 입력 이벤트(`SendInput`, `../common/winxdo.py`)로 구동해 점검하는 스크립트(`../common/checks.py`) |

## quickstart

Win32 창에 페이지를 띄우는 가장 작은 프로그램입니다(`quickstart.py`). 주소를 인자로 줄 수 있고, 창을 닫으면 브라우저를 먼저 닫은 뒤 끝납니다.

```python
import sys

from cefweaver.ui.toolkits.pywin32 import Win32Browser

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"


class Browser(Win32Browser):                          # the window, the browser and the message loop in one
    def browser_title(self, title):
        super().browser_title(title)
        print("title:", title, flush=True)


browser = Browser()
browser.on_ready = lambda: browser.load_url(URL)
browser.start("about:blank")
browser.run()                                         # until the window is closed
```

## 환경 (uv)

```sh
# 저장소 루트에서 wheel을 만든 뒤 (Windows, CPython 3.13용; Visual Studio의 C++ 빌드 도구가 필요합니다)
uv build --wheel
cd examples\pywin32
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오. 프로젝트의 extras로는 `pip install cefweaver[pywin32]`입니다.

## 실행과 점검

```sh
uv run python browser.py [주소 | demo]
uv run python smoke.py [스크린샷 디렉터리]
```

`smoke.py`는 창을 데스크톱에 열고 실제 마우스와 키보드 입력을 보냅니다. 1분 남짓 걸리는 동안 포인터와 키보드에 손대지 마십시오.

## 알아 둘 것

- **CEF의 깨움은 `PostMessage`로 전달합니다.** 어느 스레드에서나 안전합니다. `call_later`는 가장 이른 시각 하나에 맞춘 `SetTimer`입니다. 둘 다 창 프로시저가 처리하므로, 창 제목 표시줄을 끌거나 팝업 메뉴를 여는 동안(Windows가 자기 루프를 도는 동안)에도 CEF가 계속 돕니다.
- **그림은 GDI `StretchDIBits`로 그립니다.** 마지막 프레임을 버퍼에 두고 바뀐 부분(`dirty_rects`)만 복사합니다. GPU 가속 그림(공유 텍스처)은 쓰지 않습니다.
- **입력기는 `WM_IME_COMPOSITION`으로 이어집니다.** 조합 중인 글자는 `ime_set_composition`에, 확정한 글자는 `ime_commit_text`에 전합니다. 실제 한글 입력기로는 확인하지 못했고, 점검은 같은 `view` 메서드를 직접 부릅니다.
- **끌어서 놓기**: 탐색기에서 파일을 끌어다 놓으면 `WM_DROPFILES`로 받습니다. 텍스트 드롭과 페이지에서 밖으로 끄는 드래그는 OLE가 필요해서 지원하지 않습니다(페이지 안의 드래그는 뷰가 처리합니다).
- **배율**: 프로세스를 창이 생기기 전에 모니터별 DPI 인식(per-monitor v2)으로 바꾸고 `GetDpiForWindow / 96`을 배율로 씁니다. 100%에서만 확인했습니다.
- **소리**: 이 어댑터는 소리 장치가 없습니다. `audio="auto"`이면 `pygame`이 있을 때 그것을 씁니다.
