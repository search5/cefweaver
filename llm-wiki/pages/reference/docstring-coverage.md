---
title: docstring 진행 상황
type: reference
sources:
  - tests/test_docstrings.py
  - docs/conf.py
updated: 2026-10-13
---

# docstring 진행 상황

규칙은 [docstring 쓰기](../procedures/write-docstrings.md)에 있습니다. 작성 상태는 `tests/test_docstrings.py`의 `PENDING` 목록이 기계적으로 보여 주고, 아래 표는 작업 범위를 나눈 기록입니다.

| 범위 | 상태 |
| --- | --- |
| 손으로 쓴 Python (`cefweaver/*.py`, `ui/`, `ui/toolkits/`) | 완료. 공개 모듈, 클래스, 함수, 메서드 모두 있음(시험이 확인). 툴킷 구현의 어댑터 메서드와 이벤트 처리기는 한 줄입니다. |
| `cefweaver/_cefweaver.pyx`와 `tools/gen/handwritten.pyi`의 공개 API | 완료. 두 곳의 내용이 같습니다. |
| 생성되는 클래스와 메서드 (`api/*.pxi`, `_cefweaver.pyi`) | 완료. 공개 클래스와 메서드마다 있음(시험이 확인). `Args:` 설명은 헤더가 말한 곳에만 있습니다. |
| 생성되는 열거형과 값 타입 (`types/`) | 클래스는 모두 있음. 멤버 1,309개 중 608개, 필드 183개 중 45개는 헤더에 주석이 없어 docstring이 없습니다. |

## Sphinx로 만들어 본 결과 (2026-10-13)

`docs/`(Sphinx 9.1, `sphinx_rtd_theme` 3.1, Python 3.12, Linux)에서 wheel을 설치하고 `nitpicky = True`와 `-W`(경고를 오류로)로 영어와 한국어 모두 경고 없이 만들었습니다.

- **끊어진 참조를 확인했습니다.** 처음에는 모호한 참조 경고(`ref.python`)를 꺼 두었다가 사용자가 지적해서 `nitpicky`로 확인했고 약 400개의 경고가 나왔습니다. 원인과 처리: (1) `cefweaver.ui.X`, `cefweaver.types.X`로 쓴 참조가 `ui.view.X`, `types.enums.X` 이름으로 문서화되어 끊어짐 → 쪽이 패키지 이름공간(`automodule:: cefweaver.ui`, `cefweaver.types`)을 문서화하게 바꿈. (2) 생성된 `:meth:`가 상속받은 메서드(`Window.set_bounds`는 `View`가 선언)를 가리킴 → 생성기가 선언한 클래스로 연결(`docs.set_owners`). (3) 생성된 `:class:`가 열거형 쪽에서 상대 이름이라 끊어짐, Args의 `Frame`이 `cefweaver.ui.Frame`과 모호함 → `~cefweaver.X`, `cefweaver.types.X`로 한정. (4) 열거형 멤버와 필드의 docstring에서 napoleon이 첫 콜론 앞(`file://`, "to whit: ")을 타입으로 읽음 → `conf.py`가 앞에 `:`를 붙여 막음. (5) 손으로 쓴 `:attr:` 6개와 `:func:` 1개가 대상이 없음 → 리터럴과 전체 경로로 고침.
- **끄지 않고 남긴 것**: 툴킷 모듈의 Args 타입(`Gdk.*`, `Gtk.*`, `Qt.*`, `QWidget`, `wx.*`, `cairo.*` 등 외부 툴킷의 타입)과 `optional`, `callable`, `iterable` 같은 타입 설명용 낱말은 `nitpick_ignore_regex`로 둡니다. 외부 툴킷의 문서는 이 문서의 대상이 아니기 때문이며, 다른 이름이 같은 패턴에 걸려 가려질 수 있습니다.
- 처음 만들었을 때 생성된 docstring에서 약 50개의 RST 오류와 경고가 나와(들여쓴 목록, 중첩 목록, 코드 예시, 와일드카드 `*`, `<pre>`, 리터럴 뒤의 `(`, `|margin_*|`) 생성기(`docs.py`, `model.py`, `emit_types.py`)를 고쳤습니다. 컴파일된 확장의 docstring을 `autodoc`이 읽는 것을 확인했습니다.
- 컴파일된 확장은 시그니처가 없습니다(`embedsignature` 꺼짐). 생성된 클래스의 메서드는 인자 이름만 보이고 타입은 `Args:`에만 있습니다.
- **한국어 번역을 모두 채웠습니다**: `locale/ko`의 5개 카탈로그 5,167개 항목이 모두 번역되어 있습니다(`msgfmt --statistics`로 미번역 0). 번역은 서브에이전트 23개가 조각(약 220항목)으로 나누어 했고, 병합 전에 각 항목의 리터럴(`` ``x`` ``)과 역할(`:class:` 등)이 원문에 있던 것이 모두 보존되었는지 기계적으로 확인했습니다(5,114개 고유 항목 중 실패 0). 한국어 조사가 리터럴 바로 뒤에 올 때는 reST가 요구하는 `\ `를 병합 단계에서 자동으로 넣었습니다. **두 번째 검수자(서브에이전트 23개)가 5,114개 고유 항목을 모두 원문과 대조했고 506개를 고쳤습니다**(대부분 용어집 위반: thread, callback, handler, browser, cookie, cache를 영어로 둔 것, 합쇼체가 아닌 "-하십시오", 조건이 뒤집힌 번역 2건, 문장 끝의 콜론 누락). 검수 뒤에 용어(thread, callback, handler, cookie, cache, browser, popup, toolkit, offscreen)를 코드 표기 밖에서 한 번 더 일괄 통일했습니다. 이 검수도 모델이 한 것이라 사람의 감수는 아닙니다. 영어 원문이 바뀌면 `make update-po`가 그 항목을 비운 채로 두므로 그때 다시 번역해야 합니다.

## 확인하지 못한 것

- `Signals:`(gtk3)와 `Events:`(kivy)처럼 napoleon이 모르는 절이 어떻게 보이는지, 화면에서 모양을 눈으로 확인하지는 않았습니다(경고가 없다는 것만 확인).
- 서브에이전트가 쓴 영어 설명을 코드와 하나씩 대조하지는 않았습니다. 코드가 그대로인지만 AST 비교로 확인했습니다.
- macOS와 Windows에서 같은 문서가 만들어지는지는 확인하지 못했습니다(툴킷 모듈은 Linux에서 mock으로 읽습니다).
- 호스팅(Read the Docs, GitHub Actions)은 정하지 않았습니다.

## 관련 페이지

- [docstring 쓰기 (Sphinx용)](../procedures/write-docstrings.md)
