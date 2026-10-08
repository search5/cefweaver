---
title: Cython 확장 모듈 (_cefweaver)
type: component
sources:
  - cefweaver/_cefweaver.pyx
  - cefweaver/cefwrapper.pxd
  - cefweaver/__init__.py
  - pyproject.toml
updated: 2026-10-08
---

# Cython 확장 모듈 (_cefweaver)

Python 쪽의 손으로 쓴 부분입니다. 확장 모듈은 **하나**(`cefweaver._cefweaver`)이고 Linux에서는 `_cefweaver.cpython-<버전>-x86_64-linux-gnu.so`, Windows에서는 `.pyd`가 됩니다(setuptools가 이름을 정합니다). cefpython이 `.pyx` 약 47개를 `include`로 합쳐 하나의 모듈로 만드는 것과 구조가 같지만 규모는 훨씬 작습니다([관련 프로젝트](../reference/related-projects.md)).

## 파일

| 파일 | 역할 |
| --- | --- |
| `cefweaver/_cefweaver.pyx` | 모듈 본체(약 290줄). `CefApp` 클래스, JS 바인딩 중계, `add_resource` 구현. 생성된 `cef_api.pxi`를 `include`합니다. |
| `cefweaver/cefwrapper.pxd` | `CefWrapper`와 `CefValueWrapper`의 C++ 선언. 블록될 수 있는 메서드는 `nogil`입니다. |
| `cefweaver/cef_api.pxd`, `cef_api.pxi` | 생성 파일([생성된 파일](generated-files.md)) |
| `cefweaver/__init__.py` | 패키지 진입점 |
| `cefweaver/_cefweaver.pyi`, `py.typed` | 타입 스텁(생성). PEP 561 표식 |

## _cefweaver.pyx의 구성

1. 모듈 docstring: GIL 규칙([프로세스 모델과 스레드](../concepts/process-model-and-threads.md))
2. `_utf8()`: `str`, `bytes`, `os.PathLike`를 UTF-8 `bytes`로 바꿉니다(Cython이 `std::string`으로 변환).
3. `_to_python()`, `_dispatch()`: JS 바인딩의 C 콜백. `noexcept with gil`이고 모든 예외를 `sys.excepthook`으로 보냅니다.
4. `include "cef_api.pxi"`: 생성된 래퍼들. 이 줄 뒤부터 `Request`, `ResourceHandler` 같은 이름을 쓸 수 있습니다.
5. `_StaticResource`, `_StaticResourceFactory`, `_resource_key()`: `add_resource`의 구현([리소스 제공](../concepts/resource-serving.md))
6. `cdef class CefApp`: 공개 API([Python API 참조](../reference/python-api.md))
7. 맨 끝의 `__all__ = ["CefApp"] + __generated_all__`

## CefApp의 내부

- 멤버: `CefWrapper* _wrapper`, `_initialized`, `_shut_down`, `_callbacks`(바인딩 콜백의 수명을 유지하는 목록), `_resources`, `_resource_hosts`.
- `__cinit__`에서 `new CefWrapper()`. `__dealloc__`는 CEF가 실행 중이면 삭제하지 않고 남겨 둡니다.
- 모든 CEF 호출이 `with nogil:` 안에 있고, 문자열 인자는 GIL을 쥔 채 먼저 `std::string`으로 변환합니다.
- 설정 메서드는 `_require_not_initialized()`, 동작 메서드는 `_require_running()`으로 상태를 검사해서 `RuntimeError`를 냅니다.

## __init__.py

1. 패키지 디렉터리를 구합니다.
2. Linux: `libcef.so`가 있으면 `ctypes.CDLL(..., RTLD_GLOBAL)`로 **먼저** 올립니다. Windows: `os.add_dll_directory`(시험하지 못했습니다).
3. `from . import _cefweaver`와 `from ._cefweaver import *`를 하고 `__all__ = list(_cefweaver.__all__)`로 이름을 공개합니다. 공개 이름은 생성기가 만든 목록과 `CefApp`입니다.

## 모듈을 불러올 때

생성된 `cef_api.pxi`의 맨 앞이 `cef_api_hash(CEF_API_VERSION, 0)`를 호출하고, 반환된 해시가 컴파일에 쓴 헤더의 `CEF_API_HASH_PLATFORM`과 다르면 `ImportError`를 냅니다. CEF는 이 호출로 API 버전을 설정하며, 설정 전에 라이브러리 객체(`Request.create()` 등)를 쓰면 `CefRequest_0_CppToC called with invalid version -1` FATAL로 프로세스가 중단되기 때문입니다([실험으로 확인한 사실](../reference/verified-findings.md)).

## 빌드 설정

확장은 `pyproject.toml`의 `[[tool.setuptools.ext-modules]]`에 선언되어 있고 `setup.py`는 없습니다. 자세한 내용은 [패키징](packaging.md)에 있습니다.

## 관련 페이지

- [CefWrapper 클래스](native-library-api.md)
- [JavaScript 바인딩](../concepts/javascript-bindings.md)
- [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md)
