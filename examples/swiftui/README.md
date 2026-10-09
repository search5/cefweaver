# SwiftUI에 붙이는 cefweaver (macOS)

Swift 앱이 Python(libpython)을 임베드하고, SwiftUI의 `NSViewRepresentable`이 만든 `NSView`를 `CefApp.parent_view`에 주는 예제입니다. 브라우저는 CEF가 그 뷰 안에 직접 그립니다(오프스크린이 아님).

| 파일 | 내용 |
| --- | --- |
| `main.swift` | 창(`NSWindow` + `NSHostingView`), SwiftUI 뷰(`CefView: NSViewRepresentable`), Python 임베드와 `Timer`로 CEF 돌리기, 닫기 |
| `Bridge.h` | `#include <Python.h>` (Swift에서 C API를 쓰기 위한 브리징 헤더) |
| `build.sh` | `swiftc`로 `./CefSwiftUI`를 만듭니다. `PYROOT`가 cefweaver wheel을 설치한 Python의 루트입니다 |

```sh
# 1) cefweaver wheel을 설치한 Python 환경 (예: uv venv + uv pip install dist/cefweaver-*.whl)
# 2) 빌드와 실행
PYROOT=$(python3 -c "import sys; print(sys.base_prefix)") ./build.sh
CEFSWIFT_SITE=<위 환경의 site-packages> PYTHONHOME=$PYROOT ./CefSwiftUI https://example.org/
./CefSwiftUI <주소> --seconds 5      # 5초 뒤에 창을 닫는 입력을 스스로 합니다
```

알아 둘 것(확인한 내용은 [실행해서 확인한 macOS](../../llm-wiki/pages/reference/verified-findings-macos.md)의 F89):

- **GIL**: `Py_Initialize()` 뒤 메인 스레드가 GIL을 쥔 채 Cocoa 런 루프에 들어가면 CEF의 다른 스레드가 Python 콜백에서 막혀 교착합니다. `PyEval_SaveThread()`로 놓고, 호출할 때마다 `PyGILState_Ensure/Release`로 잡습니다(`python()` 함수).
- **창**: 앱 번들이 아닌 실행 파일에서 `WindowGroup`은 창을 만들지 않을 때가 있어서 `NSWindow`에 `NSHostingView`를 직접 넣습니다.
- **뷰의 주소**: `makeNSView` 안에서가 아니라 뷰가 창에 들어간 뒤(`DispatchQueue.main.async`) `start()`를 부릅니다.
- **닫기**: `windowShouldClose`가 먼저 브라우저를 닫고, 끝나면 런 루프를 끝낸 뒤 루프 밖에서 `shutdown()`을 부릅니다.
- **미해결 종료**: Swift 실행 파일에 임베드한 Python에서는 `CefShutdown()`이 돌아오지 않아 Chromium의 감시가 10초 뒤 프로세스를 죽였습니다(원인 미확인, 같은 코드가 일반 `python` 실행 파일에서는 0.1초). 그래서 이 예제는 루프가 끝난 뒤 3초 안에 CEF가 내려가지 않으면 `exit(0)`으로 나갑니다. 실제 사용 환경에서 같은지 확인하고, 아니라면 이 안전장치를 빼도 됩니다.
