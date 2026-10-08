---
title: 실험으로 확인한 사실 (F36부터)
type: reference
sources:
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/cef_wrapper_app.cc
  - tools/gen/typesys.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 실험으로 확인한 사실 (F36부터)

[실험으로 확인한 사실](verified-findings.md)(F1~F14)과 [API 계층의 확인](verified-findings-api.md)(F15~F35)에 이어지는 기록입니다. 페이지가 200줄을 넘지 않게 나누었습니다.

## F36. 명령줄 스위치는 자식 프로세스에 전달되지 않는다

- **방법**: `add_command_line_switch`로 `cefweaver-custom-switch=abc`, `disable-gpu`, `site-per-process`를 주고 실행 중인 프로세스들의 명령줄(`ps -eww`)을 비교했습니다.
- **결과**: 세 스위치 모두 `--type=renderer`, `gpu-process`, `utility`, `zygote` 프로세스의 명령줄에 **없었습니다.** 반면 `--ozone-platform=x11`은 자식에게 있었는데, Chromium이 스스로 전달하는 스위치이기 때문으로 보입니다(이유는 확인하지 않음). 그래서 `add_command_line_switch`의 스위치는 브라우저 프로세스에서만 읽힌다고 봐야 합니다. 자식 프로세스에 필요한 스위치는 `OnBeforeChildProcessLaunch`로 붙여야 합니다(메시지 라우터가 이렇게 합니다, F34).
- **영향**: 이전의 "자식 프로세스가 물려받습니다"라는 서술(`native-library-api.md`, `native-handlers.md`, `cef_wrapper_app.cc`의 주석)이 틀려서 고쳤습니다. 스위치를 자식에게도 보내는 옵션은 **만들지 않기로 했습니다**: java-cef도 같은 한계이고 사용자가 "java-cef만큼만" 가기로 했습니다(아래 비교와 [설계 결정 기록](design-decisions.md)).
- **java-cef와의 비교**(소스 확인, 실행하지는 않음): 스위치를 주는 길은 `CefApp.getInstance(args, settings)`의 `args`와 `CefAppHandler.onBeforeCommandLineProcessing`뿐이고, 그 훅은 `process_type`이 비었을 때(브라우저 프로세스)만 Java로 전달됩니다(`client_app.cpp:34`). `OnBeforeChildProcessLaunch`는 `native/`에 없습니다. 자식에게 값을 보낼 때는 스위치 대신 `extra_info`(라우터 설정), 프로세스 메시지(`AddMessageRouter`), 부모 PID 이름의 임시 파일(커스텀 스킴)을 씁니다.

## F37. 교차 사이트 iframe이 로드되지 않는다

- **방법**: `add_resource`로 `http://a.test/main.html`(iframe 포함)과 자식 페이지를 두 호스트에 제공하고 `LoadHandler`로 관찰했습니다.
- **결과**: 같은 사이트(`a.test`)의 iframe은 로드되고(`load-end` 200, `iframe-onload`), 다른 사이트(`b.test`)의 iframe은 오류도 로드 완료도 없이 멈춥니다. `site-per-process` 유무와 질의 핸들러 유무와 관계없이 같았고, `b.test`를 메인 프레임으로 여는 것은 정상이었습니다.
- **미확인**: 원인(두 번째 호스트의 스킴 핸들러, 프로세스 전환, CEF 문제 등)과 cefsimple에서도 같은지는 조사하지 않았습니다. 그래서 사이트 격리로 프로세스가 갈리는 프레임에서 메시지 라우터가 동작하는지는 **확인하지 못했습니다.**

## F38. 오프스크린 렌더링

- **방법**: `offscreen = True`와 `RenderHandler`로 빨간 페이지를 그리고, 크기 변경, 마우스 클릭, 팝업을 시험했습니다.
- **결과**:
  - `on_paint`가 `PaintElementType.VIEW`, 200x100, 길이 80000(`200*100*4`)의 **읽기 전용** `memoryview`를 받고 첫 픽셀이 BGRA의 빨강(`00 00 ff ff`)입니다. `dirty_rects`는 `Rect`의 목록이고 화면 안입니다. 호출이 끝난 뒤 뷰를 쓰면 `ValueError`입니다. `get_host().is_window_rendering_disabled()`는 `True`.
  - `get_view_rect`가 돌려준 `Rect`(핸들러의 **구조체 출력**)가 CEF에 전달됩니다. 크기를 바꾸고 `was_resized()`를 부르면 `320x240` 프레임이 옵니다. 이로써 구조체 출력 경로를 Python 핸들러까지 확인했습니다([알려진 제약과 미검증 항목](known-constraints.md)).
  - `send_mouse_click_event`가 오프스크린 페이지의 `onclick`에 닿습니다(입력은 준비 전에 버려지므로 다시 보냄, 기존 규칙).
  - `window.open`은 `null`(막힘)이고 브라우저는 하나뿐입니다.
- **발견(결함, 수정)**: `shutdown()`이 `SIGSEGV`로 죽었습니다. 창이 없는 브라우저는 `CloseBrowser(true)` 안에서 `OnBeforeClose`가 바로 실행되어 `browser_list_`에서 항목이 지워지는데, `CloseAllBrowsers`가 같은 목록을 순회하고 있어 반복자가 무효가 되었습니다. 복사본을 순회하도록 고쳤습니다(창 있는 브라우저는 닫기가 비동기라 드러나지 않았음).
- **영향**: 오프스크린 렌더링이 열렸습니다([오프스크린 렌더링](offscreen-rendering.md)).

## F39. 구조체 종류의 확대 (키보드, 화면 정보)

- **방법**: `size` 머리와 열거형, `char16_t` 필드가 있는 구조체를 열고 오프스크린 브라우저로 시험했습니다.
- **결과**:
  - `KeyEvent`(`RAWKEYDOWN`, `CHAR`, `KEYUP`)를 `send_key_event`로 보내자 입력란에 `a`가 들어가고 페이지의 `keydown`이 `key == "a"`를 받았습니다. 잘못된 인자(`"a"`)는 `TypeError`입니다.
  - `get_screen_info`가 `(True, ScreenInfo(2.0, ...))`를 돌려주면 페이지의 `window.devicePixelRatio`가 2가 되고 `on_paint`의 크기가 400x200, 길이 `400*200*4`입니다(핸들러의 구조체 출력, 중첩 구조체 `rect`).
  - `send_touch_event`(구조체에 열거형 둘)와 `ime_set_composition`(`CompositionUnderline`의 벡터, 중첩 `Range`, 열거형 `style`)은 호출이 받아들여지고 정상 종료합니다. 결과는 시험하지 않았습니다.
- **발견**: `char16_t`는 Cython이 알지 못하는 타입이라 `cdef extern from *: ctypedef unsigned short char16_t`로 알려 주었습니다.
- **영향**: 구조체 15개가 공개되고 보고서의 타입 지원이 89%에서 90%로 늘었습니다([오프스크린 렌더링](offscreen-rendering.md)).

## F40. 바이트열 입출력 (BinaryValue)

- **방법**: `BinaryValue.create(bytes)`와 `get_data(size, offset)`를 CEF 없이, 그리고 프로세스 메시지로 렌더러를 거쳐 시험했습니다.
- **결과**:
  - `bytes`, `bytearray`, `memoryview`를 받아 복사하고, `get_data`는 오프셋과 남은 길이를 지켜 `bytes`를 돌려줍니다(요청이 더 크면 남은 만큼, 끝이면 `b""`). `str`, `int`, `list`, `None`은 `TypeError`, 음수 크기는 `OverflowError`.
  - 0부터 255까지 모든 바이트가 렌더러를 거쳐 그대로 돌아옵니다.
  - `create(b"")`는 `None`입니다. CEF의 `CefBinaryValue::Create`가 빈 데이터에 `nullptr`을 돌려줍니다(`cef_origin/libcef/common/values_impl.cc:488-494`). 리스트에 `set_binary`로 넣은 값은 리스트가 소유하므로 원래 객체는 무효가 됩니다(`copy()`가 `None`, CEF의 문서대로).
- **발견**: `nogil` 안에서는 Python 객체를 `char*`로 바꿀 수 없어 포인터를 `nogil` 앞에서 꺼냅니다.
- **영향**: 열지 못했던 `BinaryValue.create`와 `get_data`가 열렸습니다. `get_raw_data`는 일부러 열지 않았습니다([알려진 제약과 미검증 항목](known-constraints.md)).

## F41. 포커스, JS 대화상자, 파일 대화상자, 다운로드 핸들러

- **방법**: 오프스크린 브라우저에서 핸들러를 달고 각 이벤트를 일으켜 보았습니다.
- **결과**:
  - `set_focus(True)`가 `on_set_focus(browser, source)`(`FocusSource` 멤버)와 `on_got_focus`로 갑니다.
  - `alert`, `confirm`, `prompt`가 `on_js_dialog(browser, origin_url, dialog_type, message_text, default_prompt_text, callback)`로 오고 `(handled, suppress_message)`를 돌려줍니다. `callback.continue_(success, user_input)`의 답이 페이지에 가서 `confirm`은 참/거짓, `prompt`는 `"typed"`가 됩니다.
  - 파일 입력을 마우스로 누르면 `on_file_dialog(browser, mode, title, default_file_path, accept_filters, accept_extensions, accept_descriptions, callback)`(`FileDialogMode.OPEN`)이 오고, `callback.continue_([path])`의 파일이 `input.files`에 들어갑니다.
  - `Content-Disposition: attachment`인 응답이 `on_before_download(browser, download_item, suggested_name, callback)`(`suggested_name == "named.txt"`)으로 오고, `callback.continue_(path, False)`의 경로에 10바이트가 저장되며 `on_download_updated`가 `is_complete()`와 `get_received_bytes()`를 알립니다.
- **영향**: java-cef의 13개 핸들러 가운데 4개를 더해 10개가 되었습니다(키보드, 인쇄, 요청이 남음, [생성 범위와 커버리지](generated-api-coverage.md)).

## F42. 키보드와 인쇄 핸들러

- **방법**: 오프스크린 브라우저에서 키 이벤트를 보내고 `host.print()`를 불렀습니다.
- **결과**:
  - `send_key_event`로 보낸 `RAWKEYDOWN`이 `on_pre_key_event(browser, event)`로 페이지보다 먼저 오고(`KeyEvent`, `type == RAWKEYDOWN`, `windows_key_code == 65`) `(handled, is_keyboard_shortcut)`를 돌려줍니다. 오프스크린에서도 호출됩니다.
  - `host.print()`는 `on_print_start`, `on_print_settings(browser, settings, get_defaults)`(`settings`는 `PrintSettings`), `on_print_reset` 순서로 옵니다.
- **확인하지 못함**: 프린터가 없는 환경이라 Chromium이 오류를 내고(`print_error_dialog`) `on_print_dialog`, `on_print_job`은 오지 않았습니다. `get_pdf_paper_size`(구조체 반환)는 컴파일과 생성만 확인했고 CEF가 부르는 경우를 만들지 못했습니다. `on_key_event`(페이지가 처리하지 않은 키)도 단정하지 않았습니다.
- **영향**: java-cef의 13개 핸들러 가운데 12개가 되었습니다(요청이 남음).

## F43. 요청 핸들러와 리소스 요청 핸들러

- **방법**: 사용자의 `RequestHandler`를 달고 탐색과 하위 리소스를 일으켰습니다. 메시지 라우터와 함께도 시험했습니다.
- **결과**:
  - `on_before_browse(browser, frame, request, user_gesture, is_redirect)`가 `True`를 돌려주면 그 페이지는 로드되지 않습니다(시작 페이지의 `data:` URL 탐색도 이 핸들러로 옵니다).
  - `get_resource_request_handler(...)`가 `(ResourceRequestHandler, disable_default_handling)`을 돌려주면 그 핸들러의 `on_before_resource_load`가 `ReturnValue.CANCEL`로 하위 리소스(이미지)를 취소하고 페이지의 `onerror`가 불립니다. `on_resource_load_complete`가 `URLRequestStatus.SUCCESS`와 수신 바이트 수를 줍니다.
  - 라우터와 사용자의 요청 핸들러가 함께 있을 때, 사용자가 탐색을 취소(`True`)하면 열린 질의가 취소되지 않고 허용된 탐색에서만 취소됩니다.
- **확인하지 못함**: `get_auth_credentials`(`AuthCallback`)와 `on_certificate_error`는 서버가 필요해 실행하지 않았습니다. `on_render_process_terminated`, `on_open_url_from_tab`, `on_resource_redirect`, `on_resource_response`, `on_protocol_execution`도 실행하지 않았습니다. `get_cookie_access_filter`는 쿠키 구조체 때문에 생성되지 않습니다.
- **영향**: java-cef의 핸들러 13개를 모두 갖추었습니다.

## F44. 스트림과 ZIP 읽기

- **방법**: CEF를 시작하지 않고 파일, 메모리, Python 핸들러, `zipfile`로 만든 ZIP으로 시험했습니다.
- **결과**:
  - `write(b"hello")`는 5, `write(b"abcdef", 2)`는 3(항목 수)이고, 항목의 배수가 아닌 길이는 `ValueError`입니다. `read(5)`, `read(2, 2)`는 바이트열을 돌려주고 끝에서는 짧거나 `b""`입니다. `seek`, `tell`, `eof`가 맞습니다.
  - `ReadHandler`와 `WriteHandler`를 Python으로 구현해 `create_for_handler`에 주면 `read(4)`, `read(3, 2)`가 핸들러의 `read(buffer, size)`로 가고 항목 수 반환이 바이트열로 바뀌어 돌아옵니다. `write(b"1234", 2)`는 핸들러가 `(b"1234", 2)`를 받고 2를 돌려줍니다.
  - ZIP의 첫 파일을 열어 100바이트씩 읽으면 앞부분과 나머지가 맞고 끝에서 `b""`입니다. 열린 파일이 없는데 읽으면 CEF가 -1을 돌려주어 `RuntimeError`입니다.
- **영향**: 앞서 제외한 `CefStreamWriter::Write` 같은 "크기 인자가 둘인" 경우가 표로 열렸습니다([스트림과 ZIP 읽기](streams.md)).

## F45. 시간(`datetime`)과 `void*` 표

- **방법**: 시간을 돌려주는 CEF 메서드와 PostData를 시험하고, 범위 밖 핸들러까지 포함한 넓은 범위로 프록시를 컴파일했습니다.
- **결과**:
  - `ZipReader.get_file_last_modified()`가 시간대가 있는 `datetime`을 돌려주고 ZIP에 적은 2020-01-02 12:00과 하루 이내로 맞습니다. 다운로드의 `get_start_time()`은 현재 시각과 2분 안이고 `get_end_time() >= get_start_time()`입니다.
  - `PostDataElement.set_to_bytes`/`get_bytes`, `PostData`, `Request.set_post_data`/`get_post_data`가 `\x00\xff`를 포함한 바이트열을 왕복합니다.
- **발견(잠재 결함, 수정)**: 범위 밖 핸들러의 `const void*`(`DevToolsMessageObserver.on_dev_tools_message`, `ServerHandler.on_web_socket_message`, `URLRequestClient.on_download_data`, `MediaObserver`)가 const 없는 `void*`로 선언되어 있어서 범위에 넣으면 헤더와 맞지 않아 컴파일이 깨질 계획이었습니다. const를 지키고 읽기 전용 `memoryview`로 바꿨고, 범위 밖 핸들러 다섯을 넣은 넓은 범위의 프록시를 컴파일하는 시험을 더했습니다.
- **java-cef와의 비교**(소스 확인): 날짜는 `java.util.Date`로 바꾸는 한 방향이고 밀리초로 줄입니다. 스트림은 드래그 데이터의 `GetFileContents`용 `WriteHandler` 하나뿐입니다.
- **영향**: 열린 메서드가 늘었고(타입 지원 92%) `void*` 때문에 막힌 것은 일부러 제외한 9개로 줄었습니다([바이트열과 시간](bytes-and-times.md)).

## F46. java-cef가 넘기지 않는 인자의 무시 (팝업, 커서, 인증서 오류)

- **방법**: java-cef가 Java로 넘기는 인자만 Python으로 넘기고 나머지는 무시(`IGNORED_PARAMS`)하도록 하고, 창 있는 브라우저에서 `window.open`과 오프스크린에서 커서 변경을 시험했습니다.
- **결과**:
  - `on_before_popup(browser, frame, target_url, target_frame_name)`가 `True`를 돌려주면 팝업이 취소되고 `window.open`이 `null`이며, `False`면 팝업이 열립니다. 오프스크린 브라우저는 사용자 핸들러를 부르지 않고 막습니다(java-cef와 같음).
  - `on_cursor_change(browser, type)`이 `CursorType` 멤버로 옵니다(`cursor:pointer` 위에서 `HAND`).
  - `on_certificate_error(browser, cert_error, request_url, callback)`는 `ssl_info` 없이 생성됩니다(실행은 TLS 서버가 필요해 확인하지 않음).
- **발견**: 무시하는 인자도 C++ 쪽에서는 헤더와 똑같이 선언해야 해서(`CefWindowInfo&`, `bool*`, `const CefCursorInfo&`) `Ignored`가 참조, 포인터, const를 보존합니다.
- **영향**: 바닥의 격차 3개가 메워졌습니다([java-cef 동등성](java-cef-parity.md)).

## F47. 헤더 맵 (멀티맵 ↔ dict)

- **방법**: `Request`와 `Response`의 헤더 맵을 CEF 없이 왕복시켰습니다.
- **결과**: `set_header_map({...})`로 준 맵이 `get_header_map()`으로 같은 `dict`로 돌아오고, `get_header_by_name("x-token")`은 대소문자를 구분하지 않으며, `Request.set(url, method, post_data, header_map)`이 URL, 메서드, 헤더를 한꺼번에 정합니다. `None`, 튜플 목록, 숫자 값은 `TypeError` 또는 `AttributeError`입니다.
- **한계**: 헤더 이름이 여러 번 나오는 멀티맵(`Set-Cookie` 등)을 CEF에서 받으면 `dict`로 옮기며 같은 키는 마지막 값만 남습니다. java-cef의 `Map<String, String>`과 같습니다.
- **영향**: 바닥의 격차 5개가 메워졌습니다. 전 API에서 맵 때문에 막히는 메서드가 없어졌습니다.

## F48. 창 핸들

- **방법**: 창 있는 브라우저와 오프스크린 브라우저에서 `get_host().get_window_handle()`을 불렀습니다.
- **결과**: 창 있는 브라우저는 X11 창 번호(양의 정수), 오프스크린은 0입니다. Linux에서 `CefWindowHandle`은 `unsigned long`이라 `int`로 엽니다(Windows는 포인터라 따로 다룰 일이 생기면 그때 정함).
- **영향**: 바닥의 격차 1개가 메워졌습니다.

## F49. 문자열 방문자, 파일 대화상자 콜백, DevTools 관찰자

- **방법**: 오프스크린 브라우저에서 각 메서드를 일으켰습니다.
- **결과**:
  - `frame.get_source(visitor)`가 `<p id="x">hello <b>there</b></p>`가 든 HTML을, `get_text(visitor)`가 `hello there`를 `visit(string)`으로 줍니다.
  - `host.run_file_dialog(FileDialogMode.OPEN, title, 기본 경로, 필터, callback)`은 `DialogHandler.on_file_dialog`가 고른 경로를 `RunFileDialogCallback.on_file_dialog_dismissed(file_paths)`로 알립니다.
  - `host.add_dev_tools_message_observer(observer)`가 `Registration`을 돌려주고, `execute_dev_tools_method(0, "Runtime.evaluate", params)`의 메시지 번호가 `on_dev_tools_method_result(browser, message_id, success, result)`의 번호와 같으며 `result`(읽기 전용 `memoryview`의 JSON)에 `"value":3`이 들어 있습니다.
- **영향**: 바닥의 격차 7개가 메워졌습니다(`Frame` 2, `BrowserHost` 2, `DevToolsMessageObserver` 2, `Registration`은 java-cef도 메서드가 없음).

## F50. 문자열과 시간이 든 구조체, PDF 인쇄

- **방법**: `CefStructBase<Traits>` 구조체(문자열, 시간 필드)를 열고 `print_to_pdf`로 PDF를 만들었습니다.
- **결과**: `types.PdfPrintSettings(scale=1.0, paper_width=8.27, paper_height=11.69, print_background=1, page_ranges="1", margin_type=PdfPrintMarginType.DEFAULT)`를 `host.print_to_pdf(path, settings, callback)`에 주면 `%PDF`로 시작하는 파일이 생기고 `on_pdf_print_finished(path, True)`가 옵니다(오프스크린에서도 됨). `Cookie`, `RequestContextSettings`, `URLParts`, `MediaSinkDeviceInfo`, `TaskInfo`, `LinuxWindowProperties`도 같은 방식으로 공개되어 구조체가 22개가 되었습니다(`CefSettings`와 `CefBrowserSettings`는 배열이나 포인터가 있어 제외).
- **발견**: 이 구조체는 파서가 `structure`로 분류해서 이름으로 찾도록 고쳤습니다. 문자열 필드는 `CefString(&field)`로 감싸 읽고 씁니다. 모든 구조체의 필드에 기본값을 주도록 바꿔(`Rect()`가 `(0, 0, 0, 0)`) 설정 구조체를 필요한 필드만으로 만들 수 있습니다.
- **영향**: 바닥의 격차 1개가 메워졌고(`PrintToPDF`) 쿠키와 요청 컨텍스트 설정의 길이 열렸습니다.

## F51. 쿠키, 그리고 구조체 문자열 쓰기의 결함

- **방법**: 전역 쿠키 관리자로 쿠키를 설정, 방문, 삭제하고, 리소스 요청 핸들러의 쿠키 접근 필터로 `Set-Cookie` 응답과 다음 요청을 관찰했습니다.
- **결과**:
  - `CookieManager.get_global_manager(None)`, `set_cookie(url, Cookie(...), callback)`(`SetCookieCallback.on_complete(True)`), `visit_all_cookies`와 `visit_url_cookies`(`CookieVisitor.visit(cookie, count, total) -> (계속, 지우기)`; 도메인은 Chromium이 `.cookie.test`로 정규화), `delete_cookies`(`DeleteCookiesCallback.on_complete(1)`), `flush_store`(`CompletionCallback.on_complete()`)가 동작하고 삭제한 쿠키는 다시 방문하면 없습니다.
  - `Set-Cookie: token=xyz`를 주는 리소스에서 `can_save_cookie`가 `("token", "xyz")`를, 다음 요청에서 `can_send_cookie`가 `token`을 받습니다. 두 메서드는 `browser`와 `frame`이 `None`일 수 있습니다.
- **발견(결함, 수정)**: 구조체의 문자열 필드를 쓰는 코드가 값을 구조체에 쓰지 못했습니다. Cython의 `cdef CefString text = CefString(target)`은 참조가 아니라 **복사**를 만들어 쿠키 설정이 모두 `False`였습니다(이름, 값이 빈 채로 CEF에 감). 앞의 `PdfPrintSettings.page_ranges` 등도 조용히 무시되고 있었습니다. `cef_string_from_utf8`로 구조체에 직접 쓰도록 고쳤습니다.
- **영향**: 바닥의 격차 9개가 메워졌습니다(`CookieManager` 6, `CookieAccessFilter` 2, `GetCookieAccessFilter` 1).

## F52. 요청 컨텍스트, URL 요청, 인증, 리다이렉트 (로컬 HTTP 서버)

- **방법**: 시험 스크립트 안에서 `http.server`를 띄우고(`/hello`, `/auth`(기본 인증), `/redirect`) CEF가 그 서버에 요청하게 했습니다. 이전에 "서버가 필요해 확인하지 못함"으로 남겨 둔 항목을 포함합니다.
- **결과**:
  - `URLRequest.create(request, client, None)`: `on_download_data`로 `hello world`, `on_download_progress`의 (현재, 전체), `on_request_complete`에서 `get_request_status()`는 `SUCCESS`, `get_response().get_status()`는 200, `cancel()`도 동작합니다. `get_auth_credentials(is_proxy, host, port, realm, scheme, callback)`에서 `callback.continue_("user", "pass")`로 `/auth`가 `welcome user`가 됩니다. 요청의 플래그에 `UrlrequestFlags.ALLOW_STORED_CREDENTIALS`가 없으면 401이 그대로 오고 클라이언트는 묻지 않습니다.
  - 브라우저: `RequestHandler.get_auth_credentials(browser, origin_url, is_proxy, host, port, realm, scheme, callback)`가 오고 인증된 페이지가 뜹니다. `ResourceRequestHandler.on_resource_redirect(..., new_url)`이 302와 새 URL을 받고, `on_resource_response`가 `("auth", 401)`, `("auth", 200)`, `("hello", 200)`을 받습니다.
  - `RequestContext`: 전역 컨텍스트, 환경설정(`intl.accept_languages`를 `ko,en`으로 바꾸고 읽음, 없는 이름은 `(False, 오류)`), 새 컨텍스트가 동작합니다. 환경설정 메서드는 부모 클래스 `CefPreferenceManager`에 있어서 부모의 가상 메서드를 합치도록 했고, 같은 이름의 오버로드(`CreateContext` 둘)는 첫 번째만 만듭니다.
- **발견**:
  - **`disable-chrome-login-prompt`**: 이 스위치가 없으면 CEF 154는 Chrome의 로그인 창을 쓰고 클라이언트의 `GetAuthCredentials`를 부르지 않습니다(`chrome_content_browser_client_cef.cc`). 그래서 사용자의 요청 핸들러가 `get_auth_credentials`를 재정의했을 때만 `initialize()`가 이 스위치를 켭니다.
  - **입출력 인자**: `OnResourceRedirect`의 `new_url`은 CEF가 현재 값을 주고 핸들러가 바꾸는 값이라(java-cef의 `StringRef`) 출력으로만 다루면 빈 값으로 덮어써 리다이렉트가 깨집니다. Python 메서드가 `new_url`을 받고 새 값을 돌려줍니다.
- **영향**: 바닥의 격차 중 `RequestContext`(환경설정 포함), `RequestContextHandler`, `URLRequest`, `URLRequestClient`가 메워졌습니다.

## 관련 페이지

- [실험으로 확인한 사실](verified-findings.md)
- [API 계층의 확인](verified-findings-api.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [java-cef 동등성](java-cef-parity.md)
