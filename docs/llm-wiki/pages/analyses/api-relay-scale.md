---
title: API 중계 규모와 생성기 선택
type: analysis
sources:
  - docs/llm-wiki/pages/reference/coverage-report.md
  - tools/gen/model.py
  - tools/gen/vendor/README.txt
updated: 2026-10-08
---

# API 중계 규모와 생성기 선택

"java-cef처럼 모든 것을 중계하려면 `.pyx`, `.pyi`를 몇 개나 만들어야 하는가, 손으로 끝낼 수 있는가"라는 질문에 답하려고 규모를 센 결과입니다. 이 숫자가 바인딩을 손으로 쓰지 않고 생성하기로 한 근거입니다.

## 센 값

| 프로젝트 | 값 | 어떻게 셌는가 |
| --- | --- | --- |
| CEF (사용 중인 154.0.34 헤더) | 클래스 **185개**, 가상 메서드 **1,439개**, 전역 함수 53개 | CEF의 `cef_parser.py`를 `build/native/cef/include`에 실행 |
| CEF (master 2026-09-29 소스) | 가상 메서드 1,441개, 핸들러/콜백/방문자 계열 클래스 75개 | 같은 파서를 `/home/jiho/cef_framework/cef_origin/include`에 실행 |
| CEF 위키 | 클래스 155개, 메서드 1,348개의 한국어 설명 | `/home/jiho/cef_framework/cef_origin/docs/llm-wiki/db/ko/classes_*.json` |
| java-cef | `native/*.cpp` **74개**(그중 `*_N.cpp` 29개), native 전체 **약 20,200줄**, Java 핸들러 인터페이스 40개, 콜백 클래스 43개 | `/home/jiho/cef_framework/java-cef/`의 `wc`와 `ls` |
| cefpython | `.pyx` **47개**(약 7,700줄), CEF 선언 `.pxd` 36개 | `/home/jiho/cef_framework/cefpython/src/`의 `wc`와 `ls` (CEF 전체가 아닌 일부만 다룸) |

세는 방식이 달라서 값끼리 직접 비교할 수는 없습니다. java-cef와 cefpython은 둘 다 **손으로 쓴** 중계 코드이고, 두 프로젝트의 규모만으로도 CEF 전체를 손으로 중계하면 수천에서 수만 줄이 된다는 감을 줍니다.

## 손으로 쓸 때의 위험

이 프로젝트의 손으로 쓴 래퍼는 메서드 10여 개 규모인데도 이번 작업에서 결함이 5건 넘게 나왔습니다. 모두 같은 종류의 연결 코드 문제입니다.

- 바인딩 객체를 다른 프로세스에 원시 복사(JS 콜백이 동작하지 않음)
- 초기화되지 않은 멤버(`m_IsReadyToExecuteJs`)
- 브라우저를 닫지 않고 `CefShutdown()`(세그멘테이션 오류)
- `CefInitialize` 실패를 무시
- 브라우저가 없을 때의 널 역참조

(자세한 내용은 [실험으로 확인한 사실](../reference/verified-findings.md)에 있습니다.) 이런 종류의 코드를 1,400개 규모로 손으로 쓰면 같은 유형의 결함이 반복될 가능성이 높다고 판단했습니다.

## 생성기가 가능한 근거

CEF에는 헤더를 읽는 공식 파서(`tools/cef_parser.py`, 2,564줄)가 있고 CEF 자신의 C↔C++ 래퍼 생성(`translator.py`)에 쓰입니다. 154 헤더에 실행해서 클래스 185개와 메서드 1,439개를 오류 없이 읽었고, 시그니처가 타입까지 정확히 나오는 것을 확인했습니다(`CefLoadHandler`의 네 메서드로 예시 확인). 그래서 하나의 정의(헤더)에서 C++ 프록시, Cython 래퍼, 타입 스텁을 모두 만들 수 있습니다([바인딩 생성기의 설계](../concepts/binding-generator.md)).

## 결과

- 1단계(리소스 핸들러)를 생성기로 구현했습니다: 클래스 9개와 함수 3개, 84+3개의 메서드와 함수.
- 모든 클래스를 범위에 넣었을 때 타입 지원만으로 81%(1,287/1,598)를 커버합니다([생성 범위와 커버리지](../reference/generated-api-coverage.md)).
- 시간 추정은 하지 않았습니다. 한 번에 끝낼 수 없으므로 단계별 시험과 커밋으로 진행합니다. 단계가 안정되면 핸들러 묶음별 병렬 작업(여러 에이전트)을 쓸 수 있고, 이는 사용자가 직접 요청해야 합니다.

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [관련 프로젝트](../reference/related-projects.md)
- [설계 결정 기록](../reference/design-decisions.md)
