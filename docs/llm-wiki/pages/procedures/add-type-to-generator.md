---
title: 새 타입 지원 추가하기
type: procedure
sources:
  - tools/gen/typesys.py
  - tools/gen/emit_cpp.py
  - tools/gen/emit_cython.py
  - tools/gen/emit_pyi.py
  - docs/llm-wiki/pages/reference/coverage-report.md
  - tests/test_generator.py
updated: 2026-10-08
---

# 새 타입 지원 추가하기

생성기가 지원하지 못하는 C++ 타입을 지원하게 만드는 절차입니다. "나중에 모든 타입을 다룰 수 있어야 한다"는 요구를 위한 확장 지점입니다. 어떤 타입이 몇 개의 메서드를 막는지는 [생성 범위와 커버리지](../reference/generated-api-coverage.md)에 있습니다.

## 어떤 타입부터

`python tools/gen/generate.py --report`의 "What blocks the rest, by type"을 봅니다. 154 기준으로 모든 클래스를 범위에 넣었을 때의 장애물은 값 타입 구조체 115, 벡터 57, 소유 포인터 32, 타입 없는 포인터 24, 구조체 18, 출력 인자 16 순이었습니다. 개수가 많은 것부터 하면 효과가 큽니다.

## 절차

1. **종류 정의**: `tools/gen/typesys.py`에 새 `Kind`(frozen dataclass)를 추가합니다. 예: `Struct(cef_name, fields)`, `Vector(element)`.
2. **분류**: 같은 파일의 `classify()`가 파서의 `result_type`(`simple`, `string`, `structure`, `refptr`, `vector`, `map`, `multimap`, `ownptr`, `rawptr`)을 보고 새 종류를 돌려주게 합니다. 지금은 해당 분기가 `Unsupported("...")`를 일으킵니다.
3. **계획 규칙**: `plan_method()`가 방향별로 허용하지 않는 조합(예: 라이브러리 메서드의 출력 인자)을 막는 곳이 있습니다. 새 종류가 어느 방향에서 허용되는지 정합니다.
4. **방출기 세 곳**을 모두 고칩니다. 하나라도 빠지면 생성된 코드가 컴파일되지 않거나 스텁이 틀립니다.
   - `emit_cpp.py`: 함수 포인터 표의 C 타입(`table_in_types`, `table_out_type`, `table_ret_type`), 프록시의 변환 코드(`_method`)
   - `emit_cython.py`: 선언(`_cy_method_signature`), 라이브러리 메서드 변환(`_library_method`), 트램펄린(`_trampoline`), 필요한 `ctypedef`나 `cdef extern` 선언(`emit_pxd`)
   - `emit_pyi.py`와 `emit_cython._annotation`: 스텁의 타입 표기
5. **시험**: `tests/test_generator.py`에 분류 시험을 추가하고(예: `GetHeaderMap`이 지원됨으로 바뀌는지), 통합 시험을 추가합니다.
6. **생성과 빌드**: `python tools/gen/generate.py`, `uv build --wheel`, 시험. 새로 열린 메서드 수가 보고서에 반영됩니다.
7. **위키 갱신**: 이 페이지의 "어떤 타입부터"와 커버리지 페이지, [생성기의 설계](../concepts/binding-generator.md)의 종류 표.

## 설계할 때 정해야 하는 것

- **소유권과 수명**: 값으로 복사하는가, 참조를 유지하는가. `CefOwnPtr`는 소유권이 호출자에게 넘어갑니다.
- **방향**: CEF가 채워 주는 출력인지, 우리가 넘기는 입력인지, 양방향인지. 출력은 핸들러에서는 반환값이 됩니다.
- **Python 표현**: 구조체는 `dataclass`나 `NamedTuple`, 벡터는 `list`, 맵은 `dict` 또는 `list[tuple]`(헤더 맵은 같은 키가 여러 번 나올 수 있는 `multimap`)가 후보입니다.
- **변환 비용**: 큰 벡터를 자주 복사하는 콜백이 있는지.

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 클래스를 생성 범위에 추가하기](add-class-to-generator.md)
- [생성기 모듈](../components/generator-modules.md)
