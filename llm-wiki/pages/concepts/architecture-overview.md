---
title: 아키텍처 개요
type: concept
sources:
  - CMakeLists.txt
  - native/cefwrapper/library.h
  - cefweaver/_cefweaver.pyx
  - tools/gen/generate.py
  - pyproject.toml
updated: 2026-10-08
---

# 아키텍처 개요

cefweaver는 Chromium Embedded Framework(CEF)의 Python 바인딩입니다. Linux x86_64와 macOS arm64에서 빌드와 시험을 마쳤고(macOS는 일부 동작이 다름), Windows는 코드 경로만 있고 검증하지 못했습니다([플랫폼 지원 현황](platform-support.md)).

## 계층

```
Python 응용
  cefweaver.CefApp                      손으로 쓴 진입점(수명 주기, JS 바인딩, add_resource)
  cefweaver.Request, ResourceHandler    CEF 헤더에서 생성한 래퍼(PEP 8 이름)
        |
Cython 확장 cefweaver._cefweaver
  _cefweaver.pyx (손으로 씀) + cef_api.pxi + api/*.pxi, cef_api.pxd (생성) + cefwrapper.pxd (손으로 씀)
        |                                   |
        |                       생성된 C++ 프록시 cefweaver_proxies.h
        |                       (CEF가 호출하는 핸들러를 Python 객체로 위임)
        v
libcefwrapper.a  (native/cefwrapper: CefWrapper 클래스와 앱, 클라이언트, 브라우저 프로세스, 렌더러 핸들러)
        |
libcef_dll_wrapper.a  (CEF 배포본의 libcef_dll 소스를 컴파일한 것)
        |
libcef.so  (CEF 배포본에 이미 만들어져 있는 파일. 소스 빌드를 쓰면 직접 컴파일한 파일)
```

별도 실행 파일 `cefsubprocess`(`native/cefsubprocess`)가 렌더러, GPU, 유틸리티 프로세스를 맡습니다([프로세스 모델과 스레드](process-model-and-threads.md)).

## 두 갈래의 Python 인터페이스

1. **손으로 쓴 경로**: `CefApp`이 `CefWrapper`(C++)를 감쌉니다. 초기화, 메시지 루프, 종료, URL 로드, JavaScript 실행, JS에서 Python으로의 호출이 여기에 있습니다. 규모가 작고 결정이 고정되어 있습니다([Cython 확장 모듈](../components/cython-extension.md), [JavaScript 바인딩](javascript-bindings.md)).
2. **생성된 경로**: CEF의 클래스를 거의 그대로 중계하는 래퍼입니다. CEF 헤더를 읽는 생성기가 C++ 프록시, Cython 래퍼, 타입 스텁을 만듭니다. 지금은 29개 클래스와 전역 함수 3개이고 확장할 수 있게 설계되었습니다([바인딩 생성기의 설계](binding-generator.md)).

`CefApp.add_resource()`는 두 경로를 잇는 예입니다. 손으로 쓴 클래스가 생성된 `ResourceHandler`와 `SchemeHandlerFactory`만 사용해서 구현되어 있습니다([리소스 제공](resource-serving.md)).

## 빌드 흐름

| 단계 | 도구 | 산출물 |
| --- | --- | --- |
| 1. CEF 확보 | `tools/prepare.py`(`--cef-root`, `--build-cef`, 또는 prebuilt 자동 다운로드) | `build/native/cef` 링크 |
| 2. 네이티브 빌드 | CMake(`CMakeLists.txt`, `native/*/CMakeLists.txt`) | `libcef_dll_wrapper.a`, `libcefwrapper.a`, `cefsubprocess` |
| 3. 런타임 스테이징 | `tools/prepare.py` | `cefweaver/` 아래에 복사된 `libcef.so`와 리소스 |
| 4. 바인딩 생성(개발 시) | `tools/gen/generate.py` | 커밋되는 생성 파일 |
| 5. 확장 빌드와 패키징 | `uv build --wheel`(setuptools, Cython) | `.so`가 들어간 wheel |

1단계부터 3단계는 사전 준비이고 `uv build --wheel`은 그 결과를 읽기만 합니다. 이 분리의 이유는 [설계 결정 기록](../reference/design-decisions.md)에 있습니다. 생성 파일은 저장소에 커밋되므로 패키지를 만드는 사람은 생성기를 실행하지 않아도 됩니다.

## 관련 페이지

- [프로세스 모델과 스레드](process-model-and-threads.md)
- [수명 주기와 메시지 루프](lifecycle-and-message-loop.md)
- [CEF 확보 방식](cef-acquisition.md)
- [런타임 파일 배치](runtime-layout.md)
- [소스 트리 지도](../reference/source-tree-map.md)
- [용어집](../reference/glossary.md)
