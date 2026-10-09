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
  - llm-wiki/pages/reference/coverage-report.md
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
| `Enum` | `typedef enum { } cef_x_t;`로 선언된 열거형 | `types`의 `IntEnum`/`IntFlag` 멤버(CEF에 줄 때는 `int`도 됨) |
| `LibRef` | 생성 범위 안의 CEF 구현 클래스의 `CefRefPtr<T>` | 래퍼 객체(널이면 `None`) |
| `ClientRef` | 생성 범위 안의 애플리케이션 구현 클래스의 `CefRefPtr<T>` | 핸들러 객체 |
| `Struct` | 필드가 기본형, 열거형, 다른 구조체인 값 타입(`CefRect`, `CefPoint`, `CefMouseEvent`, `CefKeyEvent`, `CefScreenInfo` 등 15개) | 이름 있는 튜플(`Rect(x, y, width, height)`), 정의는 `cefweaver.types`. 받는 쪽에는 같은 필드의 튜플도 됩니다. |
| `Vector` | `std::vector<T>`. 요소는 문자열, 숫자(`bool` 제외), 값 타입 구조체, 라이브러리 객체(`CefRefPtr<T>`, 출력과 핸들러 입력만) | `list[str]`, `list[int]`, `list[Rect]`, `list[Display]` (라이브러리에 주는 쪽은 아무 시퀀스) |
| `StrMap` | 문자열의 `std::multimap`(헤더 맵), `std::map`(명령줄 스위치) | `dict[str, str]`(멀티맵의 같은 키는 마지막 값이 남음, java-cef의 `Map`과 같음) |
| `Time` | `CefBaseTime`(1601년부터의 마이크로초) | 시간대가 있는 `datetime`(UTC), 0은 `None` ([바이트열과 시간](../reference/bytes-and-times.md)) |
| `ItemBytes` | 라이브러리 메서드의 `void*`, `size_t size`, `size_t n`(`fread`/`fwrite`, `ITEM_BYTES` 표) | `write(data, size=1) -> int`, `read(n, size=1) -> bytes`. [스트림과 ZIP 읽기](../reference/streams.md) |
| `Ignored` | 핸들러의 `CefEventHandle os_event`(Linux에서 `XEvent*`)처럼 Python에 넘기지 않는 인자(java-cef도 넘기지 않음) | 서명에서 빠짐 |
| `Bytes` | 라이브러리 메서드의 `const void*`와 `size_t` 쌍(뒤에 크기가 또 있으면 제외), 또는 `BYTES_OUT` 표의 `void*`와 `size_t`(`BinaryValue.GetData`) | `bytes` 같은 바이트열 입력, 출력은 `get_data(size, offset) -> bytes` |
| `Buffer` | `void*`와 뒤따르는 정수 크기 쌍, 또는 크기 인자가 없는 `const void*`(`SIZED_BUFFERS` 표의 크기 식) | 쓰기 가능한 `memoryview`, 후자는 읽기 전용 |
| `Planes` | `const float** data`와 뒤따르는 `int frames`(`PLANES` 표): 채널마다 샘플 배열 하나. 채널 수는 인자가 아니라 앞선 호출(`OnAudioStreamStarted`의 `channels`)이 알려 주고 프록시가 `REMEMBER` 표에 따라 멤버(`audio_channels_`, `std::atomic<int>`)에 기억합니다 | 채널마다 읽기 전용 `float32` `memoryview`의 `list`(길이가 `frames`). 호출이 끝나면 무효이고 `frames`는 Python에 주지 않음 |

파서의 `result_type`을 기준으로 삼되 두 가지는 따로 처리합니다. 첫째, 파서의 `is_result_struct_enum()`은 "참조나 포인터가 아니다"라는 어림짐작일 뿐이라서 쓰지 않고, 열거형은 헤더에서 `typedef enum`을 직접 찾아 구분합니다. 둘째, 파서의 `get_result_ptr_type_root()`는 C++ 클래스명이 아니라 C API 이름(`cef_request_t`)을 돌려주므로 선언된 타입 문자열(`CefRefPtr<CefRequest>`)에서 이름을 뽑습니다(이 오류로 초기 보고서의 수치가 틀렸다가 고쳤습니다).

## 열거형

열거형은 헤더에서 읽어 `cefweaver.types`의 `IntEnum`/`IntFlag`로 만듭니다. CEF에 넘길 때는 정수 그대로 되고, 핸들러의 인자와 라이브러리의 반환은 멤버로 변환합니다([types 모듈](../reference/types-module.md)).

## 벡터

`std::vector<T>`는 요소 종류마다 변환 함수가 만들어지고(`_g_list_<태그>`, `_g_vector_<태그>`), 방향마다 허용하는 요소가 다릅니다.

| 방향 | 허용하는 요소 |
| --- | --- |
| 라이브러리 메서드의 출력(`browser.get_frame_names()`, `settings.get_page_ranges()`, `Display.get_all_displays()`, `manager.get_task_ids_list()`) | 문자열, 숫자, 구조체, 객체 |
| 라이브러리 메서드에 주는 입력(`settings.set_page_ranges([...])`) | 문자열, 숫자, 구조체 |
| 핸들러가 받는 입력(`on_draggable_regions_changed`, `on_favicon_url_change`) | 문자열, 숫자, 구조체, 객체 |
| 핸들러의 출력 | 지원하지 않음 |

## 값 타입 구조체

`CefRect`처럼 CEF가 값으로 주고받는 데이터는 헤더에서 읽어 만듭니다. 다른 구조체를 필드로 가진 구조체(`CefDraggableRegion`의 `bounds`는 `CefRect`)도 읽습니다(의존하는 것이 먼저 정의됨). `include/internal/cef_types_wrappers.h`에서 `class CefX : public cef_x_t`, `class CefX : public CefStructBaseSimple<cef_x_t>`, `using CefX = CefStructBaseSimple<cef_x_t>`로 C++ 클래스를 찾고, `cef_x_t`의 선언에서 필드를 읽습니다(`tools/gen/model.py`의 `Model.structs`). 필드는 기본형(`int`, `uint32_t`, `float`, `char16_t` 등), 열거형(Python 열거형이 되고 값은 `int`로 넣을 수 있음), 다른 구조체일 수 있습니다. 맨 앞의 `size_t size`는 C API의 버전 머리라서 필드로 두지 않습니다(C++ 클래스가 채움). 문자열(`cef_string_t`)은 `str`, 시간(`cef_basetime_t`)은 `datetime`이며, 이런 구조체는 `using CefX = CefStructBase<CefXTraits>;`와 `struct CefXTraits { using struct_type = cef_x_t; ...}`로 찾습니다. **모든 구조체의 모든 필드에 기본값**(0, `0.0`, `""`, `None`, 안쪽 구조체는 `Rect()`)이 있어서 `PdfPrintSettings(scale=1.0)`처럼 필요한 것만 줄 수 있습니다(C++의 기본 생성과 같음). 포인터, 배열, 문자열이 하나라도 있으면 지원하지 않습니다(`CefCursorInfo`, `CefCookie` 등).

- Python에서는 `collections.namedtuple`입니다(`Rect(x, y, width, height)`). 예약어인 필드는 밑줄을 붙입니다(`Range.from_`).
- 입력(`const CefRect&`)은 `Rect` 또는 필드 수가 같은 시퀀스를 받고 아니면 `TypeError`입니다. 핸들러가 받을 때는 `Rect`로, 출력 인자는 핸들러가 `Rect` 또는 튜플로 돌려줍니다.
- 구조체는 범위와 상관없이 항상 생성합니다(호출하는 쪽이 `Rect`를 만들어 CEF에 넘기기 때문입니다).
- C++ 프록시의 표에서는 입력이 `const CefRect*`, 출력이 `CefRect*`이고, 프록시가 값을 복사합니다.

## 메서드 계획 규칙

- 라이브러리 쪽 클래스(CEF가 구현): Python이 부릅니다. 비상수 참조 인자는 **출력 인자**로 보고 Python 반환값으로 돌려줍니다(반환값이 있으면 그것이 먼저이고, 값이 하나면 그대로, 둘 이상이면 튜플). 기본형, 문자열, 열거형, 문자열 벡터는 출력 전용이라 인자에서 빠지고(`ok, key_code, shift, ctrl, alt = menu.get_accelerator(command_id)`), **구조체 참조는 입출력**이라 인자로 받아 바뀐 값을 돌려줍니다(`display.convert_point_to_pixels(point)`). 객체 참조(`CefRefPtr&`)는 아직 미지원입니다. 클라이언트 객체를 반환하는 메서드도 미지원입니다. 구조체는 입력(`const CefRect&`)과 반환값으로 쓸 수 있습니다.
- 클라이언트 쪽 클래스(핸들러): CEF가 부릅니다. 출력 인자(비상수 참조의 기본형, 문자열, 열거형, 구조체)는 Python 메서드의 반환값이 됩니다. 문자열 벡터는 입력(`const std::vector<CefString>&`)으로만 받고 `list[str]`로 전달됩니다. 구조체를 값으로 **반환**하는 핸들러 메서드는 아직 미지원입니다. 반환값이 먼저이고, 하나면 그대로, 둘 이상이면 튜플입니다.
- `void*`와 크기는 `Buffer` 하나로 합쳐집니다(핸들러 쪽만).
- 핸들러의 `T* flag`(비 const 포인터, 기본형)는 `T&`처럼 출력 인자이고 프록시가 `if (flag) *flag = ...`로 씁니다(`OnPreKeyEvent`의 `is_keyboard_shortcut`). 구조체를 값으로 반환하는 핸들러 메서드(`GetPdfPaperSize`)는 숨은 마지막 출력 인자로 받아 프록시가 반환합니다.
- 헤더가 `optional_param`으로 표시한 인자만 `None`을 허용합니다. 라이브러리 메서드에 허용되지 않은 곳에 `None`을 넘기면 C++가 죽는 대신 `TypeError`입니다.
- 이름: `Cef` 접두사를 떼고 클래스는 그대로, 메서드와 인자는 snake_case, 예약어는 밑줄을 붙입니다(`Continue` → `continue_`).

## 범위와 커버리지

생성할 클래스는 `tools/gen/scope.py`의 목록(라이브러리 20개, 핸들러 9개, 함수 3개)입니다. 클래스를 추가하면 그 클래스를 인자나 반환으로 쓰던 메서드도 함께 열립니다. 범위 안인데 생성하지 못한 메서드는 조용히 빠지지 않고 [커버리지 보고서](../reference/coverage-report.md)에 이유와 함께 남습니다([생성 범위와 커버리지](../reference/generated-api-coverage.md)).

## 아직 없는 것

- `CefRawPtr`인 벡터, 라이브러리 메서드에 주는 객체 목록, 맵, 소유 포인터(`CefOwnPtr`), 평범한 데이터가 아닌 구조체(포인터, 배열, 문자열이 있는 `CefCursorInfo`, `CefAcceleratedPaintInfo`, `CefCookie` 등)
- 상속 관계가 있는 라이브러리 클래스(부모 클래스가 `CefBaseRefCounted`가 아닌 경우)
- 라이브러리 메서드의 객체 참조 출력 인자(`CefRefPtr<T>&`), 핸들러 메서드의 구조체 반환과 벡터 출력
- 헤더 주석의 한국어 번역(`cef_origin` 위키의 설명)을 스텁에 쓰는 일

남은 일과 순서는 [생성기의 한계와 다음 단계](../reference/generated-api-coverage.md)에 있습니다.

## 관련 페이지

- [핸들러 프록시 구조](handler-proxies.md)
- [생성기 모듈](../components/generator-modules.md)
- [새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
