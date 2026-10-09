---
title: 새 클래스를 생성 범위에 추가하기
type: procedure
sources:
  - tools/gen/scope.py
  - tools/gen/generate.py
  - tools/gen/typesys.py
  - llm-wiki/pages/reference/coverage-report.md
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
6. **시험 추가**(시험을 먼저 쓰고 실패를 확인한 뒤 구현합니다): 핸들러이면 `tests/test_smoke.py`에 CEF를 실제로 띄워 콜백을 확인하는 시험을, 라이브러리 클래스이면 생성된 메서드를 부르는 시험을 추가합니다. 생성기 쪽 가정은 `tests/test_generator.py`에 추가합니다.
7. **위키 갱신**: [생성 범위와 커버리지](../reference/generated-api-coverage.md)와 해당 개념 페이지, `index.md`, `log.md`.

## 클래스를 쓰려면 연결도 필요합니다

핸들러 클래스를 생성해도 CEF가 그 객체를 얻는 경로가 있어야 쓸 수 있습니다. 경로는 클래스마다 다릅니다.

- 별도의 등록 함수가 있는 경우: `ResourceHandler`는 `SchemeHandlerFactory`가 반환하고, 그 팩토리는 `register_scheme_handler_factory()`에 넘깁니다. 생성만으로 충분합니다.
- `CefClient`가 돌려주는 핸들러(로드, 수명 주기, 표시 등): `Client`의 `get_..._handler()`가 반환하며, 사용자는 `CefApp.set_client()`로 클라이언트를 넘깁니다. 새 핸들러를 추가하려면 생성(`scope.py`)에 더해 **손으로 쓴 `CefWrapperClientHandler`도 고쳐야 합니다**: 해당 `Cw<이름>Forward`를 상속에 추가하고, `Get<이름>()`이 사용자의 클라이언트에서 전달 대상을 채우게 하고, 래퍼가 스스로 하던 일이 있는 메서드에는 그 일과 전달 호출(`Cw<이름>Forward::메서드(...)`)을 함께 둡니다. 순서의 기준은 [C++ 핸들러](../components/native-handlers.md)에 있습니다.
- 래퍼가 이미 스스로 구현하는 핸들러(컨텍스트 메뉴와 JavaScript 바인딩용 프로세스 메시지): 사용자에게 열려면 래퍼의 처리와 사용자의 처리를 합치는 방법을 먼저 정해야 합니다.

## 추가해도 열리지 않는 경우

- 값 타입 구조체(`CefRect`, `CefPoint`, `CefSize`, `cef_*_t` 구조체), 벡터, 맵, 소유 포인터를 인자나 반환으로 쓰는 메서드: [새 타입 지원 추가하기](add-type-to-generator.md)가 먼저입니다.
- 부모가 `CefBaseRefCounted`가 아닌 라이브러리 클래스(상속): 래퍼의 상속 구조를 아직 구현하지 않았습니다.
- 라이브러리 메서드의 출력 인자, 라이브러리 메서드가 핸들러 객체를 반환하는 경우

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
- [생성기 모듈](../components/generator-modules.md)
