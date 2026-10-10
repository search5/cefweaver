---
title: 실행해서 확인한 macOS (F79부터)
type: reference
sources:
  - setup.py
  - tools/prepare.py
  - tools/gen/model.py
  - native/cefwrapper/mac_runtime.mm
  - native/cefwrapper/platform_structs.h
  - native/cefsubprocess/CMakeLists.txt
  - tests/test_smoke.py
  - tests/test_ui.py
  - tests/test_generator.py
  - cefweaver/ui/keys.py
  - cefweaver/ui/view.py
  - examples/cocoa/quickstart.py
updated: 2026-10-10
---

# 실행해서 확인한 macOS (F79부터)

macOS arm64 지원을 추가하며 실행해서 확인한 사실입니다. 환경은 Apple Silicon(M1), macOS 26.6.2, Xcode의 Apple clang, Homebrew의 cmake 4, uv가 받은 Python 3.14.3입니다. CEF는 `154.0.34+g14c5a08+chromium-154.0.8037.98`의 `macosarm64` 표준 배포본(SHA1 `b7e1bc1c...`, 압축 약 307 MB)입니다. 앞의 항목은 [실행해서 확인한 미디어](verified-findings-media.md)에 있습니다.

## F79. 빌드

- **확인함**: `python tools/prepare.py --cef-root <배포본>`이 끝까지 됩니다. CEF의 mac 컴파일 플래그에 `-Werror -Wall -Wextra`가 있는데 래퍼 코드가 경고 없이 컴파일됐습니다. 도우미 앱 5개(`cefsubprocess Helper`, `(Alerts)`, `(GPU)`, `(Plugin)`, `(Renderer)`)가 만들어지고 모두 ad hoc 서명입니다(CEF 프레임워크도 같음).
- **확인함**: `uv build --wheel`이 `cefweaver-0.1.0-cp314-cp314-macosx_13_0_arm64.whl`(147 MB)을 만듭니다. 안에 `cefsubprocess.app`의 파일 243개가 들어 있고 프레임워크 본체와 도우미의 실행 권한(0755)이 유지됩니다. 배치한 `cefsubprocess.app`은 약 325 MB입니다.
- **확인함**: CEF 154의 mac 프레임워크는 평평한 구조(`Versions/`와 심볼릭 링크 없음)입니다. 그래서 wheel(zip)에 그대로 담을 수 있습니다.
- **함정**: `python.org`의 Python 3.14로 `prepare.py --list-versions`를 부르면 `CERTIFICATE_VERIFY_FAILED`로 실패합니다(그 Python에 인증서 번들이 없음). 검증을 끄지 않고 `curl https://cef-builds.spotifycdn.com/index.json`으로 조회했습니다. `--cef-root`를 주면 이 경로를 쓰지 않습니다.

## F80. 구동

- **확인함**: 설치한 wheel에서 `import cefweaver`가 프레임워크를 올리고 `cef_api_hash()`가 맞는 채로 끝납니다(`get_version()`이 154.0.34를 돌려줌). 오프스크린 브라우저가 0.3초 안에 초기화되고 1초쯤에 첫 프레임이 옵니다. 빨간 페이지의 첫 픽셀이 `00 00 ff ff`(BGRA)이고, 페이지의 JavaScript가 Python 바인딩을 부르고, `shutdown()`이 종료 코드 0으로 끝납니다. stderr에 아무것도 없고 도우미 프로세스가 남지 않았습니다.
- **확인함**: `NSApplication`이 없는 순수 Python 프로세스에서 `CefWeaverPrepareApplication()`이 만든 `NSApp`으로 동작합니다. Tk(자체 `NSApplication` 서브클래스)에서도 `Session`과 `CefCanvas`가 페이지를 그리고 제목이 전달되고 정상 종료합니다(`examples/tk/quickstart.py`와 같은 구성, 6초 뒤 자동 종료).
- **확인함**: 네이티브 창 모드(오프스크린이 아닌 `CefApp`)도 창을 열고 JavaScript 바인딩이 불리고 종료합니다(창 모드 시험 4개 중 3개 통과, 1개는 `xwininfo`가 필요해 건너뜀).

## F81. 시험 결과

최종 상태(arm64, Python 3.14.3, 설치한 wheel)입니다(당시 값). 창을 여는 시험까지 모두 돌렸습니다.

| 파일 | 결과 |
| --- | --- |
| `test_generator.py` | 122개 통과(건너뜀 1) |
| `test_docs.py` | 15개 통과(건너뜀 1) |
| `test_ui.py` | 164개 통과(건너뜀 5) |
| `test_smoke.py` | 194개 통과(건너뜀 9, 예상된 실패 3). `CEFWEAVER_TEST_COCOA=1`로 Cocoa 창 시험 포함. 약 3분 |
| `test_wiki.py` | 1개 실패: `offscreen-rendering.md`가 다른 컴퓨터의 경로(`/home/jiho/...`)를 링크함(이번 변경과 무관) |

- 처음 돌렸을 때(창을 열지 않는 106개 + 창 모드 4개) 5개가 실패했고 모두 F82의 플랫폼 차이이거나 Linux를 전제한 시험이었습니다. 이어서 창 모드 41개를 돌려 2개가 더 실패했습니다: `do_close`(F88에서 수정, 시험은 이제 통과)와 Ctrl+클릭 수식어(F82, 시험을 macOS에서 Alt로 바꿈).
- `test_smoke.py` 전체를 5번 돌려 1번 `test_the_request_context_handler_is_asked_about_the_requests_of_its_browser`가 한 번 실패했고, 그 시험은 단독으로 3/3, 전체로 2/2 통과했습니다. 일시적이었던 것으로 보지만 **원인은 확인하지 못했습니다.**
- 종료가 5초씩 걸리던 것이 0.06초로 줄어(F87, F88) 전체 시간이 394+390초에서 약 180초가 되었습니다.
- 건너뛰는 시험(macOS): Wayland 2, GPU 공유 텍스처 2, `xwininfo` 1, libX11 1, 인쇄 1, 호스트에 직접 키 이벤트를 보내는 시험 1(F85), 그 밖의 환경 조건.

## F82. macOS에서 Linux와 다른 동작

| 관찰 | 처리 |
| --- | --- |
| Ctrl+클릭은 오른쪽 클릭으로 해석됩니다(`menu_manager.cc: Default context menu implementation is not available`). 새 탭은 Command+클릭입니다. | 시험이 macOS에서 `EVENTFLAG_COMMAND_DOWN`(128)을 줍니다 |
| **편집 키(Backspace, 화살표, Delete)는 `native_key_code`(mac 가상 키코드)가 있어야 동작합니다.** Windows 키코드만 주면 글자는 들어가도 편집 키는 무시됩니다(`abc` 뒤 Backspace가 `abc`로 남음). 키코드(51, 123, 117)를 주면 동작합니다. | `cefweaver.ui`가 채움(F85). 호스트 API를 직접 쓰는 시험은 건너뜀 |
| **KEYUP에 `character`가 없으면 Cocoa가 그 이벤트를 key down으로 취급합니다.** 페이지에 가짜 keydown(`Unidentified`나 같은 키 한 번 더)이 가고 편집 키는 한 번 더 편집됩니다. 처음에는 "KEYUP이 편집을 반복한다"고 잘못 읽었습니다. | `cefweaver.ui`가 채움(F85) |
| 기본 컨텍스트 메뉴에 뒤로와 앞으로가 없고 `113`(`MenuId`에 이름이 없는 값)만 옵니다. 항목을 고르면 CEF가 실행하는 것(`SELECT_ALL`)은 됩니다. | 시험이 macOS에서 `BACK`, `FORWARD` 검사를 뺌 |
| 맞춤법은 `NSSpellChecker`로 검사해서 틀린 단어(`teh`)의 추천 단어가 오지 않았습니다(`NSSpellServer dataFromCheckingString timed out`). | 건너뜀. 원인 미조사 |
| `host.print()`가 90초 안에 끝나지 않습니다(시작, 설정, 끝이 오지 않음). | 건너뜀. 원인 미조사 |
| `root_cache_path` 아래에 `cache_path`로 준 `profile/` 폴더가 만들어지지 않습니다(`Local State`와 `Default/`는 만들어짐). | 그 검사만 macOS에서 뺌. 원인 미조사 |
| 창 제목(`PlatformTitleChange`)은 `NSWindow.title`로 확인했습니다(F92). 시험은 `xwininfo`를 쓰는 것이라 macOS에서 건너뜀 | |

## F83. 생성기가 어느 플랫폼의 헤더로 돌려도 같은 파일을 만든다

- 문제: CEF는 `cef_accelerated_paint_info_t`를 플랫폼마다 다르게 정의하고(`cef_types_linux.h`, `_mac.h`, `_win.h`) 배포본에는 자기 플랫폼의 헤더만 있습니다. macOS 배포본으로 생성기를 돌리면 공유 텍스처 구조체와 `on_accelerated_paint`가 파일에서 사라졌습니다. 또 커밋된 생성 파일을 macOS에서 컴파일하면 `plane_count`, `planes` 멤버가 없다는 오류와 `cef_window_handle_t`(Linux는 `unsigned long`, macOS는 `void*`) 대입 오류가 났습니다.
- 수정: Linux 정의를 생성기에 내장하고(`tools/gen/model.py`의 `LINUX_STRUCT_BODIES`), 생성 코드는 플랫폼 중립 형식(`CwAcceleratedPaintInfo`, `native/cefwrapper/platform_structs.h`)을 거치게 했습니다. 창 핸들 typedef는 CEF의 C 형식을 그대로 쓰도록 `extern` 블록에서 선언합니다.
- **확인함**: 같은 생성기로 macOS 배포본과 Linux x86_64 `minimal` 배포본(같은 154.0.34, 헤더만 사용) 양쪽에서 `python tools/gen/generate.py --check`가 `up to date`입니다. 수정 전의 Linux 헤더 기준 출력과 비교해 바뀐 것은 이름 몇 개와 변환 호출 한 줄뿐입니다.
- **한계**: macOS에서는 공유 텍스처가 없습니다. `CwAcceleratedPaintInfo`의 평면은 비어 있고 `format`과 `extra`만 CEF의 값입니다(IOSurface 핸들은 Python에 주지 않음). Linux 쪽 분기(`OS_LINUX`의 typedef)는 이 컴퓨터에서 컴파일하지 못했고, 생성 결과가 수정 전과 같음으로만 확인했습니다.

## F84. 네이티브 `NSView`에 붙이기 (`CefApp.parent_view`)

- **확인함**: `app.parent_view = <NSView의 주소>`를 주고 `initialize()`하면 브라우저가 그 뷰의 자식 뷰(`window_info.SetAsChild`)로 만들어져 뷰를 채웁니다. PyObjC로 만든 `NSWindow`의 content view에서 자식 뷰 1개, 프레임 `(0,0,640,400)`이고 페이지의 `innerWidth/innerHeight`가 640x400입니다. 창 크기를 900x500으로 바꾸면 자식 뷰가 따라가고 페이지도 900x500을 봅니다(CEF가 자동으로 크기를 맞춤, 따로 코드 없음). `shutdown()`이 정상입니다.
- **확인함**: `examples/cocoa/quickstart.py`(NSApp 이벤트 루프 + `NSTimer`가 `MessagePump.run()`을 호출)가 3번 모두 종료 코드 0으로 끝나고 도우미 프로세스가 남지 않습니다. 시험은 `CEFWEAVER_TEST_COCOA=1`로 실행하는 `WithCefInACocoaView`(PyObjC 필요).
- **함정(예제의 결함이었음)**: `NSTimer` 블록은 `None`을 돌려줘야 합니다. `lambda: a and b`가 `False`를 돌려주면 PyObjC가 `ValueError`를 Objective-C 예외로 올리고 AppKit이 `_crashOnException`으로 프로세스를 죽입니다(SIGTRAP, 종료 코드 133). 라이브러리 문제가 아닙니다.
- **함정**: `windowWillClose_` 안에서 `shutdown()`을 부르면 죽었습니다(창이 닫히는 중에 브라우저 뷰를 닫음). `windowShouldClose_`에서 `False`를 돌려주고 타이머로 미룬 뒤 `shutdown()`과 `terminate_`를 부르게 했습니다.
- **미확인**: SwiftUI의 `NSViewRepresentable`(같은 `NSView`이므로 될 것으로 보지만 Swift에서 시험하지 않음), Qt의 `winId()`, wx, Tk. 한 `NSView`에 브라우저 여러 개, 뷰를 제거하는 순서.

## F85. macOS의 키 이벤트 규칙 (`cefweaver.ui`)

호스트에 직접 키 이벤트를 보내 깨끗한 상태에서 비교했습니다(입력창에 `abc`, 캐럿 2에서 한 키씩).

| 이벤트 | 결과 |
| --- | --- |
| RAWKEYDOWN에 Windows 키코드만 | 편집 안 됨 |
| RAWKEYDOWN에 `native_key_code`, KEYUP은 `character` 0 | 편집은 되지만 KEYUP이 가짜 keydown이 됨(편집 키가 한 번 더 편집) |
| RAWKEYDOWN에 `native_key_code`, KEYUP에 `native_key_code`와 `character`(Backspace 127, 왼쪽 0xF702, Delete 0xF728) | **한 번만 편집, `keydown`과 `keyup`이 올바른 키 이름으로 도착** (Backspace, 왼쪽, Delete 각 3번) |
| 같은 순서에 CHAR(8)를 끼움 | 같은 결과 |

`ui/keys.py`의 `MAC_NATIVE_CODES`(Carbon `kVK_*`)와 `MAC_KEY_CHARS`(Cocoa 문자)가 이 규칙을 적용하고, `BrowserView.key()`는 툴킷이 주는 `native_code`가 있으면 그것을 씁니다. 일반 글자의 KEYUP은 같은 키 down의 문자를 되풀이합니다. 실제 CEF에서 `a`, `b`, `c`, Backspace, 왼쪽, Delete를 `BrowserView.key()`로 보내 `abc → ab → ab(캐럿 1) → a`를 확인했습니다(`WithCefKeys`). 
**Command 조합**: 호스트에 Command(128)+A와 Command+Z를 키 이벤트로 보내면(native 0 또는 6, 문자 유무와 무관) 아무 일도 하지 않습니다. Python 프로세스에 Edit 메뉴가 없어 CEF가 키 등가물을 찾지 못하기 때문으로 보입니다(원인은 확인하지 않음). 그래서 `BrowserView`는 macOS에서 Command를 단축키 수식어로 보고 Command+A를 `Frame.select_all()`, Command+Z를 `undo()`, Command+Shift+Z를 `redo()`로 실행하며(실제 CEF에서 입력창이 `a` → Command+A → `q`로 바뀌는 것을 확인), Command+C/X/V는 툴킷의 클립보드로 처리하고, Command가 눌린 글자는 입력하지 않습니다. 같은 키에서 Ctrl은 일반 키입니다.

**IME(오프스크린)**: `BrowserView.preedit("한", 1)`로 입력창에 조합 중인 글자가 나타나고 `commit_text("한글")`로 확정됩니다(`WithCefKeys`). 실제 입력기에서의 입력은 아닙니다.

F1~F12, 숫자 패드, 위 표 밖의 기능 키는 확인하지 않았습니다.

## F86. 여러 툴킷에서의 `parent_view`와 어댑터

Python 3.14.3(uv), PyQt6, wxPython 4.3.1, Tk 9.0, pysdl2 + pysdl2-dll에서 확인했습니다.

| 대상 | 결과 |
| --- | --- |
| Qt (`QWidget.winId()`를 `parent_view`로) | **동작.** 위젯 크기(700x426)를 정확히 채우고 창을 900x600으로 키우면 576까지 따라가고 정상 종료합니다 |
| wx (`Panel.GetHandle()`) | **동작.** 패널 크기(700x422)를 채우고 정상 종료합니다 |
| Tk (`winfo_id()`) | **죽습니다**(SIGBUS). `winfo_id()`는 `NSView`가 아닙니다(cefpython도 같은 문제를 이슈 #308, #309로 적음) |
| Tk (PyObjC로 `NSApp.windows()[-1].contentView()`) | 동작하지만 브라우저가 창 전체를 채웁니다(Tk 위젯 위치를 따르지 못함). 종료도 정상 |
| `cefweaver.ui` 어댑터: Qt(`examples/qt/quickstart.py`), wx, SDL2 | **동작.** 제목이 오고 창을 닫으면 정상 종료(종료 코드 0) |
| `cefweaver.ui` 어댑터: Kivy | Kivy 2.3.1에 Python 3.14용 SDL2 창 제공자가 없어서(`Unable to get a Window`) 본 경로는 **확인하지 못함**. pygame 제공자로 돌렸을 때 `Window.left`가 `None`이라 `screen_origin()`이 매 프레임 예외를 내는 결함을 찾아 고쳤습니다 |
| `cefweaver.ui` 어댑터: GTK 3 | 시스템에 GTK 3가 없어서 **확인하지 못함**(Homebrew로 설치하지 않았음) |

SDL2 어댑터는 `SDL_VIDEODRIVER=x11`을 항상 설정해서 macOS에서 `SDL_Init: x11 not available`로 시작도 못 했습니다. Linux에서만 설정하도록 고쳤습니다.

## F87. 여러 브라우저와 닫기 (`parent_view`)

- **확인함**: 한 창의 두 `NSView`(좌우 분할)에 `app.parent_view`와 `create_browser(parent_view=...)`로 브라우저를 하나씩 붙이면 둘 다 로드되고 각자의 뷰를 채우며, 창 크기를 키우면 부모 뷰의 오토리사이징 마스크대로 따라갑니다(왼쪽 600x500, 오른쪽은 폭 고정 400x500).
- **확인함**: 한 브라우저만 있을 때 `shutdown()`은 0.06초입니다(폴링, 외부 펌프, `NSApp.run()` 모두).
- **발견한 결함(수정함)**: `DoClose()`가 `false`를 돌려주면 CEF가 최상위 부모 **창에 `performClose:`를 보냅니다**(헤더 문서에 있음). 그래서 보조 브라우저 하나를 닫으면 앱의 창 전체가 닫혔고(`isVisible` False), 닫기 버튼이 없는 창에서는 닫기가 끝나지 않았습니다. 래퍼가 `parent_view`로 만든 브라우저(와 CEF가 만든 창의 브라우저)에서 `DoClose`를 `true`로 돌려 창을 닫지 않고, 뷰를 부모에서 떼고 `CloseBrowser(true)`를 다시 불러 닫기를 끝냅니다(그 내부 호출은 사용자의 `do_close`에 보이지 않음).
- **한계**: 여러 브라우저 중 **하나만** 닫으면 `on_before_close`가 오지 않고 `shutdown()`에서 한꺼번에 끝납니다(약 6초). 브라우저가 하나일 때는 즉시 끝나는 것과 다른 이유는 찾지 못했습니다. `CefBrowserHostView`가 해제되어야 CEF가 닫기를 끝내는데(CEF 소스의 `dealloc` → `WindowDestroyed()`), 뷰의 retain 수가 7~9로 CEF/Chromium 내부가 붙잡고 있었습니다.
- **결함(수정함)**: 처음에는 종료 대기 루프가 `CFRunLoopRunInMode`를 돌렸는데, GIL을 놓은 채로 툴킷의 Python 콜백(Tk)을 실행시켜 `PyEval_RestoreThread` 오류로 죽었습니다. 런 루프 대신 대기 루프에서 직접 뷰를 떼도록 바꿨습니다.

## F88. CEF가 만든 창과 폴링 루프

- **확인함**: 앱이 폴링하는 방식(`while app.is_running: app.do_message_loop_work()`)에서 AppKit 이벤트가 처리되지 않았습니다. `do_message_loop_work()`가 macOS에서 (`external_message_pump`가 꺼져 있으면) `NSApp`의 대기 중 이벤트와 런 루프 소스도 처리하도록 했습니다. 호출은 GIL을 쥔 채라서 툴킷 콜백도 안전합니다.
- **발견한 결함(수정함)**: CEF가 만든 창을 `close_browser()`로 닫으면 창은 닫히는데 `on_before_close`가 오지 않아 `app.is_running`이 계속 True였습니다(`shutdown()` 때에야 끝남). 문서의 빠른 시작(`while app.is_running`)이 끝나지 않는 셈입니다. 원인은 못 찾았지만(창의 retain 수가 17이고 `CefBrowserHostView`가 해제되지 않음), F87의 방식(뷰를 떼고 `CloseBrowser(true)`, 창은 래퍼가 닫음)이 이 경로에도 통해서 `do_close`(거부) → `do_close`(허용) → `on_before_close`가 0.01초 안에 오고 `is_running`이 False가 됩니다.
- 매 `CefDoMessageLoopWork()`를 autorelease pool로 감쌌습니다(Python 폴링 루프에는 메인 스레드 pool이 없음). 위 증상을 고치지는 못했지만 해롭지 않아 남겼습니다.

## F89. Swift/SwiftUI에 임베드한 Python

`examples/swiftui/`(Swift 실행 파일이 libpython을 임베드하고 `NSHostingView` 안의 `NSViewRepresentable`이 만든 `NSView`를 `parent_view`로 줌)로 확인했습니다.

- **동작**: 페이지가 뜨고 제목이 오고(`DisplayHandler`), 창 닫기 요청이 브라우저를 닫습니다.
- **결함(수정함) GIL**: `Py_Initialize()` 뒤 메인 스레드는 GIL을 쥔 채로 Cocoa 런 루프에 들어갑니다. CEF의 다른 스레드가 Python 콜백에서 GIL을 못 얻고, 메인 스레드는 그 스레드를 기다려 교착합니다(`removeFromSuperview`가 멈춤). `PyEval_SaveThread()`로 놓고 호출마다 `PyGILState_Ensure/Release`로 잡으면 해결됩니다(PyObjC는 루프에 들어갈 때 GIL을 알아서 놓음).
- **결함(우회함) 창**: 맨 실행 파일(앱 번들 아님)에서 `WindowGroup`은 창을 만들지 않을 때가 있었습니다(`NSApp.windows` 0개). `NSHostingView`를 `NSWindow`에 직접 넣으면 안정적입니다.
- **미해결 종료**: `app.shutdown()` 안의 `CefShutdown()`이 돌아오지 않아 Chromium의 `MacShutdownWatchdog`("Teardown watchdog expired")이 10초 뒤 프로세스를 종료코드 2로 죽입니다. 브라우저는 이미 닫혔고(`open=0`) 도우미 프로세스도 이미 없습니다. 같은 `.so`와 같은 스크립트가 일반 `python` 실행 파일에서는 0.06~0.1초에 끝나고, **Swift 실행 파일에 libpython을 임베드해서 가장 단순한 오프스크린 스크립트(`smoke_mac.py`)를 돌려도 재현**됩니다(SwiftUI와 무관). 메인 스레드는 `mach_msg`에서 기다리고, GIL 대기나 앱 델리게이트, 콜백 안/밖 호출, 런 루프 안/밖 호출은 원인이 아니었습니다. 원인은 못 찾았습니다. 예제는 루프 종료 뒤 3초 안에 CEF가 내려가지 않으면 `exit(0)`으로 나가게 했습니다(브라우저는 이미 닫혔고 캐시의 마지막 기록만 잘릴 수 있음).

## F90. macOS x86_64 (Rosetta)

- **빌드 확인함**: `macosx64` 배포본(SHA1 `d185ae09...`)과 Rosetta의 x86_64 Python 3.14(uv)로 `prepare.py`와 `uv build --wheel`이 통과합니다(`macosx_13_0_x86_64` wheel, 확장 모듈과 도우미와 프레임워크가 모두 x86_64).
- **구동 확인함**: `import cefweaver`(CEF 154), 오프스크린 첫 프레임(빨강), JS 바인딩이 됩니다. 초기화에 4.3초(Rosetta, arm64는 0.3초).
- **미해결**: 종료에서 F89와 같은 `MacShutdownWatchdog`("Teardown watchdog expired")이 발동합니다(종료 코드 2). 네이티브 arm64 Python에서는 일어나지 않습니다.
- **실제 Intel Mac이 아니라 Rosetta에서 확인한 것**입니다.
- `tools/prepare.py`의 결함을 찾아 고쳤습니다: 이전 실행이 도중에 끊겨 반쯤 만들어진 `cefsubprocess.app`이 남으면 다음 실행이 `FileExistsError`로 실패했습니다(스테이징 전에 지움).

## F91. Linux 쪽 코드 검증 (macOS 컴퓨터에서)

Linux x86_64 컨테이너(podman, `debian:bookworm-slim`, g++ 12)와 Linux `minimal` 배포본의 헤더로 확인했습니다.

- `native/cefwrapper`의 소스 9개(`library.cpp`, 핸들러, `cef_wrapper_client_handler_linux.cc` 등), `platform_structs.h`(`OS_LINUX` 분기), Cython이 만든 `_cefweaver.cpp` 전체가 `g++ -std=c++20 -fsyntax-only`로 컴파일됩니다.
- `setup.py`의 Linux 분기를 옮기기 전의 `pyproject.toml` `ext-modules`와 항목별로 대조했습니다(소스, 언어, 포함·라이브러리 경로, 라이브러리, 정의, 컴파일·링크 인자 모두 같고, `depends`에 새 헤더 2개만 더 있음).
- **링크와 실행은 하지 못했습니다**(x86_64 `libcef.so`와 에뮬레이션). 구문 검사까지입니다.

## F92. 창 제목과 서명

- **확인함**: CEF가 만든 창의 `NSWindow.title`이 페이지 제목을 따라갑니다(`PlatformTitleChange`의 `[window setTitle:]`). `data:` 페이지의 한글 제목이 깨져 보인 것은 charset이 없는 `data:` URL의 알려진 문제(F11)입니다.
- **서명 상태**: 도우미 앱의 실행 파일과 CEF 프레임워크는 ad hoc 서명입니다. 도우미 `.app` 번들은 봉인되지 않았고(`spctl --assess`: "code has no resources but signature indicates they must be present"), 최상위 `cefsubprocess.app`은 서명 대상 실행 파일이 없어 서명되지 않았다고 나옵니다. **실행에는 영향이 없습니다.** 배포(Gatekeeper, 공증)에는 Developer ID 서명과 hardened runtime이 필요하고 CEF 도우미에는 JIT 등의 entitlements가 필요한데, 이 부분은 **하지 않았고 확인하지 못했습니다.**
- **확인하지 못함**: 키체인 대화상자(`Chromium Safe Storage`)가 뜨는 조건. 시험 중에는 뜨지 않았습니다(캐시가 임시 폴더였고 쿠키를 저장하지 않음). 필요하면 `use-mock-keychain` 스위치를 줍니다.
- **확인하지 못함**: 실제 입력기(한글, 일본어)로의 입력. 조합과 확정을 호스트 API(`BrowserView.preedit()`, `commit_text()`)로 보내 한글이 입력창에 들어가는 것은 확인했습니다([F85](#f85-macos의-키-이벤트-규칙-cefweaverui) 의 `WithCefKeys`).

## 관련 페이지

- [플랫폼 지원 현황](../concepts/platform-support.md)
- [런타임 파일 배치](../concepts/runtime-layout.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
