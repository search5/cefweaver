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
  - docs/conf.py
  - docs/Makefile
  - docs/guide/cookbook.rst
  - docs/guide/recipes/headless.py
updated: 2026-10-13
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

## 문서 만들기 (Sphinx)

`docs/`가 docstring을 읽어 영어와 한국어 문서를 만듭니다. 쪽(`api/*.rst`)은 모듈을 나열할 뿐이고 문장은 모두 소스에서 옵니다. 새 공개 모듈을 만들면 해당 쪽에 `automodule`을 더합니다(`tests/test_docs.py`가 `ui/`와 툴킷 모듈이 빠졌는지 확인합니다).

```sh
pip install -r docs/requirements.txt    # sphinx, sphinx-rtd-theme, sphinx-intl
# autodoc은 컴파일된 확장을 import하므로 wheel을 설치한 환경에서, Qt 모듈을 읽으려면 PyQt6와 Pillow도
cd docs
make html            # _build/html/en, 경고가 있으면 실패(-W), nitpicky라 끊어진 참조도 경고
make html-all        # en과 ko
make update-po       # 원문이 바뀌었을 때 locale/ko의 .po 갱신
```

- **언어**: 원문은 영어이고(`language = "en"`), 한국어는 `locale/ko/LC_MESSAGES/<문서>.po`의 번역입니다(`gettext_compact = False`라 문서마다 파일이 있습니다). `make update-po` 뒤 비어 있는 항목이 새로 생긴 원문이며, 비워 두면 영어 원문으로 나옵니다. 한국어 조사가 리터럴이나 역할 바로 뒤에 올 때는 `` ``x``\\ 를 ``처럼 백슬래시와 공백을 넣어야 reST가 읽습니다. `.mo`와 `.pot`은 커밋하지 않습니다(빌드할 때 컴파일).
- **napoleon**: Google 스타일만 읽고(`napoleon_google_docstring = True`, numpy 끔) `Attributes:`는 `:ivar:`로 렌더링합니다(`napoleon_use_ivar`). 켜 두지 않으면 같은 속성이 `.. attribute::`와 autodoc 항목으로 두 번 나옵니다.
- **Qt 신호**는 `Signal` 객체 자체의 `__doc__`가 raw `*`를 포함해 경고가 되므로 `#:` 주석으로 문서화합니다.
- **헤더의 주석**을 RST로 바꿀 때 일어난 문제는 생성기가 처리합니다(`tools/gen/docs.py`): 들여쓴 목록과 중첩, 코드 예시(`::` 블록), `<pre>`와 `<b>`, 와일드카드(`text/*`), 한 겹 역따옴표, 리터럴 바로 뒤의 `(`.

## 사용 안내 (guide)

`docs/guide/*.rst`는 docstring이 아니라 손으로 쓴 사용 안내입니다(설치, 시작하기, 쿡북, 개념, 메시지 루프, GUI 툴킷에 넣기, 핸들러와 이벤트, JavaScript 브리지, Views, 툴킷별 상태, 컨텍스트 메뉴, 소리와 권한, 인쇄, Cast, 구성, Wayland와 GPU, 문제 해결, 한계, 개발하기). 이전 Jekyll 쪽의 주제를 이어받되 문장은 영어로 새로 썼고, 사실은 위키와 소스, 예제(`examples/`)에서 확인한 것만 적었습니다. 한국어는 `locale/ko/LC_MESSAGES/guide/*.po`입니다.

- 쿡북이 보이는 스크립트 `docs/guide/recipes/headless.py`는 설치된 wheel로 `xvfb-run python -P`를 써서 실제로 실행해 `evaluate: {'v': 'hello', 'e': None}`, `snapshot: True True`, `ok [..., 'sum=5']`가 나오는 것을 확인했습니다(2026-10-13).
- **문서는 소스에서 새로 빌드한 wheel로 빌드하고 확인합니다.** 오래된 wheel(2026-10-11 빌드)로 빌드하면 `_cefweaver.*` docstring이 소스와 달라 경고가 나고, 그 상태로 `make update-po`를 돌리면 api 카탈로그가 훼손됩니다. 2026-10-13에 `CEF_ROOT=... uv build --wheel`로 새 wheel을 만든 뒤 영어와 한국어 `-W` 빌드가 경고 없이 통과했고(Qt와 Tk 툴킷 모듈은 PyQt6와 Pillow가 있어야 import됩니다), 전체 `update-po`가 기존 카탈로그를 바꾸지 않았습니다.
- 2026-10-13에 자매 프로젝트 cefloom과 주제를 맞추려고 개념, 메시지 루프, JavaScript 브리지, 인쇄, 구성, 문제 해결 6쪽을 더했습니다. 예제는 `docs/guide/recipes/`에 있고 모두 새 wheel로 3회 같은 결과를 냈습니다. 쪽의 서술은 소스를 읽거나 실행해서 확인한 것만 썼고, 확인하지 못한 것은 쪽에 "not tried"로 적었습니다.
- 게시: `.github/workflows/docs.yml`이 main에 푸시될 때(`docs/`, `cefweaver/`, `native/` 변경) wheel을 빌드하고 `make -C docs site`로 영어와 한국어 사이트를 만들어 GitHub Pages(https://search5.github.io/cefweaver/)에 올립니다. 첫 실행은 빌드 7분 13초, 배포 11초로 성공했습니다. 러너에는 PyQt6와 Pillow도 설치합니다.
- 기능이나 동작을 바꾸면 해당 guide 쪽을 같은 작업에서 고칩니다. 쪽이 목차에서 빠지지 않았는지는 `tests/test_docs.py`가 확인합니다.

## 누락 점검

`tests/test_docstrings.py`가 손으로 쓴 Python의 공개 모듈, 클래스, 함수, 메서드(비공개와 `__init__` 제외)와 생성된 타입 스텁(`_cefweaver.pyi`)의 공개 클래스와 메서드에 docstring이 있는지, 스텁에 헤더식 `|name|`이 남지 않았는지 확인합니다. 작업 중인 모듈은 `PENDING` 목록에 두고, 지금은 비어 있습니다.

## 진행 상황

[docstring 진행 상황](../reference/docstring-coverage.md)에 모듈별 상태를 적습니다.

## 관련 페이지

- [docstring 진행 상황](../reference/docstring-coverage.md)
- [시험 실행하기](run-tests.md)
