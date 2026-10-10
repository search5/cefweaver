---
title: 설치와 빌드
---

# 설치와 빌드

이 쪽은 소스에서 빌드해 설치하는 방법을 설명합니다. CEF(Chromium)와 네이티브 라이브러리를 먼저 준비한 뒤 Python 패키지(wheel)를 만듭니다.

## 요구 사항

| 항목 | 내용 |
| --- | --- |
| 운영체제 | Linux x86_64, macOS arm64(Apple Silicon). Windows와 macOS x86_64는 검증하지 못했습니다 |
| Python | 프로젝트는 3.11 이상을 선언합니다. 이 저장소에서 시험한 것은 3.13입니다(예제는 3.13용 wheel을 가리킵니다) |
| 도구 | [uv](https://docs.astral.sh/uv/), C++ 컴파일러(macOS는 Xcode나 Command Line Tools). `cmake`와 `Cython`은 빌드가 알아서 받습니다 |
| 디스크와 네트워크 | 미리 빌드된 CEF를 내려받습니다(Linux는 압축 약 660 MB, 풀면 약 3.2 GB. macOS arm64는 압축 약 307 MB, 풀면 약 791 MB) |

## 빌드

저장소 루트에서 차례로 실행합니다.

```sh
python tools/prepare.py          # CEF 준비, 네이티브 빌드, 배치
uv build --wheel                 # dist/에 wheel을 만듭니다
```

`uv build`를 인자 없이 실행하면 sdist 단계에서 실패하므로 `--wheel`을 붙입니다.

macOS에서도 같은 명령입니다. 결과는 `cefweaver/cefsubprocess.app`(CEF 프레임워크와 도우미 앱, 약 325 MB)과 약 147 MB의 wheel입니다. python.org에서 받은 Python으로 `--list-versions`가 인증서 오류로 실패하면 `--cef-root`로 직접 받은 배포본을 가리키세요.

`prepare.py`의 선택지:

```sh
python tools/prepare.py --list-versions [FILTER]       # 받을 수 있는 CEF 버전
python tools/prepare.py --cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98"
python tools/prepare.py --cef-root /path/cef           # 직접 빌드한 CEF 사용
python tools/prepare.py --build-cef --dry-run          # 소스 빌드 계획만 보기
```

CEF를 소스에서 빌드(`--build-cef`)하려면 디스크 여유 약 120 GB, RAM 16 GB 이상, 몇 시간이 필요하고 Linux x86_64에서만 됩니다. 일반적으로는 미리 빌드된 CEF로 충분합니다.

## 툴킷 고르기

`cefweaver.ui`의 툴킷 어댑터는 서로를 불러오지 않습니다. 쓰는 툴킷만 설치하면 됩니다.

| 설치 | 툴킷 | 참고 |
| --- | --- | --- |
| `cefweaver[qt]` | Qt (PyQt6) | PySide6도 됩니다. 직접 설치하고 환경 변수 `CEFQT_BINDING=pyside6`을 줍니다 |
| `cefweaver[gtk3]` | GTK 3 (PyGObject, pycairo) | PyGObject는 소스에서 빌드되므로 시스템 패키지가 필요합니다(Debian과 Ubuntu 계열: `libgirepository-2.0-dev`, `libcairo2-dev`, `gir1.2-gtk-3.0`, `pkg-config`) |
| `cefweaver[tk]` | Tk | Pillow를 씁니다 |
| `cefweaver[sdl2]` | SDL2 | `pysdl2`와 `pysdl2-dll`을 씁니다 |
| `cefweaver[kivy]` | Kivy | |
| `cefweaver[pygame]` | (소리 출력용) | 툴킷이 페이지의 소리를 재생하지 못할 때 쓰는 대안입니다. [소리, 마이크, 카메라](media.md) 참고 |
| (extras 없음) | wxPython | PyPI에는 소스만 있어 빌드가 매우 깁니다. [wxPython 빌드 모음](https://extras.wxpython.org/wxPython4/extras/)에서 시스템에 맞는 wheel을 받으세요. `examples/wx/pyproject.toml`에 예가 있습니다 |

## 예제 실행

각 예제는 자기 폴더에서 `uv`로 실행합니다. 먼저 위에서 wheel을 만들어 두어야 합니다(예제가 `dist/`의 wheel을 가리킵니다).

```sh
cd examples/tk
uv sync
uv run python quickstart.py            # 주소를 인자로 줄 수 있음
```

예제는 `examples/gtk3`, `examples/qt`, `examples/tk`, `examples/sdl2`, `examples/wx`, `examples/kivy`에 있고, 각 폴더의 `README.md`에 그 툴킷에 필요한 준비가 있습니다. 인쇄(Linux, CUPS)는 `examples/print`에 앱이 직접 그리는 대화상자와 함께 있습니다(`libcups2-dev`가 필요).

## 알아 둘 것

- **캐시 폴더**: 캐시 경로를 주지 않으면 CEF가 현재 작업 폴더에 `cache/`를 만듭니다. 프로그램에서는 임시 폴더를 가리키세요(`ui.Session(adapter, cache_path=...)`, 창 모드는 `app.set_cache_path()`).
- **프로세스당 한 번**: CEF는 프로세스에서 한 번만 초기화할 수 있습니다. `shutdown()` 뒤에도 다시 초기화할 수 없습니다.
- **배치**: Linux는 `libcef.so`, `icudtl.dat`, `.pak` 파일, `locales/`, `cefsubprocess` 실행 파일이, macOS는 `cefsubprocess.app`이 확장 모듈 옆에 있어야 합니다. `prepare.py`와 wheel 빌드가 이 배치를 맡습니다.
