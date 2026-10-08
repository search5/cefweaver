---
title: 시험 (tests/)
type: component
sources:
  - tests/test_smoke.py
  - tests/test_generator.py
  - CLAUDE.md
updated: 2026-10-08
---

# 시험 (tests/)

`unittest`로 작성한 시험이 세 파일에 176개(통합 86, 생성기 89, 위키 점검 1) 있습니다. 그 가운데 1개는 CEF의 알려진 문제를 지키는 `expectedFailure`이고, 2개는 실제 Wayland 데스크톱에 창을 여는 선택 실행입니다(`CEFWEAVER_TEST_WAYLAND=1`). 그 가운데 1개는 CEF의 알려진 문제를 지키는 `expectedFailure`입니다. 실행 방법은 [시험 실행하기](../procedures/run-tests.md)에 있습니다.

## tests/test_smoke.py: 설치된 wheel의 통합 시험

설치된 wheel을 대상으로 하며 소스 트리에서는 `import cefweaver`가 확장 모듈을 못 찾아 시험을 건너뜁니다.

| 클래스 | 시험 | 확인하는 것 |
| --- | --- | --- |
| `ApiWithoutCef` (CEF를 띄우지 않음) | `test_calls_before_initialize_raise` | 초기화 전의 `do_message_loop_work`, `load_url`, `execute_javascript`가 `RuntimeError` |
| | `test_binding_must_be_callable` | 호출 불가능한 객체는 `TypeError` |
| | `test_generated_names_are_public_and_pep8` | 생성된 이름의 공개 여부, `continue_`, `get_url`, `get_mime_type("html")` |
| | `test_library_objects_cannot_be_created_directly` | `Request()` 거부, `Request.create()`는 초기화 전에도 동작 |
| | `test_add_resource_needs_a_running_cef` | 초기화 전 `add_resource`는 `RuntimeError` |
| | `test_the_client_and_its_handlers_are_public` | `Client`, `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`의 공개 여부 |
| | `test_value_types_are_named_tuples` | `Point`, `Rect`, `Size`, `Insets`, `Range`, `MouseEvent`의 공개 여부, 튜플 동작, 필드 이름(`from_`) |
| | `test_the_browser_host_is_public` | `BrowserHost`와 주요 메서드, `Browser.get_host`의 공개 여부 |
| | `test_browser_lists_its_frames_as_lists_of_strings` | `Browser.get_frame_names`, `get_frame_identifiers`의 공개 여부 |
| | `test_known_cef_issue_a_srcdoc_iframe_in_a_data_page_never_finishes_loading` | `expectedFailure`. `data:` 페이지의 `srcdoc` iframe이 로드를 끝내지 못하는 CEF의 문제(F27)를 기록하고, CEF가 고치면 알려 줌 |
| | `test_a_srcdoc_iframe_loads_in_a_page_served_over_http` | F27의 우회(`add_resource`로 제공) |
| | `test_the_types_module_has_the_enumerations_and_value_types` | `cefweaver.types`의 `IntEnum`, `IntFlag`, 값 타입이 `cefweaver`의 것과 같은 객체 |
| | `test_library_methods_return_enumeration_members` | `Request.get_resource_type()`이 `ResourceType` 멤버이고 여전히 `int` |
| | `test_the_menu_model_and_the_display_are_public` | `MenuModel`, `MenuModelDelegate`, `Display`의 공개 여부 |
| | `test_print_settings_and_the_drag_handler_are_public`, `test_the_task_manager_is_public` | 새 클래스의 공개 여부 |
| `ApiWithoutCef` | `test_the_context_menu_classes_and_the_devtools_switch_are_public` | 컨텍스트 메뉴 클래스의 공개 여부, `devtools_menu`의 기본값(`False`)과 설정 |
| `ApiWithoutCef` | `test_the_process_message_and_the_value_containers_are_public`, `test_values_can_be_built_and_read_without_cef` | 클래스의 공개 여부, CEF 없이 값 컨테이너의 왕복(한글, 중첩, `ValueType` 멤버, `get_keys`) |
| `ApiWithoutCef` | `test_the_message_router_api_is_public_and_checks_its_arguments` | `QueryHandler`, `QueryCallback`의 공개 여부, 인자 검사, 없는 핸들러 빼기 |
| `WithCef` | `test_a_page_asks_and_the_handler_answers_with_success_or_failure`, `test_a_persistent_query_can_answer_many_times_and_the_page_can_cancel_it`, `test_leaving_the_page_cancels_its_pending_queries`, `test_binary_requests_and_responses`, `test_handlers_are_asked_in_order_and_can_be_removed`, `test_the_names_of_the_query_functions_can_be_changed`, `test_without_a_query_handler_the_page_has_no_query_function`, `test_a_callback_that_is_dropped_without_an_answer_fails_the_query`, `test_the_router_works_with_bindings_and_the_users_process_messages` | 성공, 실패, 나중에 다른 스레드에서 답함, 처리 안 됨(-1), 지속 질의와 취소, 이동으로 취소, `ArrayBuffer` 왕복, 핸들러 순서와 빼기, 함수 이름 바꾸기, 핸들러가 없으면 `cefQuery`가 없음, 버려진 콜백이 질의를 실패시킴, 바인딩 및 사용자 메시지와 공존 |
| `WithCef` | `test_queries_from_a_frame_know_their_frame_and_only_that_frame_is_canceled`, `test_queries_from_a_popup_browser_and_its_close` | iframe의 질의가 자기 프레임으로 가고 이동하면 그 프레임만 취소됨, 팝업 브라우저의 질의와 닫을 때의 취소, 팝업을 닫은 뒤에도 첫 브라우저가 동작함 |
| `ApiWithoutCef` | `test_the_offscreen_api_is_public_and_checks_its_arguments` | `RenderHandler`의 공개 여부, `offscreen`과 `windowless_frame_rate`의 기본값과 범위 검사 |
| `ApiWithoutCef` | `test_the_structs_with_a_size_header_are_public_values` | `KeyEvent`, `ScreenInfo`, `PopupFeatures`, `TouchEvent`, `TouchHandleState`, `CompositionUnderline`의 공개 여부와 필드 이름 |
| `ApiWithoutCef` | `test_binary_values_take_and_give_bytes` | `BinaryValue.create`와 `get_data`: 바이트열 종류, 오프셋, 남은 것보다 큰 요청, 빈 데이터는 `None`, 잘못된 인자(`TypeError`, 음수는 `OverflowError`), 리스트에 넣은 뒤 소유권 |
| `WithCef` | `test_the_keyboard_handler_sees_key_events_before_the_page`, `test_the_print_handler_sees_the_start_the_settings_and_the_reset` | 오프스크린에서 보낸 키 이벤트가 `on_pre_key_event`로 먼저 옴(`KeyEvent`), `host.print()`의 `on_print_start`, `on_print_settings`(`PrintSettings`), `on_print_reset` |
| `WithCef` | `test_the_focus_handler_sees_the_focus_of_the_browser`, `test_javascript_dialogs_are_answered_by_the_handler`, `test_the_file_dialog_gets_the_files_from_the_handler`, `test_a_download_is_saved_where_the_handler_says` | `set_focus`가 `on_set_focus`(`FocusSource`)와 `on_got_focus`로 감, `alert`/`confirm`/`prompt`에 핸들러가 답함, 파일 입력을 눌러 핸들러가 고른 파일이 페이지에 들어감, 첨부 파일이 핸들러가 정한 경로에 저장됨 |
| `WithCef` | `test_binary_values_travel_in_process_messages` | 256가지 바이트가 렌더러를 왕복 |
| `WithCef` | `test_keyboard_events_type_into_an_offscreen_page`, `test_the_handler_gives_the_screen_info_and_the_page_sees_the_scale`, `test_touch_events_and_ime_compositions_are_accepted` | 키 입력이 입력란에 들어감, 화면 정보의 배율이 페이지와 프레임 크기에 반영됨, 터치와 IME 인자가 변환됨 |
| `WithCef` | `test_on_paint_gives_a_read_only_view_of_the_pixels`, `test_the_view_size_follows_get_view_rect_after_was_resized`, `test_mouse_events_reach_an_offscreen_page`, `test_an_offscreen_browser_blocks_popups_as_java_cef_does` | 오프스크린: 읽기 전용 BGRA 버퍼와 무효화, 크기 변경, 마우스 입력, 팝업 차단, 정상 종료 |
| `WithCef` | `test_a_process_message_makes_a_round_trip_through_the_renderer` | `cefweaver-ping`이 같은 인자로 `cefweaver-pong`이 되어 돌아옴(`ProcessId.RENDERER`), 보낸 메시지가 무효가 됨, 래퍼의 바인딩이 계속 동작하고 래퍼의 메시지가 사용자에게 가지 않음 |
| | `test_a_program_can_open_the_context_menu_and_pick_an_item` | 오른쪽 클릭 주입, 메뉴의 좌표, 사용자 항목의 ID(`USER_FIRST`), 고른 명령이 사용자 핸들러로 옴, 기본은 DevTools 항목 없음 |
| | `test_the_devtools_items_come_after_the_users_and_change_nothing_else` | 켠 메뉴 = 끈 메뉴 + DevTools 항목, 사용자가 본 항목 수와 받은 명령이 같음, ID 28498~28500 |
| | `test_choosing_show_devtools_opens_devtools_without_asking_the_users_handler` | 래퍼의 항목은 래퍼가 처리해 DevTools가 열림(`has_dev_tools`) |
| | `test_a_standard_command_the_user_does_not_handle_runs_as_usual` | 사용자가 `False`를 돌려준 표준 명령(전체 선택)을 CEF가 실행(켠 채와 끈 채). 예전 `return true` 결함을 잡음 |
| `WithCefOnWayland` (선택 실행) | `test_the_default_on_a_wayland_session_is_x11_and_the_window_gets_its_title` | Wayland 세션에서 기본이 X11이고 실제 창 관리자 아래에서 창에 제목이 설정됨 |
| | `test_known_cef_issue_alloy_style_crashes_on_native_wayland` | `expectedFailure`. 명시한 `ozone-platform=wayland`의 크래시를 기록하고 CEF가 고치면 알려 줌 |
| `ApiWithoutCef` | `test_set_client_checks_its_argument` | `Client`가 아닌 객체와 핸들러는 `TypeError`, `None`은 허용 |
| `WithCef` (실제 CEF) | `test_javascript_to_python_binding_and_shutdown` | 네 가지 값 형식(한글 포함)의 전달, 종료 후 `is_running`이 거짓 |
| | `test_zero_argument_call_and_exceptions_do_not_crash` | 인자 없는 호출, 콜백 예외가 CEF를 죽이지 않음 |
| | `test_load_url_and_execute_javascript` | 로딩 중 `False`, 준비 뒤 `True`, `load_url` 후 실행 |
| | `test_add_resource_serves_pages_without_a_network` | 가짜 URL 페이지, 하위 리소스, 300KB 본문 해시, 헤더, 404 |
| | `test_resource_handler_can_answer_later_from_another_thread` | `open`이 `(True, False)` 후 다른 스레드의 `continue_()` |
| | `test_exceptions_in_a_resource_handler_do_not_crash` | 핸들러와 팩토리의 예외가 보고되고 이후 페이지는 정상 |
| | `test_client_handlers_receive_events_and_the_wrapper_keeps_working` | 생성, 시작, 종료, 상태, 제목, 닫힘 이벤트와 그 순서, 모두 `initialize()`를 부른 스레드, 래퍼의 준비 플래그와 JS 바인딩 유지 |
| | `test_on_load_error_reports_the_failure_and_the_wrapper_still_shows_its_page` | 닫힌 로컬 포트의 오류 코드(-102)와 URL, 래퍼의 `data:` 오류 페이지 |
| | `test_a_client_without_handlers_and_broken_handlers_do_not_disturb_the_wrapper` | 클라이언트와 핸들러의 예외가 보고되고 래퍼는 정상 |
| | `test_set_client_must_come_before_initialize` | 초기화 뒤의 `set_client`는 `RuntimeError` |
| | `test_browser_host_gives_back_its_browser_and_sets_the_zoom` | `get_host`와 `get_browser`의 일치, `get_browser_by_identifier`, 줌 설정 |
| | `test_mouse_events_reach_the_page_at_their_coordinates` | 첫 프레임을 기다린 뒤 두 클릭의 정확한 좌표와 버튼, `MouseEvent`와 일반 튜플, 잘못된 인자의 `TypeError` |
| | `test_auto_resize_reports_the_content_size_to_the_display_handler` | `on_auto_resize`가 `Size`를 받음(구조체 입력의 Python 경로) |
| | `test_the_browsers_are_alloy_style` | `get_runtime_style() == 2`(스타일을 바꾸면 이 시험이 실패해서 문서를 고치게 함) |
| | `test_do_close_can_keep_the_browser_open` | 첫 닫기가 `do_close(True)`로 취소되고 두 번째가 `on_before_close`와 종료로 이어짐 |
| | `test_the_window_title_follows_the_page_title` | 최상위 창(루트의 직접 자식)에 페이지 제목이 설정됨(`xwininfo`가 없으면 건너뜀) |
| | `test_a_browser_lists_the_names_and_identifiers_of_its_frames` | 두 목록이 `list[str]`이고 길이가 같으며 자식 프레임 이름을 포함 |
| | `test_favicon_urls_reach_the_display_handler_as_a_list_of_strings` | `on_favicon_url_change`가 `['http://fav.test/icon.png']`를 받음 |
| | `test_handlers_receive_enumeration_members_and_modifiers_are_flags` | `on_load_error`가 `ErrorCode` 멤버를 받음, `SHIFT_DOWN \| CONTROL_DOWN`이 페이지의 수정자로 도착 |
| | `test_output_parameters_of_a_library_method_come_back_with_its_result` | `MenuModel`의 가속키(여러 출력)와 색(typedef 정수 출력)이 결과 뒤에 돌아옴 |
| | `test_a_struct_given_to_a_library_method_is_changed_and_returned` | `Display`의 좌표 변환(배율 2)이 구조체를 읽고 바꿔 돌려줌, 일반 튜플도 받음 |
| | `test_lists_of_structs_go_into_and_come_out_of_a_library_object` | `PrintSettings`의 `Range` 목록 왕복(`Range`와 일반 튜플), 잘못된 길이의 `TypeError` |
| | `test_a_list_of_objects_comes_out_of_a_library_method` | `Display.get_all_displays()` |
| | `test_a_list_of_integers_comes_out_of_a_library_method` | `TaskManager.get_task_ids_list()`의 `(True, [정수...])`, 개수 일치 |
| | `test_a_library_object_that_outlives_shutdown_does_not_crash_the_process` | 종료 뒤에 해제되는 `TaskManager`가 SIGTRAP을 내지 않음 |
| | `test_the_drag_handler_receives_the_draggable_regions_as_value_types` | CSS 드래그 영역 → `DraggableRegion(bounds=Rect(...))` 목록 |
| | `test_initialize_after_shutdown_raises_instead_of_crashing` | `shutdown()` 뒤 `initialize()`는 `RuntimeError`(전에는 세그멘테이션 오류) |
| | `test_the_process_can_end_without_shutdown` | 핸들러가 살아 있고 요청이 진행 중인 채 종료해도 정상 종료 |
| | `test_a_path_the_factory_declines_goes_on_to_the_default_handling` | `create()`가 `None`이면 CEF 기본 처리로 넘어가 `on_load_error` |
| | `test_resource_handler_callbacks_run_on_threads_other_than_the_ui_thread` | 리소스 핸들러 콜백이 메인 스레드가 아님 |

## tests/test_generator.py: 생성기 시험

CEF를 실행하지 않고 헤더만 읽습니다(`build/native/cef`가 없으면 헤더 시험은 건너뜀).

- 이름 규칙: `snake_case`, 예약어 밑줄, 접두사 제거
- 타입 분류: 클래스 이름은 선언에서 얻음, 출력 인자 순서(반환값 먼저), `void*`와 크기 쌍, 열거형과 구조체 구분, 지원하지 못하는 타입의 사유, 순수 가상 감지, 기본형과 문자열
- `CefClient`와 세 핸들러가 범위에 있는지, 클라이언트의 `get_..._handler`가 핸들러 반환으로 분류되는지, 범위 밖 핸들러가 사유와 함께 보고되는지
- 모든 핸들러에 전달 클래스가 생성되는지, 그리고 **실제 C++ 컴파일러**로 클라이언트와 세 핸들러의 전달 클래스를 한 참조 계수 클래스에 합칠 수 있는지(`c++ -fsyntax-only`, 컴파일러가 없으면 건너뜀)
- 값 타입 구조체: 필드를 C 헤더에서 읽는지, 예약어 필드 이름, 평범한 데이터가 아닌 구조체의 제외, 핸들러의 구조체 입력과 출력, 라이브러리 메서드의 구조체 입력과 반환, 핸들러의 구조체 반환이 이유와 함께 보고되는지, 표의 C 타입, 스텁의 `NamedTuple`
- **생성된 C++ 프록시를 컴파일해서 실행**: 입력 구조체가 포인터로 전달되고 출력 구조체가 참조 인자에 복사되는지(`libcef.so`가 없으면 건너뜀)
- 프로세스 메시지: 클래스가 범위에 있는지, `Frame.send_process_message`와 `Client.on_process_message_received`의 분류, `BinaryValue`의 타입 없는 포인터 보고, 스텁
- 컨텍스트 메뉴: 클래스가 범위에 있는지, 핸들러의 7개 메서드가 모두 생성되는지, `run_context_menu`가 콜백을 받는지(코드에서 항목을 고르는 수단), 전달 클래스, 스텁
- 벡터: 구조체, 객체, 정수 목록의 분류와 방향별 허용, 중첩 구조체, 스텁의 `Sequence[...]`와 `list[...]`, 정적 메서드, 표의 요소 타입. 생성된 C++ 프록시 실행 시험에 `CefDraggableRegion` 벡터가 들어 있습니다.
- 라이브러리 메서드의 출력 인자: 출력 전용(가속키의 여러 출력, typedef 출력, 문자열)과 구조체 입출력의 분류, 핸들러의 출력 인자는 출력 전용인지, 새 클래스가 범위에 있는지, 스텁의 튜플 반환과 `Point | tuple[int, int]`
- 열거형: 값 읽기(마우스 버튼, 오류 코드, 평가된 시프트와 마스크), 비트 플래그 판별, 전처리 분기, 멤버 중복 없음, 생성된 `types.py`의 실행, 스텁의 임포트와 `ErrorCode`, `MouseButtonType | int`
- 문자열 벡터: 라이브러리 메서드의 출력 인자(`get_frame_names`)와 핸들러의 입력(`on_favicon_url_change`)의 분류, 그 밖의 벡터가 이유와 함께 보고되는지, 표의 C 타입, 스텁의 `list[str]`. 생성된 C++ 프록시 실행 시험에도 벡터 전달이 들어 있습니다.
- `CefBrowserHost`가 범위에 있고 `Browser.get_host`로 닿는지, 구조체와 열거형 인자의 분류, 열리지 않는 메서드의 이유
- 생성 파일이 최신인지, 두 번 생성한 결과가 같은지

## tests/test_wiki.py: 위키 점검

`docs/llm-wiki/lint.py --quiet`를 실행해서 종료 코드가 0인지 확인합니다(1개). 링크, `sources` 경로, 색인 등재, frontmatter, 로그 형식이 깨지면 이 시험이 실패합니다. CEF나 wheel이 필요하지 않습니다.

## 설계 원칙

`CLAUDE.md`의 "시험 작성 원칙"을 따릅니다([java-cef 시험과의 비교](../analyses/java-cef-test-comparison.md)).

- **조건을 기다립니다.** `wait_until(app, 조건, 설명)`이 메시지 루프를 돌리다가 조건이 맞으면 즉시 끝나고, 시간이 지나면 기다린 대상을 밝히는 `TimeoutError`로 실패합니다.
- **CEF를 띄우는 시험은 시험마다 새 프로세스**(`run_cef()`가 `python -I -c`로 실행)에서 돕니다. 한 시험의 크래시가 다른 시험을 막지 않게 하기 위해서입니다. java-cef는 JVM 하나에서 CEF를 공유합니다.
- 실패 메시지에는 출력의 끝 3,000자만 넣습니다(한 번 긴 출력이 터미널을 덮은 적이 있습니다).
- `assertClean()`이 종료 코드 0과 `stack smashing` 부재를 확인합니다.
- **화면 안전**: CEF 시험은 `DISPLAY`가 있고 `WAYLAND_DISPLAY`가 없을 때만 실행되고, 각 스크립트는 `ozone-platform=x11`을 지정합니다. Wayland 세션에서는 Chromium이 실제 화면에 창을 열 수 있기 때문입니다([Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)).

## 아직 없는 시험

창 닫기 경로(`is_running`이 거짓이 되는 것)는 `python-xlib`로 확인했을 뿐 저장소의 시험에는 없습니다. 여러 Python 버전을 도는 시험은 수동으로 했고 CI가 없습니다. Windows 시험도 없습니다.

## 관련 페이지

- [시험 실행하기](../procedures/run-tests.md)
- [실험으로 확인한 사실](../reference/verified-findings.md)
- [생성기 모듈](generator-modules.md)
