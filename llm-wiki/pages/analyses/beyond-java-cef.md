---
title: java-cef를 바닥으로 보았을 때 어디까지 왔는가
type: analysis
sources:
  - tools/gen/surface.py
  - llm-wiki/pages/reference/coverage-report.md
  - tools/gen/scope.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - setup.py
  - examples/print/printing.py
updated: 2026-10-10
---

# java-cef를 바닥으로 보았을 때 어디까지 왔는가

[방침](../reference/java-cef-parity.md)은 "java-cef가 여는 것이 cefweaver의 바닥"입니다. 2026-10-10 시점에 그 바닥에서 얼마나 위로 왔고 어디가 아직 아래인지를 위키의 수치와 소스로 정리했습니다. 수치의 원본은 [커버리지 보고서](../reference/coverage-report.md)이고, 아래 "왔다"는 말은 **API의 범위와 이 저장소에서 확인한 것**이며 성숙도나 실사용 검증을 뜻하지 않습니다.

## 바닥은 닫혔다

- java-cef가 CEF 클래스의 메서드로 여는 389개의 격차는 **0개**입니다. 시험(`test_the_gaps_to_the_java_cef_floor_are_the_listed_ones`)이 이를 고정합니다.
- 해당이 없는 것은 java-cef의 Java 쪽 사정(AWT 창 관리, `Dispose`, `onBeforeTerminate` 등)뿐입니다.

## 바닥 위

| 항목 | java-cef | cefweaver |
| --- | --- | --- |
| 생성되는 메서드와 함수 | 약 389개를 엶(JNI로 일일이 감쌈) | **1,031개**(클래스 100개, 전역 함수 6개). 그 가운데 java-cef가 열지 않은 것이 **627개**(클래스 66개)입니다. CEF 전체 2,255개 중 약 46%이고, 타입 지원만으로는 95%까지 열 수 있습니다 |
| 값 컨테이너, 스트림, ZIP, 프로세스 메시지 | 없음(문자열 중심) | `Value`, `ListValue`, `DictionaryValue`, `BinaryValue`, `StreamReader/Writer`, `ZipReader`, `ProcessMessage` |
| 오디오, 마이크와 카메라 권한 | `AudioHandler`, `PermissionHandler` 없음 | 둘 다 있음(F71, F72, F74, F77, F78) |
| GPU 가속 페인트 | OSR은 CPU 버퍼만 | Linux의 공유 텍스처(DMA-BUF, F66). macOS는 없음 |
| JS와 Python 연결 | 메시지 라우터(문자열) | 메시지 라우터(바이트열)와 `JavascriptBridge`(JSON, `Promise`, `evaluate`) |
| 타입 | Java 클래스 몇 개 | 열거형 전부(IntEnum, IntFlag)와 구조체 22개, PEP 8 이름, 타입 스텁(`.pyi`, mypy로 검증) |
| 이벤트 루프 통합 | 없음(AWT) | `MessagePump`(외부 펌프, 폴링 없음) |
| GUI 툴킷 | Swing/AWT(윈도우드와 JOGL 오프스크린) | `cefweaver.ui`의 **어댑터 6개**: Tk, Qt(PyQt6, PySide6), GTK 3, SDL2, wxPython, Kivy. 모두 오프스크린 + 실제 X 이벤트로 점검(28~39개씩) |
| macOS의 네이티브 뷰 | AWT 안의 창 | `parent_view`로 `NSView`에 붙임: PyObjC(Cocoa), **Swift/SwiftUI**, Qt, wx(F84~F89) |
| **Views(툴킷 없는 UI)** (2026-10-10, [F96~F98](../reference/verified-findings-views.md)) | 없음(AWT와 Swing에 얹힘) | 창, 패널, 단추, 텍스트 필드, 레이아웃, 브라우저 뷰를 CEF가 직접 그림. `examples/views/`(실제 X 이벤트로 13개 점검). Linux X11에서만 확인 |
| 인쇄 | 대화상자는 Java 쪽(Swing) | PDF 인쇄와 `PrintHandler` 전부, **앱이 직접 만드는 CUPS 대화상자 예제**(`examples/print`, F94) |
| 배포 | 없음 | PyInstaller와 cx_Freeze로 묶기를 두 빌드에서 확인(F93). py2exe와 Windows는 확인하지 못함 |
| 시험 | JUnit 10개 안팎(`java/tests/junittests`) | **497개**(통합 194, UI 164, 생성기 122, 문서 15, 위키 2) |
| 문서 | 위키 | 위키 + 사람이 읽는 Jekyll 사이트(GitHub Pages) |

(java-cef의 시험 수는 `@Test`와 `public void test`를 센 값이고 시험 하나의 크기는 다릅니다. 시험 수의 비교는 규모를 가늠하는 용도입니다. [시험 비교](java-cef-test-comparison.md)에 자세한 대조가 있습니다.)

## 아직 아래이거나 같지 않은 것

| 항목 | 상태 |
| --- | --- |
| **플랫폼** | java-cef는 Linux 64/32비트, Windows 64/32비트, macOS arm64와 x86_64를 빌드 대상으로 둡니다. cefweaver는 Linux x86_64와 macOS arm64만이고, **Windows는 검증하지 못했으며** macOS x86_64는 Rosetta에서만 확인했습니다([플랫폼 지원 현황](../concepts/platform-support.md)) |
| **성숙도** | 저장소의 README가 "개발 중이며 실사용 목적이 아니다"라고 적습니다. java-cef는 오래 쓰인 프로젝트입니다. 이 문서의 "왔다"는 범위의 이야기입니다 |
| **창 모드 임베딩(툴킷 위젯에 CEF가 만든 창을 붙이기)** | java-cef의 `CefBrowserWr`에 해당. 코드는 `SetAsChild`로 플랫폼 중립으로 쓰였지만(`cef_wrapper_browser_process_handler.cc`) **확인은 macOS의 `NSView`에서만** 했습니다. Linux의 툴킷 위젯에 붙이는 것은 하지 않았고, 툴킷 어댑터는 오프스크린(CPU 복사 또는 공유 텍스처)입니다 |
| **배포 형식** | wheel의 태그가 `linux_x86_64`(로컬)이고 manylinux가 아니라 PyPI에 올리지 못합니다(F24, `auditwheel`이 거절) |
| **인쇄는 Linux 전용** | `PrintHandler`가 Linux 전용이라 macOS는 `host.print()`가 90초 안에 끝나지 않았습니다(F82) |
| 알려진 미해결 | Rosetta와 Swift 임베딩에서 `CefShutdown()`이 끝나지 않는 것(F89, F90), 여러 브라우저 중 하나만 닫을 때의 지연(F87), 동결본의 간헐적 점검 실패 두 건(F93). [알려진 제약](../reference/known-constraints.md) |

## 요약

- **API 범위**: 바닥(389)은 모두 열렸고 그 위로 627개를 더 열어 java-cef의 약 2.6배(1,031개)입니다.
- **쓰기 쉬움**: 파이썬 방식(PEP 8, 타입 스텁, `IntEnum`, `datetime`, `dict`)과 GUI 툴킷 어댑터 6개, macOS 네이티브 뷰는 java-cef에 대응이 없는 부분입니다.
- **뒤처진 곳**: 플랫폼(특히 Windows), 성숙도와 실사용 검증, Linux의 창 모드 임베딩, 배포 형식입니다.

## 관련 페이지

- [java-cef 동등성 (바닥과 그 위)](../reference/java-cef-parity.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
- [cefpython과 cefweaver의 API 차이](cefpython-comparison.md)
- [java-cef의 시험과 cefweaver의 시험 비교](java-cef-test-comparison.md)
- [플랫폼 지원 현황](../concepts/platform-support.md)
