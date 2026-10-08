---
title: 생성기 모듈 (tools/gen)
type: component
sources:
  - tools/gen/generate.py
  - tools/gen/model.py
  - tools/gen/typesys.py
  - tools/gen/scope.py
  - tools/gen/report.py
  - tools/gen/emit_cpp.py
  - tools/gen/emit_cython.py
  - tools/gen/emit_pyi.py
  - tools/gen/handwritten.pyi
  - tools/gen/vendor/README.txt
updated: 2026-10-08
---

# 생성기 모듈 (tools/gen)

`tools/gen/`의 구성입니다. 설계는 [바인딩 생성기의 설계](../concepts/binding-generator.md)에 있습니다. 파일 이름에 표준 라이브러리와 겹치는 이름은 쓰지 않습니다. 타입 분류 모듈을 처음 `types.py`로 만들었다가 표준 라이브러리의 `types`를 가리는 문제를 만나 `typesys.py`로 바꿨습니다.

| 파일 | 역할 |
| --- | --- |
| `generate.py` | 진입점. `build_all(cef_root)`가 모델, 범위, 계획, 방출기를 묶어 파일별 내용을 돌려주고, `main()`이 쓰기, `--check`, `--report`를 처리합니다. 출력 경로는 `OUTPUTS` 딕셔너리에 있습니다. |
| `model.py` | `Model(cef_root)`: 파서로 헤더를 읽고(`include`, `include/test`, `include/views`), 클래스와 함수 딕셔너리, 열거형 이름 집합(`typedef enum { } 이름;`을 헤더에서 정규식으로 찾음), `is_pure_virtual()`, `header_path()`, `comment()`를 제공합니다. 이름 변환 함수 `snake_case`, `py_class_name`, `py_method_name`, `py_param_name`도 여기 있습니다. |
| `typesys.py` | 종류(`Void`, `Prim`, `Str`, `Enum`, `LibRef`, `ClientRef`, `Buffer`, `Bytes`, `ItemBytes`, `Ignored`), `Unsupported` 예외, `classify()`, 계획 자료형 `ParamPlan`, `MethodPlan`, `plan_method()` |
| `scope.py` | 생성할 클래스와 함수의 목록(`LIBRARY_CLASSES`, `CLIENT_CLASSES`, `FUNCTIONS`), `Scope.current()`와 `Scope.everything()`(커버리지 측정용으로 모든 클래스를 범위에 넣음) |
| `report.py` | `all_plans()`, `build_report()`. 사유를 `struct`, `class`, `output parameter` 같은 묶음으로 집계합니다. |
| `emit_cpp.py` | C++ 프록시 헤더 |
| `emit_types.py` | `cefweaver/types.py`(열거형과 값 타입). 값은 `model.py`가 헤더에서 읽습니다. |
| `emit_cython.py` | `.pxd`(`emit_pxd`)와 `.pxi`(`emit_pxi`), 공통 변환 함수(`cy_c`, `cy_arg`, `public_function_name`, `_docstring` 등) |
| `emit_pyi.py` | 타입 스텁. 손으로 쓴 `handwritten.pyi`를 앞에 붙입니다. |
| `handwritten.pyi` | `CefApp`의 스텁(손으로 씀). `CefApp`의 공개 API를 바꾸면 이 파일도 고쳐야 합니다. |
| `vendor/` | CEF의 `cef_parser.py`, `date_util.py`, `file_util.py`, `version_util.py`와 라이선스. 수정 없이 복사했고 출처 커밋은 `vendor/README.txt`에 있습니다. |
| (위키 페이지) | 커버리지 보고서는 `generate.py`가 위키의 [커버리지 보고서](../reference/coverage-report.md)로 씁니다. 생성기의 한계와 다음 단계도 위키([생성기의 한계와 다음 단계](../reference/generated-api-coverage.md))에 있고, `tools/gen/`에는 마크다운이나 텍스트 문서를 두지 않습니다(`vendor/`의 라이선스와 출처 표시만 예외). |

## 의존 방향

`generate.py`가 `model`, `scope`, `typesys`, `report`, 세 방출기를 가져옵니다. `typesys`는 `model`의 이름 함수를 씁니다. `emit_pyi`는 `emit_cython`의 변환 함수를 가져다 쓰고, `emit_cython`은 `emit_cpp`의 표 타입 함수를 씁니다. 모든 모듈은 `tools/gen`이 `sys.path`에 있다는 가정으로 서로를 이름만으로 가져오며, 시험도 같은 방식으로 경로를 추가합니다(`tests/test_generator.py`).

## 방출기가 하는 일의 요약

- `emit_cpp`: 핸들러 클래스마다 표 구조체, 프록시 클래스, 전달 클래스(`Cw<이름>Forward`)를 만들고, 메서드마다 표 항목이 없을 때의 동작(기반 클래스 호출 또는 기본값)과 출력 인자 복사를 씁니다.
- `emit_cython`: 라이브러리 클래스마다 `cdef class`와 `_ptr()`, 메서드, `_wrap_*`을 만들고, 핸들러 클래스마다 Python 기반 클래스, 트램펄린, `_g_make_*`, `_g_export_*`를 만듭니다. 전역 함수는 모듈 수준 `def`입니다.
- `emit_pyi`: 클래스와 함수의 시그니처와 헤더 주석에서 만든 docstring입니다. `None`은 `optional_param`과 `Create()`가 아닌 라이브러리 반환에서만 허용하는 형태로 표기합니다.

## 관련 페이지

- [생성되는 파일](generated-files.md)
- [새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
- [시험](tests.md)
