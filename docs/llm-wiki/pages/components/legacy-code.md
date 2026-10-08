---
title: 사용하지 않는 코드와 유산
type: component
sources:
  - native/cefwrapper/custom_protocol_scheme_handler.cc
  - native/cefwrapper/custom_protocol_scheme_handler.h
  - native/cefwrapper/file_util.h
  - native/cefwrapper/cef_wrapper_app.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - native/cefwrapper/javascript_bindings_handler.h
  - native/cefwrapper/CMakeLists.txt
  - native/cefsubprocess/CMakeLists.txt
  - CMakeLists.txt
updated: 2026-10-08
---

# 사용하지 않는 코드와 유산

`native/`의 코드는 다른 프로젝트에서 가져온 것이 많습니다. 커밋 `8471fdb`의 메시지가 "cef-wrapper를 가져다가 샘플 테스트 작업중입니다"이고, `custom_protocol_scheme_handler.cc`에는 "Created by maxim on 19.10.2022" 주석과 `C:\ZenDraft` 경로가 있어서 ZenDraft라는 다른 프로젝트용 코드로 보입니다(추정). 그래서 현재 Python 경로에서 쓰이지 않거나 원래 환경에 고정된 부분이 남아 있습니다. 아래는 코드 검색으로 확인한 목록입니다. 제거하거나 고치기 전에는 이 페이지의 서술이 사실입니다.

## 호출되지 않는 코드

| 위치 | 상태 |
| --- | --- |
| `custom_protocol_scheme_handler.cc/.h` | `zen://` 스킴 핸들러와 `RegisterSchemeHandlerFactory()`. 호출이 `cef_wrapper_browser_process_handler.cc`에 `//RegisterSchemeHandlerFactory();`로 주석 처리되어 있고 `OnRegisterCustomSchemes()`의 등록도 주석입니다. 파일 읽는 루트 경로가 `C:\ZenDraft\ZenDraft\build\`로 박혀 있습니다. CMake 소스 목록에는 있어서 컴파일은 됩니다. |
| `file_util.h` | 위 핸들러만 포함합니다. |
| `CefWrapperApp::LoadUrl()`, `CefWrapperBrowserProcessHandler::LoadUrl()` | 정의와 선언만 있고 호출하는 곳이 없습니다. 현재의 `CefWrapper::LoadUrl()`은 브라우저를 직접 씁니다. 후자는 `Browser`가 널인지 확인하지 않습니다. |
| `CefWrapper::AddJavascriptBinding()`과 `javascript-binding` 메시지 경로(`javascript_bindings_handler.h`) | 인자 없는 C++ 바인딩. Python 쪽 선언(`cefwrapper.pxd`)에 없어서 쓰이지 않습니다. |
| `cef_wrapper_client_handler.cc`의 메뉴 상수 `CLIENT_ID_SHOW_SSL_INFO`, `CLIENT_ID_CURSOR_CHANGE_DISABLED`, `CLIENT_ID_MEDIA_HANDLING_DISABLED`, `CLIENT_ID_OFFLINE`, `CLIENT_ID_TESTMENU_*`, 그리고 `IsClosing()` | 정의만 있고 사용하는 곳이 없습니다(상수는 파일 안에서 한 번씩만 나옵니다). 메뉴에서 실제로 쓰는 것은 DevTools 관련 세 개입니다. |

생성된 `ResourceHandler`/`SchemeHandlerFactory` 경로가 `custom_protocol_scheme_handler.cc`의 역할을 대체할 수 있습니다([리소스 제공](../concepts/resource-serving.md)). 이 파일을 지울지는 정해지지 않았습니다.

## 원래 환경에 고정된 것

- `library.cpp`의 `ExePath()`와 `CachePath()`에 남은 주석에 개발자 PC의 경로(`C:\Dev\cef-binaries\cef_binary_106.0.27+g20ed841+chromium-106.0.5249.103_windows64\...`)가 있습니다. 실행에는 영향이 없습니다.
- `native/cefsubprocess/CMakeLists.txt`의 Windows 분기가 `../cefwrappertest/...`, `../../../src/PyCef_Dev/PyCef/...`로 복사합니다. 이 저장소에 해당 디렉터리가 없습니다.
- `native/cefwrapper/CMakeLists.txt`의 `COPY_SINGLE_FILE` 줄(주석)도 `src/PyCef_Dev`를 가리킵니다.
- 루트 `CMakeLists.txt`의 `#add_subdirectory(native)`와 `src/cefwrappertest` 블록은 주석입니다.
- 소스 목록 변수 이름 `CEFSIMPLE_SRCS`, 창 제목 `"cefsimple"`(Windows `SetAsPopup`), `SimpleRenderProcessHandler` 같은 이름은 CEF의 `cefsimple` 예제에서 왔습니다.

## 관련 페이지

- [C++ 핸들러](native-handlers.md)
- [루트 CMake와 CEF 다운로드](root-cmake.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
