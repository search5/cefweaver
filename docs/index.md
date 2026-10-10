---
title: CEFWeaver
---

# CEFWeaver

CEFWeaver는 [Chromium Embedded Framework](https://bitbucket.org/chromiumembedded/cef)(CEF)의 Python 바인딩입니다. Chromium 기반 브라우저를 Python 프로그램에 넣어 웹 페이지를 보여 주고, 페이지와 Python이 서로를 호출하게 합니다.

> 개발 중인 프로젝트입니다. 실서비스에 쓰기에는 아직 이릅니다.

## 무엇을 할 수 있나요

- **창이 있는 브라우저**: `cefweaver.CefApp`으로 CEF의 창을 띄우고 핸들러로 이벤트를 받습니다.
- **GUI 툴킷 안의 브라우저**: `cefweaver.ui`가 오프스크린 브라우저를 GTK 3, Qt(PyQt6, PySide6), Tk, SDL2, wxPython, Kivy의 위젯 안에 보여 줍니다. 마우스, 키, 한글 입력기, 복사와 붙여넣기, 끌어서 놓기를 처리합니다.
- **툴킷 없는 창(Views)**: CEF의 Views 프레임워크로 창, 도구 모음, 단추, 입력칸, 브라우저를 직접 구성합니다(Linux X11에서 확인).
- **소리, 마이크, 카메라**: 페이지의 소리를 툴킷이나 pygame으로 재생하고, 마이크와 카메라 권한을 앱이 정합니다.
- **컨텍스트 메뉴**: 오른쪽 클릭 메뉴를 툴킷의 메뉴로 보여 주고 앱이 항목을 고칠 수 있습니다.
- **생성된 CEF API**: CEF 헤더에서 생성한 PEP 8 스타일 바인딩을 씁니다.

## 문서

| 쪽 | 내용 |
| --- | --- |
| [설치와 빌드](installation.md) | CEF 준비, wheel 빌드, 툴킷 선택 |
| [시작하기](quickstart.md) | 가장 작은 프로그램, 창 모드 |
| [GUI 툴킷에 넣기](ui.md) | `Session`, 뷰와 위젯, 어댑터 |
| [Views (툴킷 없이)](views.md) | CEF만으로 창, 단추, 입력칸, 브라우저 구성 |
| [툴킷별 상태](toolkits.md) | 여섯 툴킷에서 확인한 것과 제한 |
| [소리, 마이크, 카메라](media.md) | 소리 출력, 권한 정책 |
| [컨텍스트 메뉴](context-menu.md) | 메뉴와 훅 |
| [Wayland와 GPU](wayland-gpu.md) | 플랫폼 선택과 문제 해결 |
| [한계와 알려진 제약](limitations.md) | 아직 안 되는 것 |
| [개발하기](development.md) | 시험, 생성기, 위키 |

## 지원 환경

Linux x86_64와 macOS arm64(Apple Silicon)에서 빌드하고 시험합니다. macOS는 Linux와 다른 점이 있습니다([한계와 알려진 제약](limitations.md)). Windows는 검증하지 못했고 macOS x86_64는 빌드해 보지 못했습니다.

프로젝트 저장소: [github.com/search5/cefweaver](https://github.com/search5/cefweaver)
