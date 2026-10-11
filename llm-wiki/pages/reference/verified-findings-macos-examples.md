---
title: 실행해서 확인한 macOS 예제 (F94부터)
type: reference
sources:
  - examples/tk/quickstart.py
  - examples/tk/browser.py
  - examples/qt/browser.py
  - examples/wx/browser.py
  - examples/sdl2/browser.py
  - examples/kivy/quickstart.py
  - examples/views/quickstart.py
  - examples/views/smoke.py
  - examples/print/quickstart.py
  - examples/cocoa/quickstart.py
  - examples/swiftui/main.swift
updated: 2026-10-11
---

# 실행해서 확인한 macOS 예제 (F94부터)

`examples/`의 예제를 macOS에서 하나씩 실제로 띄워 본 기록입니다. 앞의 항목은 [실행해서 확인한 macOS](verified-findings-macos.md)에 있습니다.

## F94. 예제별 결과

환경: macOS 26.6(Apple Silicon), CPython 3.14.3(Kivy만 3.13.12), scikit-build-core로 만든 `macosx_12_0_arm64` wheel(F93), CEF 154. 방법: 예제의 코드를 고치지 않고, 시험 하네스(저장소 밖)가 창의 닫기 단추와 같은 경로(`WM_DELETE_WINDOW`, `closeEvent`, `Close`, `SDL_QUIT`, `on_request_close`, `performClose`)로 몇 초 뒤에 닫게 했습니다. `browser.py`는 데모 페이지가 Python의 `appReady()`를 부르는 것을 `demo.install`을 감싸서 봤습니다. 판정: 페이지가 뜨고 제목이나 `appReady`가 오고, 종료 코드가 0이고, 도우미 프로세스가 남지 않음.

| 예제 | 결과 |
| --- | --- |
| `tk/quickstart.py`, `tk/browser.py` | 통과. `appReady` 폭 800, 배율 1(Tk 어댑터는 `scale()`이 항상 1.0: Retina에서 논리 해상도로 그려짐, 기존 동작) |
| `qt/quickstart.py`, `qt/browser.py` | 통과. 폭 900, 배율 2 |
| `wx/quickstart.py`, `wx/browser.py` | 통과. 폭 900, 배율 2 |
| `sdl2/quickstart.py`, `sdl2/browser.py` | 통과. 폭 900, 배율 2 |
| `views/quickstart.py` | 통과 |
| `views/smoke.py`의 점검 | `xdotool` 대신 Views 자체의 `send_mouse_move`, `send_mouse_events`, `send_key_press`, `Window.close()`로 같은 순서를 재현해 12개 모두 통과(창 제목, 툴바 배치, 주소 필드, 주소를 쓰고 Return, Back, Forward, Reload, 창 닫기와 종료) |
| `cocoa/quickstart.py` | 통과(종료 코드 0, 4.7초) |
| `swiftui` | 3번 모두 종료 코드 0(안전장치로 약 6.5초, [F89](verified-findings-macos.md)) |
| `kivy/quickstart.py` (3.13) | **종료가 안 됨.** 페이지와 제목은 오지만(SDL2 창 제공자), 닫기 요청 뒤 `Session.shutdown()` 안의 `CefShutdown()`이 끝나지 않아 Chromium의 `MacShutdownWatchdog`이 10초 뒤 종료 코드 2로 프로세스를 죽입니다. `kivy/browser.py`도 같음 |
| `kivy` (3.14) | 실행 못 함: Kivy 2.3.1에 Python 3.14용 SDL2 창 제공자가 없음(`Unable to get a Window`) |
| `gtk3` | **실행하지 못함**: 시스템에 GTK 3가 없음(Homebrew로 설치하지 않았음) |
| `print/quickstart.py` | 시작과 종료는 됩니다(`pycups`는 macOS에서 설치되고 프린터는 없음). `Print...`를 누르면 앱이 응답하지 않아 90초 뒤 강제 종료했습니다. 이 예제는 README에 "Linux, CUPS"로 적혀 있고 macOS는 대상이 아닙니다(`host.print()`가 끝나지 않는 것은 [F82](verified-findings-macos.md)) |

## F95. 시험하지 않은 것과 한계

- **각 툴킷의 `smoke.py`** (Tk 30개, Qt, wx 33개, SDL2 28개, Kivy 27개, GTK 3, print 11개)는 Xvfb와 `xdotool`과 X 윈도우 ID를 쓰는 **Linux 전용**이라 macOS에서 돌리지 못했습니다. 위 표의 구동 확인이 대신하는 것은 시작, 페이지, 데모 페이지와 Python의 왕복, 닫기뿐이고, 마우스·키·끌어서 놓기·클립보드·메뉴 같은 점검은 macOS의 툴킷에서 하지 않았습니다(`views`만 같은 항목을 Views 자체의 이벤트로 재현).
- **종료 감시**(`MacShutdownWatchdog`)가 걸리는 환경은 지금까지 Rosetta(x86_64), Swift 실행 파일에 임베드한 Python, Kivy입니다. 걸리지 않는 환경은 네이티브 arm64의 일반 스크립트, PyObjC, Tk, Qt, wx, pysdl2입니다. 공통점은 찾지 못했습니다([F89, F90](verified-findings-macos.md)).
- 이 하네스는 저장소에 넣지 않았습니다(예제 코드를 바꾸지 않고 밖에서 닫기를 거는 일회용 스크립트).

## 관련 페이지

- [실행해서 확인한 macOS](verified-findings-macos.md)
- [툴킷 예제](toolkit-examples.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
