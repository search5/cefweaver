---
title: docstring 쓰기 (Sphinx용)
type: procedure
sources:
  - tests/test_docstrings.py
  - cefweaver/ui/adapter.py
  - cefweaver/cast.py
  - tools/gen/docs.py
  - tools/gen/emit_types.py
  - tools/gen/handwritten.pyi
  - cefweaver/_cefweaver.pyx
updated: 2026-10-12
---

# docstring 쓰기 (Sphinx용)

나중에 Sphinx(`sphinx.ext.autodoc`와 `sphinx.ext.napoleon`)로 API 문서를 만들 수 있도록, 공개 API마다 영어 docstring을 둡니다. 형식은 Google 스타일이고, 참고한 것은 Google Python Style Guide의 docstring 절과 `requests`, `Flask` 같은 오픈소스의 레퍼런스식 주석입니다. 설명문을 늘어놓지 않고 계약(무엇을 받고, 무엇을 돌려주고, 언제 실패하는가)만 적습니다.

## 규칙

- **첫 줄**: 한 줄 요약이고 마침표로 끝납니다. 명령형(`Return the...`, `Load the...`)입니다. 클래스와 모듈은 명사구도 됩니다(`A browser view for a toolkit widget.`).
- **두 번째 줄은 비웁니다.** 더 필요하면 그다음에 본문을 씁니다.
- **절**: `Args:`, `Returns:`, `Yields:`, `Raises:`, `Attributes:`(클래스), `Example:`(필요할 때만). 인자는 `name (type): description` 형식입니다. 코드에 타입 힌트가 없으므로 타입을 여기에 적습니다. 선택 인자는 `(type, optional)`이고 기본값은 설명에 적습니다.
- **스레드와 시점**: 호출할 수 있는 스레드나 시점(`initialize()` 전후)이 제한되면 `Note:` 절에 한 줄로 적습니다.
- **참조**: 다른 대상은 `` :class:`~cefweaver.CefApp` ``, `` :meth:`~cefweaver.ui.BrowserView.load_url` ``처럼 Sphinx 역할로 가리킵니다. 코드 조각은 이중 역따옴표입니다.
- **쓰지 않는 것**: 구현 경위, 실험 결과, "왜 이렇게 했는가"는 docstring에 쓰지 않습니다. 필요하면 `#` 주석이나 위키(`reference/verified-findings*.md`)에 둡니다. 반환값이 없으면 `Returns:`를 쓰지 않습니다.
- **재정의한 메서드**: 부모 클래스(또는 `ToolkitAdapter` 같은 프로토콜)의 문서가 그대로 맞으면 짧은 한 줄만 둡니다. Sphinx는 `autodoc_inherit_docstrings`로 부모의 문서를 이어받을 수 있지만, 구조적 프로토콜은 상속이 아니므로 한 줄을 직접 둡니다.
- **비공개**: 밑줄로 시작하는 이름은 요구하지 않습니다. 쓰면 같은 형식입니다.
- **예시**:

```python
def seek(self, seconds):
    """Seek to a position in the current media.

    Args:
        seconds (float): The position from the start, in seconds.

    Raises:
        RuntimeError: If the session is closed.
    """
```

## 생성되는 API

`_cefweaver.pyi`, `api/*.pxi`, `types/`는 생성기가 만들므로 직접 고치지 않습니다. 생성기(`tools/gen/docs.py`, `emit_types.py`, `model.py`)가 CEF 헤더의 주석을 위 규칙에 맞게 바꿉니다. 클래스와 메서드, 열거형과 그 멤버, 값 타입과 그 필드의 설명이 모두 헤더의 주석에서 옵니다.

- 헤더에 주석이 없는 열거형 멤버(608개)와 값 타입 필드(45개)는 docstring이 없습니다. 지어내지 않습니다. 생성기를 고쳐서 채울 수 있는 것이 아니라 CEF가 설명하지 않은 것입니다.
- `Args:`의 설명은 헤더가 `|name| is ...`처럼 말한 곳에만 있고, 나머지는 `name (type):`로 타입만 보입니다(약 80%).
- 손으로 쓴 클래스(`QueryHandler`, `AppHandler`, `CefApp` 등)의 docstring은 `_cefweaver.pyx`와 `tools/gen/handwritten.pyi`에 같은 내용으로 둡니다.

## 누락 점검

`tests/test_docstrings.py`가 손으로 쓴 Python의 공개 모듈, 클래스, 함수, 메서드(비공개와 `__init__` 제외)와 생성된 타입 스텁(`_cefweaver.pyi`)의 공개 클래스와 메서드에 docstring이 있는지, 스텁에 헤더식 `|name|`이 남지 않았는지 확인합니다. 작업 중인 모듈은 `PENDING` 목록에 두고, 지금은 비어 있습니다.

## 진행 상황

[docstring 진행 상황](../reference/docstring-coverage.md)에 모듈별 상태를 적습니다.

## 관련 페이지

- [docstring 진행 상황](../reference/docstring-coverage.md)
- [시험 실행하기](run-tests.md)
