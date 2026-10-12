---
title: docstring 진행 상황
type: reference
sources:
  - tests/test_docstrings.py
updated: 2026-10-12
---

# docstring 진행 상황

규칙은 [docstring 쓰기](../procedures/write-docstrings.md)에 있습니다. 작성 상태는 `tests/test_docstrings.py`의 `PENDING` 목록이 기계적으로 보여 주고, 아래 표는 작업 범위를 나눈 기록입니다.

| 범위 | 상태 |
| --- | --- |
| 손으로 쓴 Python (`cefweaver/*.py`, `ui/`, `ui/toolkits/`) | 완료. 공개 모듈, 클래스, 함수, 메서드 모두 있음(시험이 확인). 툴킷 구현의 어댑터 메서드와 이벤트 처리기는 한 줄입니다. |
| `cefweaver/_cefweaver.pyx`와 `tools/gen/handwritten.pyi`의 공개 API | 완료. 두 곳의 내용이 같습니다. |
| 생성되는 클래스와 메서드 (`api/*.pxi`, `_cefweaver.pyi`) | 완료. 공개 클래스와 메서드마다 있음(시험이 확인). `Args:` 설명은 헤더가 말한 곳에만 있습니다. |
| 생성되는 열거형과 값 타입 (`types/`) | 클래스는 모두 있음. 멤버 1,309개 중 608개, 필드 183개 중 45개는 헤더에 주석이 없어 docstring이 없습니다. |

## 확인하지 못한 것

- Sphinx로 실제 문서를 만들어 보지 않았습니다(`conf.py`가 없음). 상호 참조(`:class:`)가 모두 풀리는지, `Signals:`(gtk3)와 `Events:`(kivy)처럼 napoleon이 모르는 절의 표시는 확인하지 못했습니다.
- 컴파일된 확장 모듈에서 `autodoc`이 docstring과 시그니처를 읽는지(`embedsignature`는 켜지 않음)는 확인하지 못했습니다.
- 서브에이전트가 쓴 설명을 코드와 하나씩 대조하지는 않았습니다. 코드가 그대로인지만 AST 비교로 확인했습니다.

## 관련 페이지

- [docstring 쓰기 (Sphinx용)](../procedures/write-docstrings.md)
