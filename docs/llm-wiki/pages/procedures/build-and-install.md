---
title: 빌드와 설치
type: procedure
sources:
  - README.rst
  - CLAUDE.md
  - tools/prepare.py
  - pyproject.toml
updated: 2026-10-08
---

# 빌드와 설치

Linux x86_64 기준입니다. 이 절차를 Python 3.11, 3.12, 3.13, 3.14에서 실행해서 확인했습니다.

## 준비물

- Linux x86_64, C++ 컴파일러(C++20 필요), CMake 3.19 이상, [uv](https://docs.astral.sh/uv/)
- Python 3.11 이상(`requires-python`)
- CEF를 내려받을 네트워크(prebuilt 사용 시)와 디스크 여유. 154 배포본은 압축본이 약 690MB(689,351,019바이트)이고 푼 디렉터리는 약 3.2GB입니다. `build/`는 약 3GB까지 커집니다.
- 시험하려면 `xvfb`(가상 X 서버)

## 절차

1. **사전 준비**: CEF 확보, 네이티브 빌드, 런타임 스테이징

   ```sh
   python tools/prepare.py
   ```

   `build/native/`에 `libcef_dll_wrapper.a`, `libcefwrapper.a`, `cefsubprocess`가 만들어지고, `build/native/cef`가 CEF 배포본을 가리키며, `cefweaver/`에 런타임이 복사됩니다. CEF를 직접 지정하거나 소스 빌드하는 방법은 [CEF 확보하기](obtain-cef.md)에 있습니다.

2. **wheel 빌드**

   ```sh
   uv build --wheel --python 3.13 -o dist
   ```

   **`--wheel`이 필수입니다.** 인자 없는 `uv build`는 sdist에서 wheel을 만드는 단계에서 CEF 헤더를 찾지 못해 실패합니다([패키징](../components/packaging.md)).

3. **설치**

   ```sh
   uv pip install dist/cefweaver-*.whl
   ```

4. **확인**

   ```python
   import cefweaver
   print(cefweaver.__all__)
   ```

## 다시 빌드할 때

- C++(`native/`)를 고쳤으면 `python tools/prepare.py`를 다시 실행한 뒤 wheel을 만듭니다. `pyproject.toml`의 `depends` 덕분에 정적 라이브러리가 바뀌면 확장 모듈도 다시 링크됩니다.
- `.pyx`나 생성 파일을 고쳤으면 wheel만 다시 만듭니다.
- CEF 헤더가 바뀌면(버전 변경) `python tools/gen/generate.py`가 먼저입니다([CEF 버전 올리기](update-cef-version.md)).
- 스테이징은 다시 실행해도 안전합니다. 이전에 스테이징한 항목을 지우고 새로 복사합니다.

## 자주 만난 문제

| 증상 | 원인과 해결 |
| --- | --- |
| `uv build`가 `include/cef_client.h`를 못 찾음 | `--wheel`을 쓰지 않았습니다. |
| `ImportError`: libcef.so를 못 찾음 | 스테이징이 안 된 wheel입니다. `prepare.py`를 `--no-stage` 없이 실행했는지 확인합니다. |
| 서브프로세스 경로가 옛 값 | 정적 라이브러리가 바뀌었는데 확장이 재링크되지 않은 경우입니다. 현재는 `depends`로 막혀 있지만 의심되면 `build/` 아래의 `lib.*`, `temp.*` 디렉터리를 지우고 다시 빌드합니다. |
| 구성 단계에서 clang-format 오류 | `CEFWEAVER_FETCH_CLANG_FORMAT`가 켜져 있습니다. 기본값은 꺼짐입니다. |

## 관련 페이지

- [CEF 확보하기](obtain-cef.md)
- [시험 실행하기](run-tests.md)
- [tools/prepare.py](../components/tool-prepare.md)
- [패키징](../components/packaging.md)
