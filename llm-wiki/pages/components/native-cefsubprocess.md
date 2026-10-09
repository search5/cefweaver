---
title: cefsubprocess 실행 파일
type: component
sources:
  - native/cefsubprocess/cefsubprocess.cc
  - native/cefsubprocess/CMakeLists.txt
updated: 2026-10-08
---

# cefsubprocess 실행 파일

CEF가 렌더러, GPU, 유틸리티 프로세스를 띄울 때 실행하는 별도 실행 파일입니다(`native/cefsubprocess/cefsubprocess.cc`). 역할은 java-cef의 `jcef_helper`, cefpython의 `subprocess`와 같습니다.

## main

`CefWrapperApp`을 바인딩 없이 만들어 `CefExecuteProcess()`에 넘기고, 그 반환값(자식 프로세스의 종료 코드)을 반환합니다. 렌더러 프로세스에서 JS 함수를 정의하는 `SimpleRenderProcessHandler`가 `CefWrapperApp`을 통해 연결되므로, 이 실행 파일이 `native/cefwrapper`의 헤더를 포함하고 `libcefwrapper.a`를 링크합니다.

| | Linux | Windows |
| --- | --- | --- |
| 진입점 | `int main(argc, argv)`, `CefMainArgs(argc, argv)` | `wWinMain`, `CefMainArgs(hInstance)` |
| 반환 | `CefExecuteProcess` 반환값 | 항상 0 (반환값을 쓰지 않는 원래 코드) |
| 고유 처리 | `__attribute__((no_stack_protector))` | `CefEnableHighDPISupport()`, 샌드박스 라이브러리 pragma |

Linux의 `main`에 붙은 `no_stack_protector`는 서브프로세스가 종료할 때 `*** stack smashing detected ***`로 비정상 종료하던 문제를 없앱니다. 근거는 [실험으로 확인한 사실](../reference/verified-findings.md)에 있습니다. 순정 `cefsimple`의 `main`에는 스택 보호 검사가 없고(0개), 우리 `main`에는 있었으며(`std::string` 임시 객체의 내부 `char` 버퍼 때문으로 해석합니다), 속성을 붙인 뒤 같은 시험 3회에서 오류가 0건이 되었습니다. 코드 주석이 설명하는 메커니즘(Chromium zygote가 자식 프로세스를 포크하고 자식이 이 프레임을 거쳐 종료하며 스택 보호값이 달라진다는 것)은 이 결과에서 추정한 것이고 직접 확인한 것은 아닙니다.

## CMake 타깃

- Linux: `add_executable(cefsubprocess ...)`, `INSTALL_RPATH $ORIGIN`(`BUILD_WITH_INSTALL_RPATH TRUE`), 출력 디렉터리에 CEF 바이너리와 리소스 복사(`COPY_FILES`), `libminigbm.so`가 있으면 함께 복사. 출력은 `build/native/native/cefsubprocess/Release/cefsubprocess`입니다.
- `libcefwrapper.a`, `libcef_lib`, `libcef_dll_wrapper`를 링크합니다.
- 이 빌드 디렉터리의 `cefsubprocess`가 `tools/prepare.py`의 스테이징 원본입니다([런타임 파일 배치](../concepts/runtime-layout.md)).

## 관련 페이지

- [프로세스 모델과 스레드](../concepts/process-model-and-threads.md)
- [루트 CMake와 CEF 다운로드](root-cmake.md)
- [C++ 핸들러](native-handlers.md)
