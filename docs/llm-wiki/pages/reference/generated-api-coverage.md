---
title: 생성 범위와 커버리지
type: reference
sources:
  - docs/llm-wiki/pages/reference/coverage-report.md
  - tools/gen/scope.py
  - tools/gen/report.py
updated: 2026-10-08
---

# 생성 범위와 커버리지

[커버리지 보고서](coverage-report.md)(`python tools/gen/generate.py --report`)의 요약입니다. 수치는 CEF 154.0.34 헤더 기준이며, 버전이 바뀌면 보고서를 다시 읽어야 합니다. 원본은 항상 그 보고서입니다.

## 지금 생성되는 것

범위(`scope.py`)는 클래스 9개와 전역 함수 3개입니다. 클래스의 메서드(가상과 정적) 100개 가운데 84개가 생성되고 16개가 제외되며, 함수 3개를 더해 87개입니다.

| 클래스 | 쪽 | 생성/전체 | 제외 사유 |
| --- | --- | --- | --- |
| `CefResourceHandler` | 핸들러 | 7/7 | |
| `CefSchemeHandlerFactory` | 핸들러 | 1/1 | |
| `CefCallback` | 라이브러리 | 2/2 | |
| `CefResourceReadCallback` | 라이브러리 | 1/1 | |
| `CefResourceSkipCallback` | 라이브러리 | 1/1 | |
| `CefRequest` | 라이브러리 | 18/23 | `CefPostData`가 범위 밖(3), 헤더 맵(멀티맵) 2 |
| `CefResponse` | 라이브러리 | 16/18 | 헤더 맵(멀티맵) 2 |
| `CefFrame` | 라이브러리 | 20/26 | `CefStringVisitor`, `CefV8Context`, `CefDOMVisitor`, `CefURLRequest`, `CefProcessMessage`가 범위 밖(6) |
| `CefBrowser` | 라이브러리 | 18/21 | `CefBrowserHost`가 범위 밖(1), 벡터 2 |

제외된 16개의 사유는 범위 밖 클래스 10, 멀티맵 4, 벡터 2입니다. 범위 밖 클래스는 그 클래스를 추가하면 열립니다([새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)).

## 모든 클래스를 범위에 넣는다면

보고서는 "모든 클래스를 범위에 넣었을 때 타입 지원만으로 어디까지 되는가"도 계산합니다. 154 헤더에서 메서드와 함수 1,598개 가운데 1,287개(81%)입니다. 남은 장애물은 다음과 같습니다.

| 개수 | 사유 | 대응 |
| --- | --- | --- |
| 115 | 값 타입 구조체(`CefRect`, `CefPoint`, `CefSize` 등) | 구조체 종류 추가 |
| 57 | 벡터 | 벡터 종류 추가 |
| 32 | 소유 포인터(`CefOwnPtr`) | 소유권 이전 규칙 |
| 24 | 타입 없는 포인터(`void*` 단독 등) | |
| 18 | 구조체(`cef_*_t` 값) | 구조체 종류 |
| 16 | 라이브러리 메서드의 출력 인자 | 방향 규칙 |
| 11 | 라이브러리 메서드가 핸들러 객체를 반환 | |
| 11 | 원시 포인터(`CefRawPtr`) | |
| 8 | 포인터 | |
| 8 | 멀티맵 | |
| 4 | 맵 | |
| 4 | `CefRefPtr` 참조 | |
| 2 | 클래스 | |
| 1 | 핸들러 메서드가 라이브러리 객체를 반환 | |

표의 사유는 보고서의 묶음 이름을 한국어로 옮긴 것입니다. 클래스별 지원 비율은 [커버리지 보고서](coverage-report.md)의 "Per class" 절에 있습니다(모든 클래스가 나열되고 지금 범위 안의 클래스에는 `*`가 붙습니다). 메서드가 많은 클래스는 `CefV8Value`(67개), `CefView`(52개), `CefWindow`(43개), `CefBrowserHost`(72개) 같은 V8과 뷰 계열입니다.

## 생성기의 한계와 다음 단계

생성기를 만든 직후(기준 커밋 `f9e459c`, 1단계: 리소스 핸들러)에 정리한 메모를 이 절로 옮겼습니다. 이전에는 `tools/gen/STATUS.md`에 있었습니다.

### 한계와 미검증

- Windows와 다른 CEF 버전에서의 재생성은 확인하지 못했습니다. 파서는 CEF master의 것(2026-09-29)이고 154 헤더에서 정상 동작했지만, 다른 버전의 헤더에서는 시험하지 않았습니다.
- 현재 범위는 9개 클래스입니다. `CefLoadHandler`, `CefRequestHandler`, `CefClient` 같은 나머지 핸들러는 아직 생성하지 않았습니다. 그 전에 `CefWrapperClientHandler`를 사용자 객체로 위임하는 구조로 바꾸는 설계 결정이 필요하고, 이것이 다음 단계의 핵심입니다.
- 헤더의 한국어 설명(`cef_origin` 위키)은 아직 스텁에 쓰지 않았고 헤더의 영어 주석을 그대로 쓰고 있습니다.
- 대상 클래스를 상속하는 클래스(예: `CefDictionaryValue` 계열)는 아직 처리하지 않습니다.
- 그 변경은 문서와 시험이 생성기, 모듈 연결, 시험이라는 여러 묶음에 걸쳐 있고 묶음별 커밋은 `cef_api.pxi` 없이 빌드되지 않아서, 합의한 기준(파일이 겹치면 한 번에)대로 커밋 하나로 했습니다.

### 다음 단계 (결정 필요)

1. 핸들러 위임 구조로 `CefClient`를 바꾸고 `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`를 범위에 추가합니다. 핸들러가 가장 흔한 사용 경로입니다.
2. 보고서 1순위인 값 타입 구조체(`CefRect`, `CefPoint` 등)를 지원해서 한꺼번에 많은 메서드를 엽니다(115 + 18건).

어느 쪽을 먼저 진행할지는 아직 정해지지 않았습니다. 확인하지 못한 항목 전체는 [알려진 제약과 미검증 항목](known-constraints.md)에 있습니다.

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
- [Python API 참조](python-api.md)
