---
title: 실험으로 확인한 사실 2 (핸들러, 호스트, 스타일, 생성기)
type: reference
sources:
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - tools/gen/model.py
  - tests/test_smoke.py
  - tests/test_generator.py
updated: 2026-10-08
---

# 실험으로 확인한 사실 2 (핸들러, 호스트, 스타일, 생성기)

[실험으로 확인한 사실](verified-findings.md)의 이어지는 번호입니다. 실행해서 확인한 것만 적고, 추측은 [알려진 제약과 미검증 항목](known-constraints.md)에 둡니다.

## F15. 클라이언트 핸들러의 이벤트와 래퍼의 동작

- **방법**: `Client`, `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`를 상속한 객체를 `set_client()`로 넘기고 `data:` 페이지와 닫힌 로컬 포트의 URL을 로드했습니다(`tests/test_smoke.py`의 시험 4개).
- **결과**: 한 번의 로드에서 `on_after_created`, `on_load_start`(주 프레임), `on_loading_state_change`(`True`와 `False`), `on_title_change`, `on_load_end` 순으로 이벤트가 왔고 생성이 시작보다 앞, 시작이 종료보다 앞이었습니다. 모든 콜백은 `initialize()`를 부른 스레드(`MainThread`)에서 실행되었습니다. 닫힌 포트의 오류는 `error_code == -102`(`ERR_CONNECTION_REFUSED`)와 요청한 URL로 왔고, 래퍼는 이어서 `data:` 오류 페이지를 로드했습니다. 사용자의 `on_load_end`와 클라이언트의 getter가 예외를 일으켜도 `sys.excepthook`으로 보고될 뿐 래퍼의 준비 플래그와 JS 바인딩은 정상이었고, 종료할 때 `on_before_close`가 전달되었습니다.
- **변이 시험**: 전달 호출 두 곳(`OnLoadEnd`, `OnBeforeClose`)을 일부러 지우자 새 시험 3개가 실패했고 실패 메시지가 기다린 사건을 가리켰습니다. 복구하자 모두 통과했습니다.
- **영향**: 위임 구조가 의도대로 동작합니다. 확인하지 못한 것은 [알려진 제약과 미검증 항목](known-constraints.md)에 적었습니다.

## F16. 값 타입 구조체

- **방법**: 헤더에서 읽은 구조체로 생성한 `cefweaver_proxies.h`를 `c++`로 컴파일해 프록시를 직접 호출하는 프로그램을 만들고 실행했습니다(`tests/test_generator.py`). `libcef.so`를 링크했습니다(`CefString`이 필요).
- **결과**: 입력 구조체는 표에 `const CefRect*`로 전달되었고(`5,6,7,8`), 표가 채운 출력 구조체는 CEF 메서드의 참조 인자에 복사되었습니다(`10,20,30,40`). wheel은 C 컴파일러 경고 없이 빌드되었습니다(내보내기와 변환 함수를 `inline`으로 선언해 미사용 함수 경고를 없앴습니다). 전체 시험 48개가 통과했습니다.
- **영향**: 구조체 입력과 출력의 C++ 쪽은 확인했습니다. Python 핸들러까지의 경로는 [알려진 제약과 미검증 항목](known-constraints.md)에 적었습니다.

## F17. 브라우저 호스트

- **방법**: `browser.get_host()`로 얻은 `BrowserHost`로 줌, 마우스, 자동 크기 조정, 닫기를 실행했습니다(`tests/test_smoke.py`, 가상 X 서버).
- **결과**:
  - 줌: `set_zoom_level(1.0)` 뒤 `get_zoom_level()`이 `1.0`을 돌려줍니다(초기값 `0.0`).
  - 마우스: `send_mouse_click_event`로 보낸 클릭이 페이지의 `mousedown`으로 도착하고 좌표와 버튼이 그대로입니다(Alloy 스타일, F18). `MouseEvent`와 일반 튜플 모두 받고, 길이가 다르거나 튜플이 아니면 `TypeError`입니다.
  - 자동 크기 조정: `set_auto_resize_enabled(True, Size(100, 100), (900, 700))` 뒤 `on_auto_resize`가 `Size`(예: 360 x 240)와 함께 호출됩니다. 핸들러의 구조체 입력이 Python까지 오는 것을 이것으로 확인했습니다.
  - 닫기: `close_browser(False)`가 `on_before_close`를 부르고 `is_running`을 거짓으로 만듭니다.

## F18. Chrome 스타일과 Alloy 스타일

- **방법**: 같은 시험을 Chrome 스타일(기본값)과 `window_info.runtime_style = CEF_RUNTIME_STYLE_ALLOY`로 만든 브라우저에서 실행하고, 차이를 스파이크로 따로 조사했습니다.
- **Chrome 스타일**: `get_runtime_style()`이 `1`. `do_close`가 **호출되지 않았습니다**(헤더가 `DoClose`를 Alloy 스타일에만 부른다고 밝힘). 마우스 좌표에 창 장식의 오프셋이 있었습니다((50, 60)이 (41, 50)). 창 제목은 CEF가 `<title> - Chromium`으로 자동 설정했습니다.
- **Alloy 스타일**: `get_runtime_style()`이 `2`.
  - `do_close`가 호출되고 `True`를 돌려주면 닫기가 취소됩니다(`running`이 계속 참). 이후 `False`를 돌려주면 `on_before_close`로 이어지고 종료됩니다.
  - 마우스 좌표는 정확합니다((50, 60)이 (50, 60)).
  - **준비되기 전에 보낸 입력은 버려집니다.** 로드 직후의 클릭은 도착하지 않았고, 페이지의 `requestAnimationFrame` 콜백이 불린(첫 프레임) 뒤의 클릭은 대부분 도착했습니다. 그러나 첫 프레임 뒤에도 10번 중 1번은 첫 클릭이 버려져서 두 번째에 도착했고(첫 프레임 뒤 10~35ms에 도착), 이 때문에 시험이 불안정했습니다(50번 중 1번 실패). 준비를 알리는 신호는 찾지 못해서 시험은 도착할 때까지 다시 보냅니다. 처음에는 포커스 문제로 짐작했으나 `document.hasFocus()`가 처음부터 참이었고 `set_focus`는 영향이 없어서 아니었습니다.
  - CEF가 만든 800x600 최상위 창이 **제목 없이** 뜹니다. 래퍼가 X11로 설정하게 했고, 루트의 자식 창에 `_NET_WM_NAME`이 있는 것을 `xwininfo`로 확인했습니다.
- **영향**: 래퍼는 Alloy 스타일만 만듭니다([설계 결정 기록](design-decisions.md)). 시험이 스타일(`== 2`), `do_close`의 거부, 창 제목, 마우스를 지킵니다. Alloy 스타일에서의 네이티브 Wayland는 확인하지 못했습니다([알려진 제약과 미검증 항목](known-constraints.md)).

## F19. 리소스 핸들러 콜백의 스레드

- **방법**: `create`, `open`, `get_response_headers`, `read` 안에서 `threading.get_ident()`를 기록했습니다.
- **결과**: 네 곳 모두 메인 스레드와 다른 스레드에서 실행되었습니다. 스레드 이름은 `Dummy-1`~`5`로(Python이 만든 스레드가 아님) 호출마다 다를 수 있었습니다. 헤더가 말하는 IO 스레드인지는 이름으로 구별하지 못했습니다.

## F20. shutdown() 뒤 initialize()

- **방법**: 같은 프로세스에서 `shutdown()` 뒤 새 `CefApp().initialize()`를 호출했습니다.
- **결과**: 세그멘테이션 오류(종료 코드 139)였습니다. 지금은 `RuntimeError`로 막습니다(`test_initialize_after_shutdown_raises_instead_of_crashing`).

## F21. shutdown() 없이 프로세스가 끝나는 경우

- **방법**: 핸들러(클라이언트, 스킴 팩토리)가 살아 있고 요청이 진행 중인 채로 `shutdown()` 없이 스크립트를 끝냈습니다(5번 반복, 그리고 시험).
- **결과**: 모두 종료 코드 0으로 정상 종료했습니다.

## F22. 팩토리가 거절한 경로

- **방법**: 등록한 호스트에서 한 경로는 핸들러를, 다른 경로는 `None`을 돌려주었습니다.
- **결과**: 핸들러를 준 경로는 200으로 로드되었습니다. `None`을 준 경로는 CEF 기본 처리(네트워크)로 넘어가 `ERR_NAME_NOT_RESOLVED`(-105)로 실패했고 `on_load_error`가 불렸습니다. 시험은 오류 코드는 확인하지 않고 팩토리가 물었는지와 오류의 URL만 확인합니다(네트워크 환경에 따라 코드가 다를 수 있기 때문).

## F23. 다른 CEF 버전의 헤더로 생성

- **방법**: 147.0.14와 152.0.12의 `minimal` 배포본에서 `include/`만 받아 현재 범위로 생성기를 실행하고, 생성한 프록시 헤더, Cython 확장(`cython` 후 `c++ -fsyntax-only`), 래퍼의 손으로 쓴 소스 5개를 해당 버전의 헤더로 컴파일했습니다.
- **결과**: 154, 152, 147 모두 생성되고 전부 컴파일되었습니다. 생성 결과는 첫 줄의 버전 표기만 달랐습니다(현재 범위의 API는 147에서 154까지 같음). 해당 버전의 `libcef`로 실제 실행하지는 않았습니다.

## F24. manylinux

- **방법**: `auditwheel show dist/cefweaver-*.whl`.
- **결과**: 허용되는 태그가 `linux_x86_64`뿐입니다. wheel이 빌드 호스트(Ubuntu, glibc 2.43)의 `GLIBC_2.43` 등을 참조하고, `libcef`가 manylinux 허용 목록 밖의 `libnss3`, `libdbus-1`, `libasound`, `libudev`, `libsystemd`, `libgnutls` 등을 요구합니다.

## F25. GIL을 놓지 않으면 교착한다

- **방법**: `shutdown()`의 `with nogil`을 지운 변형 빌드와 정상 빌드에서 같은 시나리오를 실행했습니다. 끝나지 않는 응답(`read`가 계속 데이터를 돌려줌)을 IO 쪽 스레드가 읽는 중에 `shutdown()`을 호출하고, `faulthandler.dump_traceback_later(25)`로 감시했습니다.
- **결과**: 정상 빌드는 0.03초에 끝났고 그 사이에도 Python 콜백이 계속 불렸습니다(읽기 165회에서 338회). 변형 빌드는 3번 모두 `shutdown()`에서 반환하지 않아 25초에 감시 타이머가 프로세스를 끝냈습니다. 규칙(CEF를 부르는 호출은 GIL을 놓는다)이 필요하다는 근거입니다.

## F26. 문자열 벡터와 프레임

- **방법**: `browser.get_frame_names()`, `get_frame_identifiers()`(라이브러리의 출력 인자)와 `on_favicon_url_change`(핸들러의 입력)를 실행했습니다.
- **결과**: 둘 다 `list[str]`로 오고 내용이 맞습니다(프레임 이름 `inner`, 아이콘 URL `http://fav.test/icon.png`). 이름 목록의 순서는 일정하지 않았습니다. 식별자는 `5-<16진수>` 꼴의 문자열입니다.
- **부수 발견**: F27 (`data:` 페이지의 `srcdoc` iframe).
- **부수 수정**: 핸들러가 받는 문자열, 구조체, 목록은 `optional_param` 표시와 상관없이 `None`이 아니라 값(빈 값 포함)으로 옵니다. 스텁이 `title: str | None`처럼 잘못 적었던 5곳을 고쳤습니다. 라이브러리 메서드의 입력만 `None`을 허용합니다.

## F27. data: 페이지의 srcdoc iframe이 로드를 끝내지 못한다 (CEF 154.0.34의 문제)

- **증상**: 페이지 URL이 `data:`(또는 `about:blank`)이고 `<iframe srcdoc=...>`가 있으면 `on_load_end`가 오지 않고 로딩 상태가 계속 참입니다. 자식 프레임의 `about:srcdoc` 탐색이 `on_load_error`로 `ERR_ABORTED`(-3)로 보고됩니다. 렌더러는 CPU를 쓰지 않고 잠든 채(`Sl`) 원격 디버깅의 `Page.getFrameTree`와 `Runtime.evaluate`에도 응답하지 않습니다.
- **원인은 cefweaver가 아닙니다.** CEF 배포본의 공식 예제 `cefsimple`(우리 코드 없음, 같은 `libcef` 154.0.34)을 따로 빌드해 같은 페이지를 열어도 똑같이 멈추고, 다른 페이지는 정상입니다. 일반 Google Chrome 155는 같은 페이지를 정상으로 로드합니다(`document.readyState`가 `complete`, iframe 내용 `child`).
- **조건 비교** (모두 `srcdoc` iframe 포함 페이지):

  | 부모 페이지 | 결과 |
  | --- | --- |
  | `data:` URL (시작 URL이든 `load_url`이든, base64든 퍼센트 인코딩이든) | 멈춤 |
  | `about:blank`에서 JavaScript로 iframe을 넣음 | 멈춤 |
  | `http://`(`add_resource`) | 정상 |
  | `http://` + CSP `sandbox`(출처가 불투명) | 정상 |
  | `file://` | 정상 |
  | `data:` 부모의 `<iframe src="about:blank">`, `<iframe src="data:...">` | 정상 |

- **배제한 것**: GPU(`disable-gpu`, `disable-gpu-compositing`, swiftshader, `in-process-gpu`), 샌드박스, 사이트 격리(`disable-site-isolation-trials`, `disable-features=IsolateOrigins,site-per-process`), `disable-web-security`, 렌더러 백그라운딩, Chrome/Alloy 스타일(두 스타일 모두 멈춤), 클라이언트 위임(`set_client` 없이도 멈춤), JS 바인딩, 출처의 불투명성(CSP `sandbox`로 확인), CEF 렌더러에 붙는 기능 플래그(일반 Chrome에 같은 `--enable-features`, `--disable-features`를 줘도 정상).
- **고칠 수 없는 이유**: 원인이 미리 빌드된 `libcef` 안에 있습니다. `ptrace_scope=1`이라 렌더러에 `gdb`를 붙이지 못했고 `libcef`는 심볼이 없어서 스택을 봐도 이름이 나오지 않을 것입니다. 받을 수 있는 가장 새 버전이 154.0.34입니다.
- **확인하지 못한 것**: 152 등 이전 CEF에서도 같은지(152의 `cefsimple`은 원격 디버깅 포트를 열지 않아 시간 관계로 중단), 이후 CEF에서 고쳐졌는지.
- **우회**: 페이지를 `app.add_resource("http://...")`로 제공하거나 `file://`을 쓰고, `data:` 페이지에서는 `srcdoc` 대신 `src`를 쓰는 iframe을 씁니다.
- **시험**: `test_known_cef_issue_a_srcdoc_iframe_in_a_data_page_never_finishes_loading`이 `expectedFailure`로 이 문제를 지킵니다. CEF가 고치면 "예상 밖 성공"으로 알려 줍니다. `test_a_srcdoc_iframe_loads_in_a_page_served_over_http`가 우회를 확인합니다.

## F28. types 모듈

- **방법**: 헤더의 열거형 101개를 파싱해 `cefweaver/types.py`를 만들고 wheel에 넣어 실행했습니다.
- **결과**: 100개를 읽었고 1개(`cef_color_id_t`, 매크로로 만든 목록)를 건너뜁니다. 클래스 이름은 중복이 없고, 비트 플래그가 17개입니다. `ErrorCode`는 네트워크 오류 목록을 확장해 250개 멤버를 가집니다(`CONNECTION_REFUSED == -102`). 핸들러가 받은 `error_code`는 `types.ErrorCode.CONNECTION_REFUSED` 멤버(같은 객체)이고, `SHIFT_DOWN | CONTROL_DOWN`으로 보낸 클릭은 페이지의 `shiftKey`와 `ctrlKey`가 참, `altKey`가 거짓으로 도착했습니다. 라이브러리 메서드의 반환(`Request.get_resource_type()`)도 멤버입니다.
- **부수 발견(제 실수)**: 전처리 조건을 처리하는 첫 구현이 "이 분기가 선택되었는가" 대신 "이 `#if` 묶음에서 이미 분기가 선택되었는가"를 봐서 `#else` 가지의 멤버까지 포함했고, 그 결과 `ContentSettingTypes`에 같은 이름이 두 번 나와 `types.py`를 불러오지 못했습니다. 시험(`test_only_the_selected_branch_of_a_condition_is_read`, `test_every_enumerator_is_defined_once`)을 먼저 추가해 실패를 확인한 뒤 고쳤습니다.
- **부수 발견(빌드)**: F27을 조사하며 Chrome 스타일 변형으로 만든 정적 라이브러리를 소스만 되돌리고 다시 빌드하지 않아, 그 뒤 wheel이 Chrome 스타일로 만들어졌습니다. 스타일을 고정하는 시험(`test_the_browsers_are_alloy_style`)이 잡았습니다. 네이티브 소스를 건드렸다 되돌렸다면 `python tools/prepare.py`를 다시 실행해야 합니다.

## F29. 라이브러리 메서드의 출력 인자

- **방법**: `MenuModel`(창 없이 만들 수 있음)과 `Display`를 범위에 넣고 출력 인자를 가진 메서드를 실행했습니다. `Display`는 변환이 눈에 보이도록 `--force-device-scale-factor=2`를 주었습니다.
- **결과**:
  - 출력 전용: `menu.get_accelerator(1)`은 설정 전 `(False, 0, False, False, False)`, `set_accelerator(1, 65, True, False, True)` 뒤 `(True, 65, True, False, True)`. `get_color`는 `cef_color_t`(정수의 typedef)를 `(True, 0xFF112233)`으로 돌려줍니다.
  - 구조체 입출력: 배율 2.0에서 `convert_point_to_pixels(Point(10, 20))`이 `Point(20, 40)`, `convert_point_from_pixels((40, 80))`이 `(20, 40)`입니다. 배율 1.0에서도 `(10, 20)`을 그대로 돌려주어 값이 CEF로 들어가는 것이 확인됩니다(출력 전용이었다면 `(0, 0)`). 일반 튜플도 받습니다.
  - `Display`의 경계는 배율 2.0에서 DIP로 640x512(1280x1024 화면)입니다.
  - `MenuModel.create_menu_model(delegate)`에는 `MenuModelDelegate`(핸들러 7개 메서드)가 필요하고, 창이나 브라우저 없이 `initialize()` 뒤에 만들 수 있었습니다.
- **영향**: 라이브러리 출력 인자(기본형, 문자열, 열거형, 구조체)를 지원합니다. 모든 클래스를 넣었을 때의 지원이 87%가 되었고 "출력 인자" 장애물이 사라졌습니다.

## F30. 벡터의 요소 종류와 종료 뒤에 해제되는 객체

- **방법**: `PrintSettings`, `Display`, `TaskManager`, `DragHandler`를 범위에 넣고 요소가 구조체, 객체, 정수인 벡터를 실행했습니다.
- **결과**:
  - 구조체 목록: `set_page_ranges([Range(1, 3), (5, 5), Range(9, 12)])` 뒤 `get_page_ranges()`가 `Range` 세 개를 돌려주고(`get_page_ranges_count() == 3`), 값이 세 개가 아닌 튜플은 `TypeError`입니다.
  - 객체 목록: `Display.get_all_displays()`가 `Display` 객체의 목록이고 주 디스플레이의 ID를 포함합니다.
  - 정수 목록: `TaskManager.get_task_manager().get_task_ids_list()`가 `(True, [0, 1, 2, 3, 4, 5])`이고 길이가 `get_tasks_count()`와 같습니다.
  - 핸들러 입력, 중첩 구조체: CSS `-webkit-app-region: drag` 요소가 있는 페이지에서 `on_draggable_regions_changed`가 `[DraggableRegion(bounds=Rect(10, 20, 300, 40), draggable=1)]`로 불립니다(`bounds`가 `Rect`).
- **크래시와 수정**: `TaskManager` 객체가 프로세스 종료까지 살아 있으면 인터프리터가 정리하면서 종료된 CEF에 `Release()`를 불러 **SIGTRAP**(종료 코드 133)이 납니다. 메서드를 부르지 않아도 매번 그랬고(4가지 변형 모두), `shutdown()` 앞에 `del`하면 정상입니다. `Browser`, `Display` 등은 괜찮았습니다. 수정: `shutdown()` 뒤에 해제되는 라이브러리 객체는 `Release()`를 부르지 않고 버립니다(`__dealloc__`). 시험(`test_a_library_object_that_outlives_shutdown_does_not_crash_the_process`)을 먼저 쓰고 크래시를 확인한 뒤 고쳤습니다. 여러 객체를 한꺼번에 쥔 첫 시험은 해제 순서가 달라서 크래시하지 않아 시험으로 쓸모가 없었습니다.

## F31. Alloy 스타일과 Wayland, 창 관리자 아래의 창 제목

- **방법**: 실제 Wayland 데스크톱(GNOME mutter + XWayland)에서 `ozone-platform`을 바꿔 실행했습니다(사용자의 허락). 상세와 표는 [Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)에 있습니다.
- **결과**: XWayland(`x11`)는 정상(88프레임, NVIDIA WebGL, 종료 코드 0)이고, 네이티브 Wayland(`wayland`, 미지정)는 약 1초 뒤 `SIGTRAP`입니다. 페이지와 제목 코드와 무관하며, `cefsimple`의 Alloy는 Wayland에서 살아 있었습니다.
- **창 제목의 버그**: Alloy로 바꿀 때 구현한 창 제목 설정이 "루트의 자식 창까지 올라가기"를 했는데, 창 관리자가 있는 실제 데스크톱에서는 CEF의 최상위 창(`GetWindowHandle()`, `WM_STATE: Normal`)을 지나 **창 관리자의 프레임 창**(`mutter-x11-frames`)에 제목을 써서 보이지 않았습니다. 창 관리자가 없는 Xvfb에서는 이 오류가 드러나지 않아 시험이 통과했습니다. 핸들에 직접 쓰도록 고쳤습니다(`cefsimple`과 같은 방식). 또 Wayland에서 `cef_get_xdisplay()`를 먼저 부르면 죽을 수 있어서 창 핸들(Wayland에서는 비어 있음)을 먼저 확인합니다.
- **시험**: 실제 화면에 창을 여는 시험이라 기본 실행에서는 건너뛰고 `CEFWEAVER_TEST_WAYLAND=1`일 때만 실행합니다(`WithCefOnWayland`). 기본값이 X11인지와 창 제목(실제 창 관리자 아래)을 확인하는 시험과, 명시한 `wayland`의 크래시를 기록하는 `expectedFailure` 시험이 있습니다.

## F32. 컨텍스트 메뉴를 코드로 열고 고르기, DevTools 항목의 켜고 끔

- **방법**: `host.send_mouse_click_event`로 오른쪽 클릭을 주입하고(누름과 뗌, 메뉴가 열릴 때까지 다시 보냄), 사용자 핸들러의 `run_context_menu`에서 `callback.continue_(id, 0)`으로 항목을 골랐습니다. `app.devtools_menu`를 끈 채와 켠 채로 같은 시나리오를 실행했습니다.
- **결과**:
  - 메뉴는 CEF의 기본 항목(로케일을 따라 한국어 "뒤로", "앞으로", "인쇄", "페이지 소스 보기" 등) 뒤에 사용자의 항목이 붙고, `params`의 좌표는 클릭한 곳(30, 30)입니다. 사용자가 고른 명령이 `on_context_menu_command`로 옵니다.
  - 켠 쪽의 메뉴는 끈 쪽의 메뉴 **뒤에** 구분선과 DevTools 항목 셋(ID 28498~28500)이 붙은 것과 같고, 사용자의 핸들러가 `on_before_context_menu`에서 본 항목 수(5)와 받은 명령은 켜든 끄든 같습니다.
  - 켠 채 "Show DevTools"를 고르면 사용자의 핸들러는 호출되지 않고 `host.has_dev_tools()`가 참이 됩니다.
  - 사용자가 처리하지 않은 표준 명령(전체 선택, ID 117)은 CEF가 실행해서 페이지의 선택이 `'hello'`가 됩니다(켠 채와 끈 채 모두).
- **기존 결함 확정**: 예전의 `OnContextMenuCommand`는 모르는 명령에 `true`를 돌려주었습니다. 그 동작을 되살린 변형 빌드에서는 전체 선택 뒤 페이지의 선택이 `''`로 비어 있었습니다. 표준 명령이 컨텍스트 메뉴에서 실행되지 않던 실제 버그입니다.
- **영향**: 컨텍스트 메뉴를 사용자에게 열었고, 래퍼의 DevTools 항목은 기본 끔으로 바꾸었습니다(이전에는 항상 켜짐).

## F33. 프로세스 메시지와 값 컨테이너

- **방법**: `ProcessMessage`, `ListValue`, `DictionaryValue`를 만들고, `cefweaver-ping`을 렌더러로 보내 `cefweaver-pong`을 `Client.on_process_message_received`로 받았습니다.
- **결과**:
  - 값 컨테이너는 CEF를 시작하기 전에도 동작합니다. 한글 문자열, 정수, 불리언, 실수, 중첩 사전과 목록이 왕복하고, `get_keys()`는 `(True, ['k', 'n'])`, `get_type()`은 `ValueType` 멤버입니다.
  - 렌더러 왕복: 보낸 정수, 한글 문자열, 중첩 사전이 그대로 돌아오고 `source_process`는 `ProcessId.RENDERER` 멤버입니다.
  - 보낸 메시지는 소유권이 넘어가서 `is_valid()`가 거짓이 됩니다(CEF 문서대로).
  - 래퍼의 JavaScript 바인딩은 같은 실행에서 계속 동작하고, 래퍼의 메시지(`javascript-python-binding`)는 사용자의 핸들러에 오지 않습니다(사용자가 받은 이름은 `cefweaver-pong` 하나).
- **영향**: 프로세스 메시지 수신을 이름으로 나누는 방식이 동작합니다. 렌더러가 C++라서 사용자 정의 메시지를 보내는 쪽은 진단용 ping/pong뿐입니다([알려진 제약과 미검증 항목](known-constraints.md)).

## 관련 페이지

- [실험으로 확인한 사실](verified-findings.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [설계 결정 기록](design-decisions.md)
- [types 모듈](types-module.md)
