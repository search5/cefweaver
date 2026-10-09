---
title: CefWrapper 클래스
type: component
sources:
  - native/cefwrapper/library.h
  - native/cefwrapper/library.cpp
  - native/cefwrapper/global_vars.h
  - cefweaver/cefwrapper.pxd
updated: 2026-10-08
---

# CefWrapper 클래스

`native/cefwrapper/library.h`와 `library.cpp`의 `CefWrapper`가 손으로 쓴 C++ 진입점입니다. Cython의 `CefApp`이 이것을 `new`로 만들어 감쌉니다(`cefweaver/cefwrapper.pxd`가 선언).

## 공개 메서드

| 메서드 | 설명 |
| --- | --- |
| `bool InitCefSimple(std::string start_url)` | CEF를 초기화하고 시작 URL로 브라우저를 만듭니다. 실패하면 `false`. 순서는 [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md)에 있습니다. |
| `void DoCefMessageLoopWork()` | `CefDoMessageLoopWork()` 한 번 |
| `void ShutdownCefSimple()` | 브라우저를 닫고 `CefShutdown()` |
| `bool LoadUrl(std::string)` | 브라우저가 없으면 `false` |
| `void SetClient(CefRefPtr<CefClient>)` | 표시, 수명 주기, 로드 이벤트를 받을 클라이언트(생성된 `CwClientProxy`). 초기화 전에만 의미가 있고, 초기화 때 브라우저 프로세스 핸들러가 받아 `CefWrapperClientHandler`에 넘깁니다. 종료 때 해제됩니다. |
| `bool ExecuteJavascript(std::string)` | 실행하지 못하면(`CefApp` 없음, 브라우저 없음, 로딩 중) `false` |
| `bool IsRunning()`, `bool IsReadyToExecuteJavascript()` | 상태 |
| `void AddJavascriptPythonBinding(name, handler, owner)` | Python 호출 바인딩. 초기화 전에만 의미가 있습니다(초기화 때 `CefWrapperApp`으로 복사됩니다). |
| `void AddJavascriptBinding(name, fn)` | 인자 없는 C++ 바인딩. Python에는 노출하지 않았습니다. |
| `SetCustomCefSubprocessPath`, `SetCustomCefCachePath`, `SetCustomCefResourcesPath` | 경로 설정. 초기화 전에만 의미가 있습니다. |
| `AddCommandLineSwitch(name, value)` | Chromium 명령줄 스위치. 값이 비어 있으면 값 없는 스위치. 브라우저 프로세스의 `OnBeforeCommandLineProcessing`에서 적용됩니다. 자식 프로세스(렌더러, GPU 등)에는 전달되지 않습니다([실험으로 확인한 사실](../reference/verified-findings-more.md) F36). |

`CefWrapper`의 `CefRefPtr<CefWrapperApp> m_App`이 앱 객체를 쥐고 있고, `CefApp`(Python)이 `shutdown()` 전에 `CefWrapper`를 삭제하지 않는 이유는 [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md)에 있습니다.

## 경로 함수

- `ModuleDir()`(Linux, 익명 네임스페이스): `dladdr()`로 이 코드가 들어 있는 공유 객체(확장 모듈)의 디렉터리를 얻습니다. 정적 라이브러리가 확장 모듈에 링크되므로 그 모듈의 위치입니다.
- `ExePath()`: 서브프로세스 기본 경로. Linux는 `<ModuleDir>/cefsubprocess`, 그 밖은 `현재 작업 디렉터리/cefsubprocess/cefsubprocess.exe`.
- `CachePath()`: `현재 작업 디렉터리/cache`. `set_cache_path`를 쓰지 않으면 Python 프로세스의 현재 디렉터리에 `cache/`가 만들어집니다.

## 전역 상태

`global_vars.h`는 `inline bool g_IsRunning`을 선언합니다(UTF-8 BOM으로 시작하는 파일입니다). 초기화 성공 시 켜지고, 브라우저가 닫힐 때(`OnBeforeClose`)와 `ShutdownCefSimple()`에서 꺼집니다. 프로세스당 CEF가 하나라는 전제의 전역입니다.

## 알려진 약점

- `IsReadyToExecuteJavascript()`는 `CefWrapperClientHandler::GetInstance()`가 널인지 확인하지 않고 바로 역참조합니다(`library.cpp`). Python의 `is_ready_to_execute_javascript`는 `initialize()` 전과 `shutdown()` 뒤를 먼저 걸러서 이 경로를 피하지만, 브라우저 생성 전에 C++에서 직접 부르면 위험합니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).
- 모든 설정 메서드가 "초기화 전에만"이라는 제약을 C++에서는 검사하지 않습니다. 검사는 Python 래퍼(`_require_not_initialized`)가 합니다.

## 관련 페이지

- [C++ 핸들러](native-handlers.md)
- [Cython 확장 모듈](cython-extension.md)
- [Python API 참조](../reference/python-api.md)
