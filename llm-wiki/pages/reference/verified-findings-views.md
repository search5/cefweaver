---
title: 실행해서 확인한 Views (F96~F98)
type: reference
sources:
  - tools/gen/scope.py
  - tools/gen/emit_cython.py
  - tools/gen/model.py
  - tools/gen/typesys.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - examples/views/browser.py
  - examples/views/smoke.py
  - tests/test_smoke.py
updated: 2026-10-10
---

# 실행해서 확인한 Views (F96~F98)

CEF의 Views 프레임워크(창, 패널, 단추, 텍스트 필드, 레이아웃, 델리게이트 22개 클래스)를 열고 확인한 기록입니다. 결정과 이유는 [열지 않은 CEF 메서드와 cefpython의 비교](../analyses/unopened-cef-api.md)에 있고, 사용법은 `examples/views/`와 사이트의 "Views (툴킷 없이)"에 있습니다. 환경은 Linux x86_64, CEF 154, X11(Xvfb)이며 **Windows, macOS, Wayland는 확인하지 못했습니다.**

## F96. 상속을 Python 상속으로 열었다 (2026-10-10)

- **문제**: 생성기는 라이브러리 클래스의 부모 메서드를 **펼쳐서** 하나의 클래스로 만들었습니다(`CefRequestContext`와 `PreferenceManager`). 생성된 클래스는 각자 독립된 `cdef class`이고 인자를 정확한 타입으로 검사하므로, `window.add_child_view(browser_view)`처럼 파생 뷰를 `View` 자리에 넘길 수 없고, `get_child_view_at()`처럼 `View`를 돌려주는 메서드는 실제 종류(`Window`, `LabelButton`)를 알려 줄 수 없습니다.
- **구현**(`tools/gen`): 범위 안의 라이브러리 클래스 가운데 **부모도 범위 안에 있으면 Python 하위 클래스**로 만듭니다(`Scope.python_parent`: 부모가 범위 밖이면 이전처럼 펼침, 그래서 기존 클래스는 바뀌지 않음). 하위 클래스는 **자기 메서드만** 갖고(`Window` 107개가 아니라 자기 것만, `typesys.plan_class`), 루트(`View`)의 `CefRefPtr[CefView] _ref`를 공유하며, 메서드는 타입이 맞는 접근자(`_ptr_CefWindow`, `<CefWindow*>self._ref.get()`)로 CEF를 부릅니다. 하위 타입을 받는 인자는 `CefRefPtr[CefX](<CefX*>obj._ref.get())`로 내려 캐스트하고, 루트 타입 인자는 그대로 받습니다. **반환값은 `_wrap_<클래스>`가 CEF의 `AsBrowserView()`, `AsButton()`, `AsPanel()`, `AsWindow()` 같은 메서드로 실제 종류를 찾아** 가장 구체적인 Python 클래스로 감쌉니다. `.pxd`의 `cppclass`는 부모를 적고, 정의는 부모가 먼저 오도록 정렬합니다(`Scope.library_classes`). 클라이언트 쪽 델리게이트는 프록시가 모든 가상 메서드를 구현해야 하므로 **펼친 채** 둡니다.
- **측정**: 22개 클래스 789개 메서드가 오류 없이 생성됩니다. 상속한 클래스는 자기 메서드만 가져 생성량이 줄어, Views의 메서드는 펼친 789개가 **309개**(라이브러리 192개는 자기 것만 + 델리게이트 117개는 펼친 채)가 되고 그 가운데 306개가 생성됩니다. 합계는 **1,031개 메서드, 100개 클래스**(`Image` 포함, 이전 725개에서 +306, 당시 값이고 지금은 1,182개와 129개)입니다. wheel 빌드는 70초에서 **91초**, wheel 크기는 160.9MB에서 162.7MB입니다.
- **확인(실제 CEF, 시험 `test_a_views_window_holds_a_toolbar_and_a_browser_view`)**: `Window → Panel → View`, `BrowserView`, `MenuButton → LabelButton → Button`이 Python 하위 클래스이고, 델리게이트의 `on_window_created`가 `Window` 객체를 받고, `get_child_view_at()`이 `["Panel", "BrowserView"]`, 도구 모음의 자식이 `["LabelButton", "Textfield"]`, `get_view_for_id()`가 `Textfield`, `toolbar.get_parent_view()`가 `Window`, `browser_view.get_window()`가 `Window`로 옵니다. 상자 배치에서 도구 모음과 브라우저가 창 너비를 채우고 높이의 합이 창 높이와 같습니다.
- **막힌 것 (해결함)**: 309개 중 3개(`View.GetDelegate`, `BrowserViewDelegate.GetDelegateForPopupBrowserView`, `WindowDelegate.GetParentWindow`)는 라이브러리 메서드가 클라이언트 객체를 돌려주거나 핸들러 메서드가 클라이언트 또는 라이브러리 객체를 주고받는 경우라서 처음에는 열지 못했습니다. 같은 날 생성기를 고쳐 열었습니다([F100, F101](verified-findings-views.md)).

## F97. 외부 메시지 펌프에서는 CEF 자신의 창에 X11 입력이 오지 않는다 (2026-10-10)

- **증상**: `MessagePump`(`external_message_pump`)로 돌리면 Views 창이 그려지고 레이아웃과 페이지 이동도 되지만, **마우스 클릭과 키 입력이 `on_button_pressed`와 페이지의 `mousedown`/`keydown`에 오지 않습니다**(`xdotool`로 클릭해도 `pressed: []`).
- **가름(실험)**: (1) 같은 가상 화면에서 **설치된 Chrome 155는 같은 클릭과 키를 받습니다**(제목이 `key1a`로 바뀜). 환경이나 창 관리자 문제가 아닙니다. (2) 같은 앱을 `do_message_loop_work()`를 자주 부르는 **폴링**으로 바꾸면 단추가 눌립니다(`pressed: [3, 3]`). (3) 페이지 영역의 입력도 같은 결과입니다.
- **해석(추정)**: 외부 펌프 모드에서 CEF는 알린 작업만 돌리고, CEF가 소유한 창의 X11 이벤트를 처리하는 일은 이벤트 루프가 해야 하는데 Views에는 그 루프(예: GTK)가 없습니다. 툴킷 어댑터가 `MessagePump`를 쓰는 것은 입력을 툴킷의 창이 받기 때문입니다. CEF 소스에서 원인을 확인하지는 않았습니다.
- **적용**: `examples/views`는 폴링 루프(`do_message_loop_work()`와 5ms 대기)를 씁니다. 그러면 `smoke.py`의 13개(주소칸 클릭, 입력, Return, Back, Forward, Reload, 창 닫기)가 **연속 3회** 통과합니다. 창 관리자가 없는 가상 화면이어도 `windowfocus`가 필요 없었습니다.

## F98. 생성기 수정 두 건과 첫 브라우저 없는 시작 (2026-10-10)

- **API 버전(`removed`, `added`)**: `CefTextfield`의 `SetTextColor` 등은 헤더에서 `#if CEF_API_REMOVED(15000)` 안에 있어 우리의 API 버전(`CEF_API_VERSION_EXPERIMENTAL` 999999)에서는 **컴파일러가 보지 못하는 메서드**인데 파서는 목록에 넣어서 `has no member named` 오류가 났습니다. `model.API_VERSION`과 `Model.virtual_funcs/static_funcs`가 그 버전에 없는 메서드를 거릅니다(파서는 가상 함수에만 `exists_at_version`을 주어서 정적 함수에는 같은 규칙을 직접 적용). 이전에는 이런 메서드가 든 클래스를 열지 않아서 드러나지 않았습니다.
- **상속한 순수 가상 메서드**: 델리게이트 프록시가 순수 가상(`= 0`) 메서드의 기반 구현을 불러 `undefined symbol: CefButtonDelegate::OnButtonPressed`로 import가 실패했습니다. `is_pure_virtual`이 클래스 자신의 헤더만 보아서 부모에서 물려받은 메서드(`MenuButtonDelegate`의 `OnButtonPressed`는 `ButtonDelegate`가 선언)를 놓쳤습니다. 선언한 부모까지 올라가도록 고쳤습니다.
- **`initialize(None)`**: 첫 브라우저를 만들지 않고 CEF만 초기화합니다(`CefWrapper::SetFirstBrowser`, 전역 `g_NoFirstBrowser`). `is_running`은 `shutdown()`까지 `True`이므로 창이 닫힌 것은 `WindowDelegate.on_window_destroyed`로 압니다.
- **`shutdown()`과 열린 창 (F99)**: 창이 열린 채 `app.shutdown()`을 부르면 세그멘테이션 오류(종료 코드 139)가 났습니다. 원인은 `CefShutdown()`이 불릴 때 살아 있는 브라우저가 있는 것이었고, `ShutdownCefSimple()`이 `CloseOtherBrowsers()`로 남은 브라우저를 닫고(최대 500회 펌프) 종료하도록 고쳐 해결했습니다(`native/cefwrapper/library.cpp`). 열린 창으로 부르는 시험이 통과합니다.
- **CEF가 간직한 Python 객체 되찾기 (F100)**: `View.get_delegate()`, `BrowserHost.get_client()`, `RequestContext.get_handler()`는 CEF에 준 Python 객체 자체를 돌려줍니다(`is`로 같음, 시험으로 확인). 래퍼가 RTTI 없이 빌드되어 `dynamic_cast`가 안 되므로, 프록시를 만들 때 포인터와 Python 객체를 등록부(`CwProxyRegistry`)에 넣고 찾습니다. 프록시가 아닌 것(CEF가 만든 객체, 델리게이트를 주지 않은 뷰)은 `None`입니다. 핸들러가 라이브러리 객체를 돌려주는 메서드(`WindowDelegate.get_parent_window`)와 라이브러리 객체를 받는 핸들러 메서드도 같은 방식으로 열렸습니다.
- **팝업 델리게이트 (F101)**: `BrowserViewDelegate.get_delegate_for_popup_browser_view(browser_view, settings, client, is_devtools)`는 실제 클릭으로 `target=_blank` 링크를 열었을 때 불렸고, `client`는 열어 준 쪽의 클라이언트였으며 `on_popup_browser_view_created`도 뒤따랐습니다. 클라이언트에 `LifeSpanHandler`가 없으면 두 메서드가 불리지 않았습니다(팝업 자체는 열림). `execute_java_script`의 `window.open`은 사용자 동작이 없어 열리지 않았습니다. 이유를 소스로 확인하지는 않았습니다. `get_parent_window`는 창마다 불렸고 `(부모, False, False)`를 돌려주는 시험이 통과합니다.
- **기존의 간헐적 실패(이번 변경과 무관)**: `test_a_second_offscreen_browser_paints_on_its_own_and_the_first_is_unaffected`가 **변경 전 wheel에서도 20회 중 2회 실패**합니다(첫 `on_paint`의 첫 픽셀이 투명). 새 wheel에서는 20회 중 0회, 다른 실행에서 1회였습니다. 원인은 조사하지 않았습니다.
- **시험**: 생성기 시험 1개(`test_a_class_below_another_generated_class_is_a_python_subclass`), 스모크 2개(Views 클래스의 상속, 창과 도구 모음과 브라우저 뷰), `examples/views/smoke.py` 13개, `QuickstartDocs`와 `Quickstarts`에 `views`를 더했습니다.

## 관련 페이지

- [열지 않은 CEF 메서드와 cefpython의 비교](../analyses/unopened-cef-api.md)
- [새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)
- [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
