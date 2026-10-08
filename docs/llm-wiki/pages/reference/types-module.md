---
title: types 모듈 (열거형과 값 타입)
type: reference
sources:
  - tools/gen/model.py
  - tools/gen/emit_types.py
  - tools/gen/emit_cython.py
  - tools/gen/emit_pyi.py
  - cefweaver/types.py
  - cefweaver/__init__.py
  - tests/test_generator.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# types 모듈 (열거형과 값 타입)

`cefweaver.types`는 CEF의 열거형과 값 타입 구조체를 파이썬 타입으로 모은 모듈입니다. `cefweaver/types.py`는 순수 파이썬 파일이고(컴파일된 코드 없음) 생성기가 CEF 헤더에서 만듭니다. 직접 고치지 않습니다.

```python
from cefweaver import types

host.send_mouse_click_event(
    types.MouseEvent(50, 60, types.EventFlags.SHIFT_DOWN | types.EventFlags.CONTROL_DOWN),
    types.MouseButtonType.LEFT, False, 1)

class Load(cefweaver.LoadHandler):
    def on_load_error(self, browser, frame, error_code, error_text, failed_url):
        if error_code == types.ErrorCode.ABORTED:     # error_code is an ErrorCode
            return
```

## 들어 있는 것

| 종류 | 개수 | 파이썬 | 예 |
| --- | --- | --- | --- |
| 열거형 | 100 (멤버 1,309개) | `enum.IntEnum` | `MouseButtonType`, `ErrorCode`, `TransitionType`, `ResourceType`, `RuntimeStyle` |
| 비트 플래그 | 17 (위 100개에 포함) | `enum.IntFlag` | `EventFlags`, `DragOperationsMask`, `SchemeOptions`, `LogItems` |
| 값 타입 구조체 | 23 | `typing.NamedTuple` | `Point`, `Rect`, `Size`, `Insets`, `Range`, `MouseEvent`, `DraggableRegion`(필드 `bounds`가 `Rect`), `KeyEvent`(필드 `type`이 `KeyEventType`), `ScreenInfo`, `PopupFeatures`, `TouchEvent`, `TouchHandleState`, `CompositionUnderline`, `AudioParameters`, `BoxLayoutSettings`, `BrowserSettings`(문자열, `State`, 색) |

값 타입은 `cefweaver.Rect`와 같은 객체입니다(`cefweaver.Rect is cefweaver.types.Rect`). 열거형은 `cefweaver.types`에만 있습니다.

## 값은 정수와 튜플 그대로 통합니다

- CEF에 넘길 때는 `IntEnum`/`IntFlag`가 `int`의 하위 클래스이고 `NamedTuple`이 튜플이라서 **일반 정수와 튜플도 그대로** 됩니다. `send_mouse_click_event(event, 0, False, 1)`도 동작합니다.
- CEF에서 받을 때(핸들러의 인자, 라이브러리 메서드의 반환값)는 **멤버로 변환**합니다. 열거형의 멤버에 없는 값을 CEF가 주면 변환하지 못하고 **일반 `int`로 그대로** 전달합니다(예외를 내지 않음). `IntFlag`는 멤버의 조합이어도 변환됩니다.
- 그래서 `error_code == -102`와 `error_code is types.ErrorCode.CONNECTION_REFUSED`가 모두 참입니다.
- 타입 스텁: 받는 쪽은 `ErrorCode`, 라이브러리에 주는 쪽은 `MouseButtonType | int`입니다(`mypy`가 일반 정수도 받게 하려고).

모든 필드에 기본값이 있습니다(C++의 기본 생성과 같게 0, `0.0`, `""`, `None`). 구조체의 필드가 다른 구조체일 수 있습니다(`DraggableRegion.bounds`). 이때 안쪽 구조체가 먼저 정의됩니다. 필드가 열거형이면 그 열거형의 클래스가 타입이 됩니다(`KeyEvent.type`). C API의 `size` 머리는 필드에 없고 C++ 클래스가 채웁니다.

## 이름 규칙

- 클래스 이름: C 이름에서 `cef_`와 `_t`를 떼고 CamelCase로 바꿉니다(`cef_mouse_button_type_t` → `MouseButtonType`). C++ 헤더의 `typedef cef_errorcode_t ErrorCode;` 같은 별칭은 **철자의 대소문자만 다를 때**(`Errorcode`와 `ErrorCode`) 별칭을 씁니다. 클래스 안에서만 뜻이 통하는 별칭(`CefContextMenuParams`의 `TypeFlags`)은 쓰지 않고 `ContextMenuTypeFlags`로 만듭니다. 이름이 겹치지 않는 것을 시험이 확인합니다.
- 멤버 이름: 모든 멤버가 공유하는 접두사를 뗍니다(`MBT_LEFT` → `LEFT`, `ERR_ABORTED` → `ABORTED`, `CEF_RUNTIME_STYLE_ALLOY` → `ALLOY`). 떼면 이름이 겹치거나 숫자로 시작하면 `_`를 붙이거나 전체 이름을 유지합니다.

## 값을 읽는 방법 (`tools/gen/model.py`)

헤더의 `typedef enum { ... } cef_x_t;`를 파싱합니다. 값은 정수, 시프트(`1 << 3`), 앞 멤버의 참조, `|`, `&`, `+`, `-`, `~`로 계산합니다(`ast`로 허용한 연산만).

- **전처리 조건**: `#if CEF_API_ADDED(버전)`은 **최신 API**로 보고 참, 그 `#else`와 `#elif` 가지는 거짓입니다. `#if !defined(GENERATING_CEF_API_HASH)`도 참입니다. 다른 조건이 나오면 그 열거형을 건너뜁니다.
- **네트워크 오류 목록**: `cef_errorcode_t`는 본문에서 `#define NET_ERROR(label, value) ERR_##label = value,`와 `#include "include/base/internal/cef_net_error_list.h"`로 250개의 오류를 가져옵니다. 생성기가 그 파일의 `NET_ERROR(이름, 값)` 줄을 읽어 확장합니다(`ErrorCode.CONNECTION_REFUSED == -102`).
- **비트 플래그 판별**: 이름이 `_flags_t`나 `_mask_t`로 끝나고 단일 비트 값이 둘 이상이거나, 값이 0이 아닌 멤버가 모두 단일 비트이고 셋 이상이면 `IntFlag`입니다. 열거형과 플래그가 섞인 `TransitionType`은 `IntEnum`입니다.
- **건너뛰는 것**: `cef_color_id_t`(매크로 파일로 만든 목록) 하나입니다. 건너뛴 열거형은 이유가 `Model.enum_skipped`에 남고, 그 열거형을 쓰는 메서드는 전과 같이 `int`로 다룹니다.

## 시험

생성기 시험은 값 읽기(마우스 버튼, 오류 코드, 평가된 시프트, 마스크), 플래그 판별, 전처리 분기, 멤버 중복 없음, 생성된 `types.py`를 실행해서 `IntEnum`, `IntFlag`, `NamedTuple`이 동작하는지를 확인합니다. 통합 시험은 라이브러리 메서드의 반환이 멤버인지(`request.get_resource_type()`), 핸들러가 `ErrorCode` 멤버를 받는지, 수정자 플래그(`SHIFT_DOWN | CONTROL_DOWN`)가 페이지의 `shiftKey`와 `ctrlKey`로 도착하는지를 확인합니다([시험](../components/tests.md)).

## 관련 페이지

- [Python API 참조](python-api.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [생성기 모듈](../components/generator-modules.md)
- [생성되는 파일](../components/generated-files.md)
