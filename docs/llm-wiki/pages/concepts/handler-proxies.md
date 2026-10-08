---
title: 핸들러 프록시 구조
type: concept
sources:
  - tools/gen/emit_cpp.py
  - tools/gen/emit_cython.py
  - native/cefwrapper/generated/cefweaver_proxies.h
  - cefweaver/cef_api.pxi
updated: 2026-10-08
---

# 핸들러 프록시 구조

CEF의 핸들러(애플리케이션이 구현하는 클래스, 파서 용어로 client-side)를 Python 클래스로 구현하게 하는 장치입니다. 지금은 `ResourceHandler`, `SchemeHandlerFactory`, `Client`, `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`가 이 방식이며, 이후 핸들러도 같은 구조로 생성됩니다.

## 구성

핸들러 클래스마다 생성기가 세 가지를 만듭니다(`native/cefwrapper/generated/cefweaver_proxies.h`).

- `Cw<이름>Callbacks`: 함수 포인터 표입니다. 소유자(`void* py`), 해제 함수(`release`), 메서드마다 `fn_<메서드>` 항목이 있습니다.
- `Cw<이름>Proxy`: CEF 클래스를 상속해 모든 가상 메서드를 구현하는 C++ 클래스입니다. 각 메서드는 표의 항목을 부릅니다.
- `Cw<이름>Forward`: 손으로 쓴 핸들러가 이벤트를 **관찰하고도 사용자에게 넘기게** 하는 기반 클래스입니다([전달 클래스](#전달-클래스)).

Cython 쪽(`cefweaver/cef_api.pxi`)은 Python 기반 클래스(예: `class ResourceHandler`), 메서드마다 CEF가 부르는 **트램펄린** 함수(`noexcept with gil`), 표를 채우고 프록시를 만드는 `_g_make_*`, CEF에 넘길 참조(+1)를 만드는 `_g_export_*`, CEF 객체를 감싸는 `_wrap_*`를 만듭니다.

```
CEF 스레드 --> Cw...Proxy::Method() --> 표의 함수 포인터 --> 트램펄린(with gil) --> Python 메서드
```

## 재정의하지 않은 메서드

`_g_make_*`는 `getattr(type(obj), 이름) is not 기반클래스.이름`일 때만 표에 항목을 넣습니다. 즉 **사용자가 재정의한 메서드만** 표에 들어갑니다. 항목이 없으면 프록시는 CEF 기반 클래스의 구현을 그대로 부릅니다(`CefResourceHandler::Open(...)`). 메서드가 순수 가상(`= 0`)이면 기반 클래스에 구현이 없으므로 반환 형식의 기본값(`false`, `0`, 빈 참조)을 돌려줍니다. 순수 가상 여부는 파서가 알려 주지 않아서 `Model.is_pure_virtual()`이 헤더 본문에서 찾습니다. 이 감지가 처음에 틀려서 순수 가상 함수를 호출하는 코드가 생성된 적이 있습니다([설계 결정 기록](../reference/design-decisions.md)).

## 전달 클래스

래퍼는 이벤트를 사용자에게 넘기기 전에 스스로 해야 할 일이 있습니다(로드가 끝나면 준비 플래그를 켜는 것 등). 그래서 사용자의 핸들러를 CEF에 곧바로 넘기지 않고, 래퍼의 핸들러가 CEF의 호출을 받아 자기 일을 한 뒤 사용자의 핸들러로 넘깁니다.

`Cw<이름>Forward`는 이 "넘기기"를 생성한 코드입니다. `forward_<이름>_`(해당 CEF 클래스의 `CefRefPtr`) 멤버에 대상이 있으면 그 대상의 같은 메서드를 부르고, 비어 있으면 CEF 기반 클래스의 구현(순수 가상이면 반환 형식의 기본값)을 부릅니다. 인자는 선언 그대로 전달되므로 값 변환이 필요 없고, 출력 인자는 참조로 그대로 이어집니다.

- **참조 계수를 구현하지 않습니다.** 한 객체가 `CwDisplayHandlerForward`, `CwLifeSpanHandlerForward`, `CwLoadHandlerForward`를 함께 상속하고 `IMPLEMENT_REFCOUNTING`을 한 번만 쓰게 하기 위해서입니다. 이 조합이 컴파일되는지는 생성기 시험(`test_forwarders_combine_in_one_reference_counted_class`)이 실제 컴파일러로 확인합니다.
- 전달 대상은 래퍼의 `Get...Handler()`가 CEF가 물을 때마다 사용자의 클라이언트에서 다시 얻어 넣습니다. 그래서 사용자의 `get_load_handler()`는 이벤트마다 Python에서 실행될 수 있고, 매번 새 객체를 돌려줘도 됩니다.

## 값의 전달 방식

| 종류 | 표의 C 타입 | Python 쪽 |
| --- | --- | --- |
| 기본형(`bool`, 정수, 실수) | 원래 타입 | 그대로 |
| 열거형 | `int` | `int` |
| 문자열 입력 | `const CefString*` | `str` |
| CEF 객체(`CefRefPtr<T>` 입력) | `T*` | 생성된 래퍼 객체(`None`이면 널) |
| 출력 인자 | 포인터(`T*`, `CefString*`) | 메서드의 **반환값** |
| `void*`와 크기 쌍 | `void*`, 크기 타입 | 쓰기 가능한 `memoryview` |
| 핸들러 반환(`CefRefPtr<T>` 반환) | `T*` (참조 1개를 넘김) | 핸들러 객체 또는 `None` |

- 반환값은 반환 형식이 `void`가 아니면 그것이 먼저이고 그 뒤에 출력 인자가 순서대로 옵니다. 값이 하나면 그대로, 둘 이상이면 튜플입니다. 개수가 맞지 않으면 예외가 되고 보고됩니다.
- 핸들러가 객체를 돌려줄 때(`create`) 트램펄린은 `AddRef()`한 원시 포인터를 넘기고, 프록시는 `CefRefPtr`로 받은 뒤 `Release()`해서 참조 수를 맞춥니다.
- 입력 객체의 원시 포인터는 호출 동안만 유효합니다. 트램펄린이 `CefRefPtr`로 감싸 래퍼 객체를 만들면서 참조를 늘립니다.

## 수명과 오류

- 프록시가 Python 소유자를 `Py_INCREF`로 붙들고, 프록시가 소멸하면 `release`(`_g_release`, `with gil`)가 `Py_DECREF`합니다. 소멸은 CEF 스레드에서 일어날 수 있으므로 GIL을 다시 얻습니다.
- 트램펄린 안의 모든 예외는 `_g_report()`를 거쳐 `sys.excepthook`으로 보고되고 반환 형식의 기본값(`0`, `NULL`)을 돌려줍니다. 예외가 C++로 넘어가지 않습니다.
- `CefApp.shutdown()`을 부르지 않고 프로세스가 끝나면 프록시 해제가 인터프리터 종료 뒤에 일어날 수 있습니다. 이 경우는 시험하지 않았습니다.

## 관련 페이지

- [바인딩 생성기의 설계](binding-generator.md)
- [리소스 제공](resource-serving.md)
- [생성기 모듈](../components/generator-modules.md)
- [프로세스 모델과 스레드](process-model-and-threads.md)
- [C++ 핸들러](../components/native-handlers.md)
