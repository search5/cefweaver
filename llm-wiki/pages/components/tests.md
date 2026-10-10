---
title: 시험 (tests/)
type: component
sources:
  - tests/test_smoke.py
  - tests/test_generator.py
  - tests/test_ui.py
  - CLAUDE.md
updated: 2026-10-10
---

# 시험 (tests/)

`unittest`로 작성한 시험이 다섯 파일에 527개(통합 221, 생성기 125, UI 164, 위키 점검 2, 문서 점검 15) 있습니다. `unittest` 로더로 2026-10-10에 센 값이고, 전체를 한 번 돌린 실행은 526개(건너뜀 9, 예상된 실패 3)였고, 그 뒤에 생성기 시험 1개를 더해 527개입니다([F108](../reference/verified-findings-opened.md)).

macOS에서는 `test_smoke.py`가 `cefsubprocess.app`이 있으면 CEF 시험을 실행하고(`RUNTIME_OK`), Linux 전용인 `ozone-platform` 스위치를 주지 않으며, 일부는 `skipIf`로 건너뜁니다. `test_generator.py`에는 플랫폼마다 다른 구조체를 중립 형식으로 읽는지 보는 시험이 하나 있습니다. 결과는 [F81~F82](../reference/verified-findings-macos.md)에 있습니다.

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
| `ApiWithoutCef` | `test_streams_read_and_write_bytes_in_items`, `test_python_objects_can_be_the_source_and_the_sink_of_a_stream`, `test_a_zip_reader_reads_a_file_of_the_archive` | 파일 스트림의 항목 단위 읽기와 쓰기(항목 크기, 부분 읽기, 끝, `seek`), 메모리 스트림, Python의 `ReadHandler`와 `WriteHandler`, `zipfile`로 만든 ZIP의 파일 읽기와 열린 파일이 없을 때의 `RuntimeError` |
| `ApiWithoutCef` | `test_a_request_carries_post_data_made_of_bytes` | `PostDataElement.set_to_bytes`/`get_bytes`(크기가 앞인 규약, 부분, 남은 것보다 큰 요청, 잘못된 인자), `PostData`와 `Request.set_post_data`로 왕복 |
| `ApiWithoutCef` | `test_header_maps_are_dicts` | `Request`/`Response`의 `get_header_map`/`set_header_map`/`Request.set`이 `dict`로 왕복함(대소문자 구분 없는 조회, 빈 맵, 잘못된 인자) |
| `ApiWithoutCef` | `test_structs_with_strings_and_times_have_defaults` | 문자열과 시간이 든 구조체(`PdfPrintSettings`, `Cookie`)와 모든 구조체의 기본값 |
| `ApiWithoutCef` | `test_a_command_line_is_built_and_read` | `CommandLine`을 CEF 없이 만들고 읽음(`set_program`, `append_*`, `get_switches`(`dict`), `get_arguments`, `reset`) |
| `ApiWithoutCef` | `test_drag_data_holds_a_link_text_and_files` | `DragData`의 종류(새 것은 조각), 조각, 링크(메타데이터는 `mime:이름:url`), 파일 경로와 이름 목록, `clone`, `get_file_contents` |
| `WithCef` | `test_dropping_drag_data_on_an_offscreen_page`, `test_starting_a_drag_from_an_offscreen_page`, `test_pending_queries_can_be_canceled_from_the_host` | `drag_target_drag_enter`/`over`/`drop`이 페이지의 `ondrop`에 닿고 `DragHandler.on_drag_enter`가 옴, 마우스로 끌면 `RenderHandler.start_dragging`이 `DragData`(조각 `carried`)와 함께 옴, `cancel_pending_queries`가 질의를 취소하고 페이지에 -1 |
| `WithCef` | `test_the_app_handler_hooks_the_command_line_the_schemes_and_the_context`, `test_a_second_start_of_the_application_reaches_the_first_one` | 훅의 순서(명령줄, 스킴, 컨텍스트), 명령줄에 붙인 스위치가 `get_global_command_line()`에 있음, 사용자 스킴이 렌더러에서도 표준이라 `location.host`가 나옴, 같은 `cache_path`의 두 번째 프로세스가 첫 프로세스의 `on_already_running_app_relaunch`로 옴 |
| `WithCef` | `test_a_request_context_has_preferences_and_can_be_created` | 전역 `RequestContext`(`is_global`, `is_same`), 환경설정(`has_preference`, `get_preference`, `set_preference`가 `(성공, 오류)`, `get_all_preferences`), 새 컨텍스트(`create_context(RequestContextSettings, RequestContextHandler)`) |
| `WithCef` | `test_a_url_request_downloads_with_progress_and_credentials`, `test_a_browser_asks_for_credentials_and_reports_redirects_and_responses` | 로컬 HTTP 서버로: `URLRequest`의 다운로드 데이터와 진행률과 상태, 취소, 인증(`get_auth_credentials`), 브라우저의 `RequestHandler.get_auth_credentials`, `on_resource_redirect`(입출력 `new_url`), `on_resource_response` |
| `WithCef` | `test_the_cookie_manager_sets_visits_and_deletes_cookies`, `test_the_cookie_access_filter_sees_the_cookies_of_a_resource` | `CookieManager`의 `set_cookie`, `visit_all_cookies`, `visit_url_cookies`, `delete_cookies`, `flush_store`와 완료 콜백들(쿠키가 구조체의 문자열과 시간이 CEF에 닿음), `get_cookie_access_filter`의 `can_save_cookie`(`Set-Cookie` 응답)와 `can_send_cookie`(다음 요청) |
| `WithCef` | `test_print_to_pdf_writes_a_pdf_and_tells_the_callback` | `print_to_pdf(path, PdfPrintSettings, callback)`이 `%PDF`로 시작하는 파일을 쓰고 `on_pdf_print_finished(path, True)` |
| `WithCef` | `test_a_string_visitor_gets_the_source_and_the_text_of_a_frame`, `test_run_file_dialog_reports_the_files_the_dialog_handler_chose`, `test_a_devtools_message_observer_gets_the_result_of_a_method` | `Frame.get_source`/`get_text`의 `StringVisitor`, `run_file_dialog`가 `DialogHandler`의 선택을 `on_file_dialog_dismissed`로 알림, `add_dev_tools_message_observer`와 `execute_dev_tools_method(Runtime.evaluate)`의 결과 JSON(`"value":3`) |
| `WithCef` | `test_the_window_handle_is_the_native_window_of_a_windowed_browser`, `test_an_offscreen_browser_has_no_window_handle` | `get_window_handle()`이 창 있는 브라우저에서는 X11 창 번호(양의 정수), 오프스크린에서는 0 |
| `WithCef` | `test_the_life_span_handler_decides_about_a_popup_from_its_url_and_name`, `test_the_display_handler_gets_the_cursor_type` | `on_before_popup(browser, frame, target_url, target_frame_name)`가 `True`면 `window.open`이 `null`, `False`면 두 번째 브라우저가 생김, 마우스를 `cursor:pointer` 위로 옮기면 `on_cursor_change`가 `CursorType.HAND`를 받음 |
| `WithCef` | `test_the_request_handler_can_cancel_a_navigation`, `test_the_resource_request_handler_sees_and_can_cancel_resources`, `test_the_router_and_the_users_request_handler_both_get_the_navigation` | `on_before_browse`가 `True`면 페이지가 로드되지 않음, `get_resource_request_handler`가 돌려준 핸들러의 `on_before_resource_load`가 이미지를 취소하고 `on_resource_load_complete`가 상태와 바이트 수를 줌, 메시지 라우터와 사용자의 핸들러가 한 탐색을 나눠 받음(사용자가 취소하면 질의가 열려 있음) |
| `WithCef` | `test_the_keyboard_handler_sees_key_events_before_the_page`, `test_the_print_handler_sees_the_start_the_settings_and_the_reset` | 오프스크린에서 보낸 키 이벤트가 `on_pre_key_event`로 먼저 옴(`KeyEvent`), `host.print()`의 `on_print_start`, `on_print_settings`(`PrintSettings`), `on_print_reset` |
| `WithCef` | `test_the_focus_handler_sees_the_focus_of_the_browser`, `test_javascript_dialogs_are_answered_by_the_handler`, `test_the_file_dialog_gets_the_files_from_the_handler`, `test_a_download_is_saved_where_the_handler_says` | `set_focus`가 `on_set_focus`(`FocusSource`)와 `on_got_focus`로 감, `alert`/`confirm`/`prompt`에 핸들러가 답함, 파일 입력을 눌러 핸들러가 고른 파일이 페이지에 들어감, 첨부 파일이 핸들러가 정한 경로에 저장됨 |
| `WithCef` | `test_binary_values_travel_in_process_messages` | 256가지 바이트가 렌더러를 왕복 |
| `WithCef` | `test_a_killed_renderer_reaches_the_request_handler_and_cancels_the_queries`, `test_a_ctrl_click_on_a_link_asks_the_handler_before_a_new_tab`, `test_an_external_protocol_reaches_the_resource_request_handler`, `test_a_certificate_error_is_decided_by_the_handler`, `test_the_request_context_handler_is_asked_about_the_requests_of_its_browser` | 렌더러 종료와 질의 취소, Ctrl 클릭의 새 탭 요청, `mailto:`의 프로토콜 실행, 자체 서명 인증서(`openssl`로 만든 로컬 TLS 서버)의 거부와 허용, `set_request_context`로 준 컨텍스트의 핸들러(F55) |
| `ApiWithoutCef` | `test_tasks_and_threads_are_in_the_module` | `Task`, `post_task`, `post_delayed_task`, `currently_on` |
| `WithCef` | `test_a_task_posted_from_any_thread_runs_on_the_ui_thread_in_the_message_loop`, `test_a_task_runs_on_the_io_thread_and_a_delayed_task_waits`, `test_a_task_from_a_thread_wakes_the_message_pump_of_the_application` | 어느 스레드에서 보내도 UI 작업은 메시지 루프에서 UI 스레드로, IO 작업은 IO 스레드로, 지연 작업은 기다린 뒤, 스레드에서 보낸 작업이 `MessagePump`를 깨움(F63) |
| `ApiWithoutCef` | `test_the_app_handler_has_the_message_pump_hook_and_does_nothing_by_default`, `test_a_message_pump_keeps_the_latest_request_and_a_fall_back_timer`, `test_a_message_pump_needs_an_app_that_is_not_started_yet` | 훅의 기본 동작, `MessagePump`의 규약(최신 요청이 대체, 대비 타이머, 다른 스레드, 실행 중의 요청 보존, 시작한 앱 거부) |
| `WithCef` | `test_cef_asks_for_message_loop_work_from_any_thread_when_the_application_asks_for_it`, `test_cef_does_not_schedule_work_unless_the_application_asks_for_it`, `test_a_message_pump_runs_cef_by_the_deadlines_cef_gives_and_never_waits_long` | 설정을 켰을 때만 훅이 여러 스레드에서 불림, `MessagePump`의 기한만으로 페이지 로드(F62) |
| `ApiWithoutCef` | `test_a_browser_cannot_be_created_before_cef_runs` | CEF가 돌기 전의 `create_browser`는 `RuntimeError` |
| `WithCef` | `test_a_second_offscreen_browser_paints_on_its_own_and_the_first_is_unaffected`, `test_each_browser_has_its_own_transparency`, `test_the_bindings_and_the_router_work_in_every_browser`, `test_closing_one_browser_leaves_the_others_and_the_app_running`, `test_a_browser_can_have_a_request_context_of_its_own`, `test_a_windowed_app_can_create_windowed_and_offscreen_browsers`, `test_create_browser_checks_its_arguments` | 둘째 브라우저의 그림과 투명도, 바인딩과 라우터, 하나를 닫아도 계속 도는 앱과 첫 브라우저의 준비 표시, 브라우저별 요청 컨텍스트, 창과 오프스크린의 혼합, 인자 검사(F60) |
| `WithCef` | `test_the_app_can_be_used_from_on_after_created_of_the_first_browser` | 첫 브라우저의 `on_after_created`(`initialize()`가 끝나기 전)에서 `add_resource`, `load_url`, `execute_javascript`가 거부되지 않고 `load_url`이 `True`, 페이지가 로드됨(F67) |
| `WithCef` | `test_a_flags_enum_with_the_highest_bit_can_be_given_to_cef` | `DragOperationsMask.EVERY`(0xFFFFFFFF)를 `drag_target_*`에 넘겨도 넘치지 않음(F68) |
| `ApiWithoutCef` | `test_shared_textures_are_a_flag_and_the_info_is_a_value_type`, `test_read_plane_copies_the_bytes_of_a_descriptor_from_its_offset` | `shared_texture`의 기본값과 형식 검사, `AcceleratedPaintInfo`의 기본값, `read_plane`이 오프셋부터 복사하고 잘못된 디스크립터에 `OSError` |
| `WithCef` | `test_a_shared_texture_browser_gets_a_frame_one_way_or_the_other` | 켠 브라우저가 텍스처든 `on_paint`든 한쪽으로만 프레임을 받음(GPU 없는 Xvfb에서는 `on_paint`, F66) |
| `WithCef` | `test_a_shared_texture_arrives_as_dmabuf_planes_in_place_of_pixels` | `CEFWEAVER_TEST_GPU=1`일 때만. 실제 GPU와 디스플레이에서 평면, 디스크립터, 형식, 더티 사각형, 새 프레임(F66) |
| `WithCef` | `test_the_pixels_of_a_shared_texture_are_those_of_the_page` | `CEFWEAVER_TEST_GPU_PIXELS=1`일 때만. 이 개발 기기에서는 0으로 읽혀 실패함(원인 미확인, F66). `tests/egl_dmabuf.py`로 EGL 가져오기 |
| `ApiWithoutCef` | `test_a_javascript_bridge_checks_what_it_exposes` | 이름 검사(식별자, 예약어, 중복), 호출 가능 검사, `origins`의 형식 |
| `WithCef` | `test_python_functions_are_called_from_a_page_with_json_values_and_return_promises`, `test_a_function_of_the_page_given_to_python_can_be_called_back`, `test_python_calls_a_function_of_the_page_and_evaluates_expressions`, `test_a_bridge_answers_only_the_origins_it_was_given_and_leaves_other_queries_alone`, `test_the_bridge_works_in_an_iframe_and_in_every_browser`, `test_the_bridge_works_in_a_frame_of_another_site_with_a_renderer_of_its_own` | JSON 값과 `Promise`와 예외, 페이지 함수의 콜백과 `release`, `execute_function`과 `evaluate`, 출처 제한과 응용 자신의 질의, iframe과 둘째 브라우저와 다른 사이트의 프레임(F65) |
| `ApiWithoutCef` | `test_browser_settings_default_to_cefs_choices_and_cannot_change_after_initialize` | `BrowserSettings`의 기본값, `app.browser_settings`의 교체와 형식 검사 |
| `WithCef` | `test_a_browser_with_javascript_disabled_shows_its_noscript_content`, `test_each_browser_can_have_settings_of_its_own`, `test_images_and_local_storage_can_be_turned_off`, `test_the_font_family_of_the_browser_settings_stays`, `test_the_background_color_of_the_browser_settings_wins_for_an_opaque_browser`, `test_create_browser_checks_the_settings` | JavaScript, 이미지, 로컬 저장소, 글꼴 이름, 배경색의 효과, 브라우저마다의 설정, 인자 검사(F64) |
| | `test_known_cef_issue_the_integer_font_sizes_of_the_browser_settings_do_not_last`, `test_known_cef_issue_the_default_encoding_of_the_browser_settings_is_not_used` | `expectedFailure`. 글꼴 크기가 100ms 뒤 되돌아감, `default_encoding`이 쓰이지 않음. CEF가 고치면 알려 줍니다(F64) |
| `ApiWithoutCef` | `test_the_version_is_known_before_cef_starts_and_matches_the_cef_headers` | `get_version()`이 헤더의 CEF와 Chromium 버전과 같고 `initialize()` 전에도 됨(F59) |
| `ApiWithoutCef` | `test_settings_hold_the_fields_of_the_java_cef_settings_and_check_them`, `test_settings_are_given_to_the_app_and_cannot_change_after_initialize`, `test_transparent_is_a_flag_for_the_offscreen_browser` | `Settings`의 필드 14개, 형식과 범위 검사, 오타 거부, `app.settings` 교체, `transparent` 기본값 |
| `WithCef` | `test_the_user_agent_and_its_product_are_set`, `test_the_locale_and_the_javascript_flags_are_set`, `test_the_log_file_and_severity_are_set`, `test_the_remote_debugging_port_is_open`, `test_session_cookies_survive_a_restart_only_when_asked_to`, `test_the_settings_without_a_visible_effect_are_accepted_by_cef`, `test_the_root_cache_path_holds_the_profile_data_and_the_cache_path_lies_within`, `test_the_background_color_fills_the_window_where_a_page_draws_none` | 설정의 효과를 페이지, 파일, 포트, 두 프로세스의 쿠키로 확인(F58). 효과가 안 보이는 필드는 시작만 확인 |
| `WithCef` | `test_an_offscreen_browser_needs_no_display_server_with_the_headless_platform` | `DISPLAY` 없이 `headless`로 오프스크린이 그리고 스크립트를 실행하고 정상 종료(F61) |
| `WithCef` | `test_an_offscreen_page_is_transparent_unless_told_otherwise`, `test_the_background_color_shows_where_an_opaque_page_draws_none` | `transparent`가 투명(0,0,0,0)과 흰색, `background_color`가 초록(F58) |
| `WithCef` | `test_a_korean_composition_reports_the_character_bounds_and_draws_its_underline` | `ㄱ`, `가`, `각` 조합의 `compositionupdate`, 글자 경계의 개수와 위치, 밑줄의 두께와 모양이 픽셀로 다름, 확정한 값(F56) |
| `WithCef` | `test_a_cross_site_iframe_loads_and_its_queries_reach_the_handler`, `test_a_cross_site_iframe_of_added_resources_loads_and_asks` | 서로 다른 사이트의 iframe(로컬 서버 둘, `add_resource`의 두 호스트)이 JS 바인딩과 라우터가 켜진 채 로드되고, 자식 프레임의 `report()`와 질의가 닿음(F57). `execute_javascript`는 로딩 중이면 `False`라서 준비를 기다린 뒤 보냄 |
| `WithCef` | `test_keys_beyond_a_letter_edit_and_move_in_an_offscreen_input`, `test_a_touch_reaches_the_page_as_a_touch_event`, `test_an_ime_composition_becomes_text_in_an_offscreen_input`, `test_the_popup_of_a_select_is_drawn_as_a_second_element` | 편집 키와 수정자와 한글, 터치 이벤트, IME 조합과 확정, `<select>` 팝업의 표시와 크기와 그리기(F55) |
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

권한 핸들러 시험 4개(`WithCef`, 가짜 장치로 `getUserMedia`, [F71](../reference/verified-findings-media.md)): 허용하면 `granted:1`과 핸들러가 받은 출처, 권한, 메인 프레임 여부, 취소하면 `denied:NotAllowedError`, `False`(기본 처리)도 거부, `enable-media-stream` 스위치를 주면 핸들러가 거부하도록 되어 있어도 허용되고 핸들러는 불리지 않음.

오디오 핸들러 시험 4개(`WithCef`, 440Hz 사인파와 `disable-audio-output`, [F72](../reference/verified-findings-media.md)): 채널마다 `memoryview`로 오는 패킷(채널 수, 프레임 수, 커지는 `pts`, 소리가 있음, 호출이 끝나면 무효), 페이지를 떠나면 정지, 앱이 정한 매개변수(48000Hz, 480프레임)를 따름, `False`로 캡처를 거절. 생성기 시험에는 `Planes`(`list[memoryview]`, `audio_channels_`) 1개가 늘었습니다.

### 2026-10-10에 더한 시험 (Views, 남은 API, 렌더러 이벤트)
`test_smoke.py`에 27개를 더했습니다(확인한 사실은 [F99~F101](../reference/verified-findings-views.md), [F102~F108](../reference/verified-findings-opened.md)).

| 묶음 | 시험이 확인하는 것 |
| --- | --- |
| Views | 클래스가 부모의 Python 하위 클래스임, 창이 도구 모음과 `BrowserView`를 가짐, 열린 Views 창을 둔 채 `shutdown()`이 브라우저를 닫음, `View.get_delegate()`와 `BrowserHost.get_client()`가 준 객체를 되돌려 줌, `get_parent_window`, 팝업 델리게이트 |
| Image | 비트맵을 담고 PNG와 JPEG를 만듦, 페이지에서 내려받음, 초기화 전에는 만들 수 없음 |
| 핸들러와 서버 | Find, Frame, 접근성 핸들러, 탐색 항목 방문, SSL 상태의 인증서, CEF 서버가 HTTP 요청에 답함, 응답 필터, 클라이언트 인증서 선택 |
| 전역 함수와 기타 | 시작 뒤의 전역 함수, `is_rtl()`은 시작 전에 거절, 출처와 환경설정 관찰, 미디어 라우터와 구성요소 갱신, 추적 파일, DevTools를 따로 연 창, 공유 메모리 메시지 |
| 앱 핸들러와 렌더러 이벤트 | `on_before_child_process_launch`, `on_register_custom_preferences`, 렌더러가 보내는 JavaScript 오류와 포커스 노드와 컨텍스트, 켜지 않으면 이벤트가 오지 않음 |

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
- 열거형: 값 읽기(마우스 버튼, 오류 코드, 평가된 시프트와 마스크), 비트 플래그 판별, 전처리 분기, 멤버 중복 없음, 생성된 `types` 패키지의 임포트, 스텁의 임포트와 `ErrorCode`, `MouseButtonType | int`
- 문자열 벡터: 라이브러리 메서드의 출력 인자(`get_frame_names`)와 핸들러의 입력(`on_favicon_url_change`)의 분류, 그 밖의 벡터가 이유와 함께 보고되는지, 표의 C 타입, 스텁의 `list[str]`. 생성된 C++ 프록시 실행 시험에도 벡터 전달이 들어 있습니다.
- `CefBrowserHost`가 범위에 있고 `Browser.get_host`로 닿는지, 구조체와 열거형 인자의 분류, 열리지 않는 메서드의 이유
- 초기화 전에 부르면 죽는 정적 함수(`NEEDS_CEF_RUNNING`)에 가드가 생성되는지, `Request.create()`에는 없는지
- 라이브러리 클래스의 Python 상속(`Window(Panel)`, `Panel(View)`): 부모가 먼저 정의되는지, 자식은 자기 메서드만 갖고 형 있는 포인터로 CEF를 부르는지, 객체가 실제 타입으로 감싸지는지. 프록시 등록부(`CwFindProxy`, `dynamic_cast` 없음)와 준 객체를 되찾는 메서드의 스텁
- 생성 파일이 최신인지, 두 번 생성한 결과가 같은지

## tests/test_ui.py: UI 어댑터 시험

`cefweaver.ui`의 시험입니다([UI 어댑터 API](../reference/ui-api.md)). 92개는 가짜 브라우저(호출을 기록)와 가짜 어댑터로 CEF 프로세스 없이 실행합니다: 마우스(위치, 수정 키, 클릭 횟수를 세는 규칙, 툴킷이 주는 횟수), 키(`RAWKEYDOWN`, `CHAR`, `KEYUP`, Ctrl이나 Alt에서의 생략, Enter와 Tab과 BackSpace의 `CHAR`), 문자와 입력기 글자, 조합, 클립보드 키(능력에 따라 가로채기와 통과), 그리기와 팝업과 커서와 선택 텍스트, 제목과 주소와 로딩, 나가는 드래그(어댑터가 없을 때의 중계, 있을 때의 `start_drag_out`)와 들어오는 드래그(단계별, `leave` 미루기, 한꺼번에 오는 드롭의 대기), 키 코드와 수정 키 상수, 위젯 기반 클래스(`BrowserWidget`의 위임과 훅), 툴킷 모듈(여섯 개의 존재, 툴킷을 임포트하지 않음, 서로 임포트하지 않음, 뷰의 비공개 속성을 쓰지 않음, `Checked:`와 `Not checked:`), 세션의 시작 대상, PNG 쓰기와 뷰의 snapshot과 프레임의 `change`, 그림 저장소(`PictureStore`: 처음, dirty rect의 행, 잘림, 크기 변경, 복사본, 팝업), 표 객체(`KeyTable`, 수정 키 표 셋, `CursorTable`), 드래그 시작 전략(`immediate`, `posted`, `on_motion`)과 데이터 없는 단계. 1개(`WithCef.test_a_browser_runs_in_the_headless_adapter`)는 `HeadlessAdapter`로 실제 브라우저를 띄워 첫 그림, 클릭, 입력, 한글 확정, 외부 드롭, 크기 변경, 정상 종료를 확인합니다(5번 연속 통과).

`WithCef`와 별개로 `Quickstarts`는 예제의 uv 환경이 있을 때 일곱 툴킷(여덟 환경, `views` 포함)의 `quickstart.py`를 실제로 실행해 첫 제목을 받고 창을 닫아 정상 종료를 확인합니다(환경이 없으면 건너뜀). `QuickstartDocs`는 README가 quickstart 파일의 코드를 그대로 싣는지, 코드가 40줄 이하인지 확인합니다.

`tests/playback_check.py`는 시험 모음이 아니라 **수동 점검 도구**입니다(실제 유튜브 영상이 재생되는지, [절차](../procedures/check-playback.md)).

## tests/test_wiki.py: 위키 점검

`llm-wiki/lint.py --quiet`를 실행해서 종료 코드가 0인지 확인합니다(시험 2개: 위키가 저장소 루트에 있는지, 점검 통과). `tests/test_docs.py`(15개)는 `docs/`의 링크, 제목, 빠른 시작 코드를 지킵니다. 링크, `sources` 경로, 색인 등재, frontmatter, 로그 형식이 깨지면 이 시험이 실패합니다. CEF나 wheel이 필요하지 않습니다.

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
