---
title: 래퍼와 사용자가 핸들러를 나눠 쓰는 방법
type: analysis
sources:
  - native/cefwrapper/cef_wrapper_client_handler.h
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/generated/cefweaver_proxies.h
  - tools/gen/emit_cpp.py
updated: 2026-10-08
---

# 래퍼와 사용자가 핸들러를 나눠 쓰는 방법

컨텍스트 메뉴와 프로세스 메시지 핸들러를 사용자에게 열기 전에 정리한 분석입니다. 결정은 아직 나지 않았습니다.

## 왜 한 객체가 둘을 모두 맡는가

`CefClient`는 `GetLoadHandler()` 같은 getter로 핸들러를 **종류마다 하나씩** 돌려받습니다. 래퍼와 사용자가 각자 핸들러를 가질 수 없고, 한 객체가 CEF의 호출을 받아 둘에게 나눠 줘야 합니다. 핸들러를 분리하는 것은 CEF의 구조상 불가능합니다. 로드, 수명 주기, 표시, 드래그 핸들러는 이미 이 방식으로 풉니다: 래퍼의 `CefWrapperClientHandler`가 받고, 생성된 전달 클래스(`Cw<이름>Forward`)가 사용자의 핸들러로 넘깁니다([핸들러 프록시 구조](../concepts/handler-proxies.md)). 어떤 메서드는 래퍼가 먼저 하고 사용자에게 넘기고, 어떤 메서드는 사용자에게 먼저 묻습니다([C++ 핸들러](../components/native-handlers.md)).

## 컨텍스트 메뉴와 프로세스 메시지가 다른 점

이 둘은 전달만으로 끝나지 않는 이유가 서로 다릅니다.

### 프로세스 메시지(`OnProcessMessageReceived`): 결정이 필요 없습니다

래퍼가 처리하는 메시지는 이름이 `javascript-binding`과 `javascript-python-binding`인 둘뿐이고 처리하면 `true`, 그 밖은 이미 `false`를 돌려줍니다. 이름으로 나누면 충돌이 없습니다: 래퍼의 두 이름은 래퍼가 처리하고, 나머지는 사용자에게 넘기면 됩니다. 사용자의 핸들러가 돌려주는 `bool`이 그대로 CEF에 전달됩니다. 남은 일은 `CefProcessMessage`를 생성 범위에 넣는 것입니다.

### 컨텍스트 메뉴: 선택이 필요한 부분이 있습니다

1. **같은 메뉴 모델을 둘이 고칩니다.** `OnBeforeContextMenu(browser, frame, params, model)`에서 래퍼는 "Show DevTools", "Close DevTools", "Inspect Element" 항목을 더합니다. 사용자가 같은 `model`에서 `clear()`를 부르면 순서에 따라 래퍼의 항목이 사라지거나, 래퍼가 사용자의 비움 뒤에 항목을 더합니다.
2. **명령 ID가 겹칩니다.** 래퍼의 ID는 `MENU_ID_USER_FIRST`(26500)부터 시작하는데, 이 값은 사용자에게 허용된 범위의 맨 앞입니다. 사용자가 첫 ID를 쓰면 래퍼의 "Show DevTools"와 같은 번호입니다.
3. **`OnContextMenuCommand`가 모르는 명령을 모두 처리한 것으로 돌려줍니다.** 코드의 `default` 분기가 `// Allow default handling, if any.`라는 주석과 달리 `return true`입니다(`true`는 처리했다는 뜻이라 CEF가 기본 처리를 건너뜁니다). 복사, 붙여넣기 같은 CEF의 표준 명령이 눌려도 실행되지 않을 가능성이 있습니다. 코드를 읽고 판단한 것이고 **실행으로 확인하지 못했습니다**(Python에서 메뉴를 열고 항목을 고르는 수단이 아직 없습니다). 사용자에게 열기 전에 `false`로 고쳐야 하는 기존 결함일 가능성이 높습니다.

## 선택지

| 쟁점 | 선택지 | 의견 |
| --- | --- | --- |
| 항목을 더하는 순서 | (가) 래퍼가 먼저 더하고 사용자가 고침 (나) 사용자가 먼저 고치고 래퍼가 더함 (다) 래퍼의 DevTools 항목을 선택 사항으로 하고 기본은 끔 | (나)가 사용자의 `clear()`를 존중하면서 래퍼의 항목을 지킵니다. (다)는 래퍼가 메뉴에 손대지 않게 해서 충돌을 없애지만 지금의 동작이 바뀝니다. |
| ID 충돌 | 래퍼의 ID를 사용자 범위의 맨 끝쪽(`MENU_ID_USER_LAST` 근처)으로 옮김 | 사용자는 앞에서부터 쓰므로 거의 겹치지 않습니다. |
| 명령의 처리 | 래퍼의 ID이면 래퍼가 처리하고 그 밖은 사용자에게 넘기며, 사용자도 `false`이면 `false` | 위의 결함도 이때 고쳐집니다. |

## 관련 페이지

- [핸들러 프록시 구조](../concepts/handler-proxies.md)
- [C++ 핸들러](../components/native-handlers.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
