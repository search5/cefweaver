---
title: 새 클래스를 생성 범위에 추가하기
type: procedure
sources:
  - tools/gen/scope.py
  - tools/gen/generate.py
  - tools/gen/typesys.py
  - docs/llm-wiki/pages/reference/coverage-report.md
  - tests/test_generator.py
updated: 2026-10-08
---

# 새 클래스를 생성 범위에 추가하기

CEF 클래스를 Python에서 쓰게 하는 가장 흔한 작업입니다. 타입 처리 코드는 바꾸지 않고 목록만 고치므로 위험이 작습니다.

## 절차

1. **보고서로 후보 확인**: `python tools/gen/generate.py --report`의 "Per class" 표에서 대상 클래스의 `지원/전체` 메서드 수를 봅니다(모든 클래스를 범위에 넣었다고 가정한 값). 지원 수가 적으면 아래 "추가해도 열리지 않는 경우"를 먼저 검토합니다.
2. **분류 확인**: 클래스가 라이브러리 쪽(CEF 구현)인지 핸들러 쪽(애플리케이션 구현)인지 알아야 합니다. 파서의 `is_library_side()`/`is_client_side()`가 정하며 헤더의 `/*--cef(source=client)--*/` 표시가 근거입니다. 틀린 목록에 넣으면 `Scope`의 생성 때 단언문이 실패합니다.
3. **목록에 추가**: `tools/gen/scope.py`의 `LIBRARY_CLASSES`, `CLIENT_CLASSES`, `FUNCTIONS` 중 맞는 곳.
4. **생성**: `python tools/gen/generate.py`. 새 클래스뿐 아니라, 그 클래스를 인자나 반환으로 쓰던 기존 메서드(이전에는 "class ... is not generated yet"로 제외됨)가 함께 열립니다. 생성 파일과 [커버리지 보고서](../reference/coverage-report.md)의 차이를 읽습니다.
5. **빌드**: `uv build --wheel`. 생성된 C++와 Cython 코드는 컴파일해 보기 전에는 맞는지 알 수 없습니다. 오류가 나면 생성기의 방출기를 고칩니다(생성 파일을 직접 고치지 않습니다).
6. **시험 추가**: 핸들러이면 `tests/test_smoke.py`에 CEF를 실제로 띄워 콜백을 확인하는 시험을, 라이브러리 클래스이면 생성된 메서드를 부르는 시험을 추가합니다. 생성기 쪽 가정은 `tests/test_generator.py`에 추가합니다.
7. **위키 갱신**: [생성 범위와 커버리지](../reference/generated-api-coverage.md)와 해당 개념 페이지, `index.md`, `log.md`.

## 클래스를 쓰려면 연결도 필요합니다

핸들러 클래스를 생성해도 CEF가 그 객체를 얻는 경로가 있어야 쓸 수 있습니다. 예를 들어 `ResourceHandler`는 `SchemeHandlerFactory`가 반환하고, 그 팩토리는 `register_scheme_handler_factory()`에 넘깁니다. `LoadHandler`나 `LifeSpanHandler`는 `CefClient`가 돌려주는 객체인데 지금의 `CefWrapperClientHandler`는 이들을 한 클래스에 고정해서 구현하므로, **`CefClient`를 사용자 객체로 위임하는 구조로 바꾸는 일이 먼저**입니다. 이 설계 결정이 아직 남아 있습니다([README와 CLAUDE.md 요약](../summaries/readme-and-claude-md.md)).

## 추가해도 열리지 않는 경우

- 값 타입 구조체(`CefRect`, `CefPoint`, `CefSize`, `cef_*_t` 구조체), 벡터, 맵, 소유 포인터를 인자나 반환으로 쓰는 메서드: [새 타입 지원 추가하기](add-type-to-generator.md)가 먼저입니다.
- 부모가 `CefBaseRefCounted`가 아닌 라이브러리 클래스(상속): 래퍼의 상속 구조를 아직 구현하지 않았습니다.
- 라이브러리 메서드의 출력 인자, 라이브러리 메서드가 핸들러 객체를 반환하는 경우

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
- [생성기 모듈](../components/generator-modules.md)
