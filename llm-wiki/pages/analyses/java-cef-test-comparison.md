---
title: java-cef 시험과의 비교
type: analysis
sources:
  - tests/test_smoke.py
  - CLAUDE.md
  - llm-wiki/pages/components/tests.md
updated: 2026-10-10
---

# java-cef 시험과의 비교

"java-cef는 우리 시험과 비슷한 흐름을 타는가"라는 질문에 답하려고 조사한 내용입니다. 조사한 자료: `/home/jiho/cef_framework/java-cef/`의 위키(`docs/llm-wiki/pages/run-and-test.md`, `known-constraints.md`)와 원본 `tools/run_tests.sh`, `java/tests/junittests/`의 7개 파일(총 794줄)입니다. 위키가 가리키는 원본을 직접 읽었습니다.

## java-cef의 시험 구조

- **러너**: JUnit 5 콘솔(`third_party/junit/junit-platform-console-standalone-1.4.2.jar`)로 `--select-package tests.junittests`. `tools/run_tests.sh`가 `LD_PRELOAD=libcef.so`와 `LD_LIBRARY_PATH`를 설정합니다.
- **전역 초기화**: `TestSetupExtension`이 JUnit의 `BeforeAllCallback`으로 JVM 수명 동안 **한 번만** `CefApp.startup(null)`과 `CefApp.getInstance(settings)`를 호출합니다. 모든 시험이 끝나면 `close()`가 `CefApp.getInstance().dispose()`를 부르고 `CountDownLatch`로 `TERMINATED` 상태를 기다립니다.
- **TestFrame**: 브라우저를 띄우는 시험의 기반 클래스(299줄, `JFrame`)입니다. 익명 서브클래스가 `setupTest()`에서 핸들러를 달고 브라우저를 만들며, 원하는 콜백이 오면 `terminateTest()`로 창 닫기를 시작하고, 시험 본문은 `awaitCompletion()`(`CountDownLatch.await`)으로 기다립니다. 창 닫기는 `windowClosing`과 `doClose`가 번갈아 호출되는 7단계이고 생성자 주석에 설명되어 있습니다.
- **가짜 응답**: `addResource(url, content, mime)`로 `http://test.com/test.html` 같은 URL의 응답을 등록하고, `TestFrame.getResourceHandler`가 `TestResourceHandler`로 응답합니다.
- **시험 내용**: 시험 메서드는 9개입니다. `DragDataTest` 6개(브라우저 없이 `CefDragData` 객체만), `DisplayHandlerTest` 2개(제목과 주소 변경 콜백), `TestFrameTest` 1개(`TestFrame` 자체).
- **화면**: `run_tests.sh`에 가상 디스플레이 처리가 없습니다(확인한 범위에서 헤드리스 실행 방법이 코드에 없음).
- java-cef 위키의 `known-constraints.md`는 이 환경에서 JUnit 시험을 실행하지 못했다고 밝힙니다. 그러므로 **java-cef의 시험이 실제로 통과하는지는 위키도, 이 조사도 확인하지 못했습니다.**

## cefweaver와의 비교

| | java-cef | cefweaver |
| --- | --- | --- |
| 초기화 | 전체 시험이 CEF 하나를 공유 | 시험마다 새 프로세스 |
| 완료 대기 | 콜백 + `CountDownLatch` | 메시지 루프를 돌리며 조건 확인(`wait_until`) |
| 가짜 응답 | `addResource` + 리소스 핸들러 | `app.add_resource()`(생성된 리소스 핸들러 API 위에 구현), 간단한 페이지는 `data:` URL |
| 정리 | `cleanupTest`, `onBeforeClose`로 명시적 | 프로세스 종료(2026-10-10부터 `shutdown()`이 남은 브라우저를 먼저 닫음, [F99](../reference/verified-findings-views.md)) |
| 시험 프레임워크 | JUnit 5 | `unittest` |
| 화면 | 실제 창(`JFrame`) | Xvfb와 X11 지정, Wayland 환경에서는 건너뜀 |
| 범위 | 핸들러와 UI 중심, 시험 9개 | 바인딩, 수명 주기, 리소스 핸들러, 클라이언트 핸들러, 생성기, 위키 점검, 시험 134개(2026-10-08 기준. 2026-10-10에는 정의된 시험 메서드가 `test_smoke.py` 221개, `test_generator.py` 125개, `test_ui.py` 164개 등 500개를 넘음) |

## 채택한 것

1. **조건 기반 대기**: java-cef의 `awaitCompletion()`에 해당하도록 고정 시간 대기를 `wait_until()`로 바꿨습니다. 시간 제한은 상한이고 초과하면 기다린 대상을 밝히는 `TimeoutError`로 실패합니다.
2. **가짜 URL 응답**: java-cef의 `addResource`에 해당하는 `add_resource()`를 만들었습니다. 처음에는 C++ 래퍼에 리소스 핸들러 API가 없어서 도입하지 못했는데, 이것이 바인딩 생성기의 1단계 범위가 된 계기입니다([리소스 제공](../concepts/resource-serving.md)).

## 채택하지 않은 것

CEF를 모든 시험이 공유하는 방식은 한 시험의 크래시가 전체를 중단시키고 시험 사이에 상태(캐시, 열린 브라우저)가 섞이므로, 시험이 5개에서 120여 개였던 당시에는 프로세스 분리의 안정성을 택했습니다. 시험이 많아져서 시험당 비용(약 0.5초)이 커지면 공유 방식을 검토합니다([시험](../components/tests.md)).

## 관련 페이지

- [시험](../components/tests.md)
- [관련 프로젝트](../reference/related-projects.md)
- [설계 결정 기록](../reference/design-decisions.md)
