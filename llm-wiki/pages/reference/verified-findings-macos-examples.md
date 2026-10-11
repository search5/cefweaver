---
title: 실행해서 확인한 macOS 예제와 인쇄 (F94부터)
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
| `print/quickstart.py` | 시작과 종료는 됩니다(`pycups`는 macOS에서 설치되고 프린터는 없음). `Print...`를 누르면 시스템 인쇄 패널이 모달로 뜨고 패널이 닫힐 때까지 Tk 루프가 멈춥니다(제 하네스는 누르지 않아 90초 뒤 강제 종료했습니다). 이 예제는 README에 "Linux, CUPS"로 적혀 있고 macOS는 대상이 아닙니다([F96](#f96-macos에서-인쇄하는-방법)) |

## F95. 시험하지 않은 것과 한계

- **각 툴킷의 `smoke.py`** (Tk 30개, Qt, wx 33개, SDL2 28개, Kivy 27개, GTK 3, print 11개)는 Xvfb와 `xdotool`과 X 윈도우 ID를 쓰는 **Linux 전용**이라 macOS에서 돌리지 못했습니다. 위 표의 구동 확인이 대신하는 것은 시작, 페이지, 데모 페이지와 Python의 왕복, 닫기뿐이고, 마우스·키·끌어서 놓기·클립보드·메뉴 같은 점검은 macOS의 툴킷에서 하지 않았습니다(`views`만 같은 항목을 Views 자체의 이벤트로 재현).
- **종료 감시**(`MacShutdownWatchdog`)가 걸리는 환경은 지금까지 Rosetta(x86_64), Swift 실행 파일에 임베드한 Python, Kivy입니다. 걸리지 않는 환경은 네이티브 arm64의 일반 스크립트, PyObjC, Tk, Qt, wx, pysdl2입니다. 공통점은 찾지 못했습니다([F89, F90](verified-findings-macos.md)).
- 이 하네스는 저장소에 넣지 않았습니다(예제 코드를 바꾸지 않고 밖에서 닫기를 거는 일회용 스크립트).

## F96. macOS에서 인쇄하는 방법

질문은 "CUPS는 Linux 전용이니 macOS에 맞는 인쇄 방법은 무엇인가"였습니다. 먼저 전제를 확인했습니다. CEF의 `PrintHandler`는 헤더에 "handle printing **on Linux**"라고 적혀 있고 CEF 소스의 인쇄 코드도 `print_dialog_linux`뿐입니다. 그래서 **Linux 전용인 것은 CEF의 `PrintHandler` API(와 예제의 Tk 대화상자)** 입니다. **CUPS 자체는 macOS에도 있습니다**: macOS의 인쇄 시스템이 CUPS여서 `lp`, `lpr`, `lpstat`, `lpadmin`이 있고 `cupsd`가 돌며, `pycups`가 설치되어 `/private/var/run/cupsd`에 연결됩니다. 이 Mac에서 `getPrinters()`는 비어 있었고(추가된 큐 없음) `getDests()`와 `lpstat -e`가 네트워크 프린터 1대를 찾았습니다.

방법은 두 가지로 가르면 됩니다.

| 방법 | 어떻게 | 확인한 것 |
| --- | --- | --- |
| **사람이 쓰는 인쇄** | `host.print()` 하나 | 오프스크린과 CEF 창 모드 모두 호출이 곧바로 돌아오고 **macOS 시스템 인쇄 패널**(`NSPanel` "Print", 모달)이 뜹니다. 프린터, 용지, 쪽 범위, 부수, "PDF로 저장"은 그 패널이 맡습니다. 앱이 대화상자를 만들 필요가 없고 `PrintHandler`는 불리지 않습니다(`on_print_start`, `on_print_settings`, `on_print_dialog`, `on_print_job`이 모두 오지 않음) |
| **대화상자 없이 코드로 인쇄** | `print_to_pdf()`로 PDF를 만들고 시스템에 넘김 | 아래 |

**`print_to_pdf()`** (오프스크린, 창 모드 모두): 콜백 `ok=True`, 쪽 나눔(`page-break-before`)이 반영된 2쪽, A4(`paper_width=8.27`, `paper_height=11.69` 인치로 596x842pt), 글자 보존(PDFKit으로 읽음). Linux가 요구하는 `get_pdf_paper_size`는 macOS에서 필요 없습니다.

**PDF를 시스템에 보내는 두 길** (프린터로는 보내지 않았습니다):

- `NSPrintOperation`(PyObjC의 `PDFKit.PDFDocument.printOperationForPrintInfo_scalingMode_autoRotate_`): `showsPrintPanel=False`로 `runOperation()`이 0.2초에 `True`를 돌려주고, 인쇄 정보의 작업 처리를 "파일로 저장"(`NSPrintSaveJob`, `NSPrintJobSavingURL`)으로 하면 2쪽 PDF가 만들어집니다. 프린터로 보내려면 처리를 스풀로 하고 `NSPrinter`를 지정하면 됩니다(**시험하지 않았습니다**: 이 Mac에 추가된 프린터가 없음). 인쇄 정보는 빈 딕셔너리가 아니라 `NSPrintInfo.sharedPrintInfo().copy()`로 만들어야 합니다(빈 딕셔너리는 `KeyError: 'NSSavePath'`).
- `lp`(CUPS): CLI가 동작합니다(없는 큐 이름과 없는 파일은 각각 거부하고 작업을 만들지 않음). `lpstat -e`와 `pycups`의 `getDests()`는 추가하지 않은 발견된 프린터도 보여 주므로 그 이름으로 `lp -d`를 쓸 수 있을 것입니다. 실제 인쇄는 하지 않았습니다.

**하지 못한 것과 한계**

- 시스템 인쇄 패널에서 **실제로 인쇄를 눌러 작업이 끝나는 것**을 확인하지 못했습니다. 패널은 별도 서비스가 그리는 원격 뷰라서 기본 단추를 `performClick:`으로 눌러도 닫히지 않았고(자동화 불가), 사람이 눌러야 합니다. 공유 `NSPrintInfo`에 "파일로 저장"을 지정해 두어도 패널을 통한 작업에는 쓰이지 않았습니다(파일이 만들어지지 않음).
- 이전 기록(F82, 시험의 건너뜀 이유, `print` 예제 README, 한계 문서)에 "`host.print()`가 끝나지 않는다(원인 미조사)"고 쓴 것은 **틀렸습니다.** 호출은 곧바로 돌아오고(`invoke returned`가 같은 초), 모달 패널이 떠 있는 동안 앱의 루프가 멈춘 것입니다. **확인함**: `print` 예제의 Tk에서 `after()` 콜백이 1초마다 돌다가 `Print...`를 누른 3.0초부터 패널이 떠 있던 5초 동안 한 번도 돌지 않았고, 다른 스레드가 메인 스레드에 `abortModal`을 보내 패널을 닫은 8.0초 뒤 0.1초 만에 다시 돌았습니다(8.1, 9.1, ...). 사람이 패널을 닫으면 앱이 재개됩니다. 그동안 Tk와 같은 앱 쪽 타이머와 CEF 루프(`MessagePump`)도 멈춘다는 뜻이므로, 인쇄 중에 페이지가 갱신되지 않는 것은 정상입니다.
- 창이 없는 오프스크린에서도 패널은 시트가 아니라 독립된 모달 창으로 뜹니다.
- 그래서 `examples/print`의 Tk 대화상자와 `PrintHandler` 흐름은 macOS에서는 쓸 수 없고 쓸 필요도 없습니다. macOS용 예제는 `examples/print/printing_mac.py`, `quickstart_mac.py`, `smoke_mac.py`이고 `quickstart.py`가 `sys.platform`으로 넘깁니다. `smoke_mac.py`의 두 실행(함수, `--window`)이 통과했습니다(Letter 가로 PDF 792x612pt, `NSPrintOperation`의 파일 저장, `lp`의 없는 대상 거부, 패널이 뜨는 것, `PrintHandler`가 불리지 않는 것, 창의 단추 4개). 이 점검에서 알게 된 것: 가로 용지는 세로로 주고 `landscape=True`만 주어야 합니다(두 번 돌리면 세로가 됨). `NSApp.modalWindow()`는 모달 루프 안(타이머 콜백)에서만 값이 있고, 패널은 `NSApp.windows()`에 "Print"라는 `NSPanel`로 바로 보입니다.

## 관련 페이지

- [실행해서 확인한 macOS](verified-findings-macos.md)
- [툴킷 예제](toolkit-examples.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
