---
title: 바인딩 생성기의 설계
type: concept
sources:
  - tools/gen/generate.py
  - tools/gen/model.py
  - tools/gen/typesys.py
  - tools/gen/scope.py
  - tools/gen/report.py
  - tools/gen/vendor/README.txt
  - docs/llm-wiki/pages/reference/coverage-report.md
updated: 2026-10-08
---

# 바인딩 생성기의 설계

CEF API를 Python으로 거의 그대로 중계하려면 클래스 185개, 가상 메서드 약 1,440개분의 연결 코드가 필요합니다. 이 코드를 손으로 쓰지 않고 CEF 헤더에서 생성합니다. 규모의 근거는 [API 중계 규모와 생성기 선택](../analyses/api-relay-scale.md)에 있습니다.

## 파이프라인

```
CEF 헤더 (build/native/cef/include)
   | CEF의 cef_parser.py (tools/gen/vendor, 수정 없이 복사)
   v
model.py     클래스, 메서드, 인자의 모델 + 열거형 목록 + 순수 가상 감지 + PEP 8 이름
   | scope.py   지금 생성할 클래스와 함수의 목록
   v
typesys.py   모든 C++ 타입을 종류(kind)로 분류하고 메서드마다 계획(MethodPlan)을 만듦
   |           지원하지 못하는 타입은 이유와 함께 "미지원"으로 기록
   v
emit_cpp.py     C++ 프록시 헤더
emit_cython.py  Cython 선언(.pxd)과 래퍼(.pxi)
emit_pyi.py     타입 스텁(.pyi)
report.py       커버리지 보고서
```

생성 결과는 저장소에 커밋됩니다([생성된 파일](../components/generated-files.md)). 패키지를 빌드하는 사람은 생성기를 실행하지 않아도 되고, 헤더가 바뀔 때(CEF 버전 변경)만 개발자가 실행합니다.

## 입력: 사용 중인 배포본의 헤더

파서는 CEF 저장소 master의 `tools/cef_parser.py`(2026-09-29 커밋)를 그대로 복사했고, 입력 헤더는 실제로 링크하는 CEF 배포본의 것입니다. 그래서 생성 결과는 언제나 쓰는 `libcef`와 같은 버전입니다. 154 배포본의 헤더에서 클래스 185개, 가상 메서드 1,439개를 읽는 것을 확인했습니다. master 소스(같은 파서)에서는 1,441개입니다. 다른 CEF 버전의 헤더로 재생성해 본 적은 없습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 타입 종류

`tools/gen/typesys.py`의 `classify()`가 파서의 타입 분석을 다음 종류로 바꿉니다.

| 종류 | 대상 | Python |
| --- | --- | --- |
| `Void` | `void` 반환 | `None` |
| `Prim` | `bool`, 정수형(`int`, `int64_t`, `size_t` 등), `double`, `float`, `cef_color_t` | `bool`, `int`, `float` |
| `Str` | `CefString` | `str` |
| `Enum` | `typedef enum { } cef_x_t;`로 선언된 열거형 | `int` |
| `LibRef` | 생성 범위 안의 CEF 구현 클래스의 `CefRefPtr<T>` | 래퍼 객체(널이면 `None`) |
| `ClientRef` | 생성 범위 안의 애플리케이션 구현 클래스의 `CefRefPtr<T>` | 핸들러 객체 |
| `Buffer` | `void*`와 뒤따르는 정수 크기 쌍 | `memoryview` |

파서의 `result_type`을 기준으로 삼되 두 가지는 따로 처리합니다. 첫째, 파서의 `is_result_struct_enum()`은 "참조나 포인터가 아니다"라는 어림짐작일 뿐이라서 쓰지 않고, 열거형은 헤더에서 `typedef enum`을 직접 찾아 구분합니다. 둘째, 파서의 `get_result_ptr_type_root()`는 C++ 클래스명이 아니라 C API 이름(`cef_request_t`)을 돌려주므로 선언된 타입 문자열(`CefRefPtr<CefRequest>`)에서 이름을 뽑습니다(이 오류로 초기 보고서의 수치가 틀렸다가 고쳤습니다).

## 메서드 계획 규칙

- 라이브러리 쪽 클래스(CEF가 구현): Python이 부릅니다. 비상수 참조 출력 인자는 아직 미지원입니다. 클라이언트 객체를 반환하는 메서드도 미지원입니다.
- 클라이언트 쪽 클래스(핸들러): CEF가 부릅니다. 출력 인자(비상수 참조의 기본형, 문자열, 열거형)는 Python 메서드의 반환값이 됩니다. 반환값이 먼저이고, 하나면 그대로, 둘 이상이면 튜플입니다.
- `void*`와 크기는 `Buffer` 하나로 합쳐집니다(핸들러 쪽만).
- 헤더가 `optional_param`으로 표시한 인자만 `None`을 허용합니다. 라이브러리 메서드에 허용되지 않은 곳에 `None`을 넘기면 C++가 죽는 대신 `TypeError`입니다.
- 이름: `Cef` 접두사를 떼고 클래스는 그대로, 메서드와 인자는 snake_case, 예약어는 밑줄을 붙입니다(`Continue` → `continue_`).

## 범위와 커버리지

생성할 클래스는 `tools/gen/scope.py`의 목록(라이브러리 7개, 핸들러 2개, 함수 3개)입니다. 클래스를 추가하면 그 클래스를 인자나 반환으로 쓰던 메서드도 함께 열립니다. 범위 안인데 생성하지 못한 메서드는 조용히 빠지지 않고 [커버리지 보고서](../reference/coverage-report.md)에 이유와 함께 남습니다([생성 범위와 커버리지](../reference/generated-api-coverage.md)).

## 아직 없는 것

- 값 타입 구조체(`CefRect`, `CefPoint` 등), 벡터, 맵, 소유 포인터(`CefOwnPtr`)
- 상속 관계가 있는 라이브러리 클래스(부모 클래스가 `CefBaseRefCounted`가 아닌 경우)
- 라이브러리 메서드의 출력 인자
- 헤더 주석의 한국어 번역(`cef_origin` 위키의 설명)을 스텁에 쓰는 일

남은 일과 순서는 [생성기의 한계와 다음 단계](../reference/generated-api-coverage.md)에 있습니다.

## 관련 페이지

- [핸들러 프록시 구조](handler-proxies.md)
- [생성기 모듈](../components/generator-modules.md)
- [새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
