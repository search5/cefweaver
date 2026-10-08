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

`unittest`로 작성한 시험이 세 파일에 25개(통합 11, 생성기 13, 위키 점검 1) 있습니다. 실행 방법은 [시험 실행하기](../procedures/run-tests.md)에 있습니다.

## tests/test_smoke.py: 설치된 wheel의 통합 시험

설치된 wheel을 대상으로 하며 소스 트리에서는 `import cefweaver`가 확장 모듈을 못 찾아 시험을 건너뜁니다.

| 클래스 | 시험 | 확인하는 것 |
| --- | --- | --- |
| `ApiWithoutCef` (CEF를 띄우지 않음) | `test_calls_before_initialize_raise` | 초기화 전의 `do_message_loop_work`, `load_url`, `execute_javascript`가 `RuntimeError` |
| | `test_binding_must_be_callable` | 호출 불가능한 객체는 `TypeError` |
| | `test_generated_names_are_public_and_pep8` | 생성된 이름의 공개 여부, `continue_`, `get_url`, `get_mime_type("html")` |
| | `test_library_objects_cannot_be_created_directly` | `Request()` 거부, `Request.create()`는 초기화 전에도 동작 |
| | `test_add_resource_needs_a_running_cef` | 초기화 전 `add_resource`는 `RuntimeError` |
| `WithCef` (실제 CEF) | `test_javascript_to_python_binding_and_shutdown` | 네 가지 값 형식(한글 포함)의 전달, 종료 후 `is_running`이 거짓 |
| | `test_zero_argument_call_and_exceptions_do_not_crash` | 인자 없는 호출, 콜백 예외가 CEF를 죽이지 않음 |
| | `test_load_url_and_execute_javascript` | 로딩 중 `False`, 준비 뒤 `True`, `load_url` 후 실행 |
| | `test_add_resource_serves_pages_without_a_network` | 가짜 URL 페이지, 하위 리소스, 300KB 본문 해시, 헤더, 404 |
| | `test_resource_handler_can_answer_later_from_another_thread` | `open`이 `(True, False)` 후 다른 스레드의 `continue_()` |
| | `test_exceptions_in_a_resource_handler_do_not_crash` | 핸들러와 팩토리의 예외가 보고되고 이후 페이지는 정상 |

## tests/test_generator.py: 생성기 시험

CEF를 실행하지 않고 헤더만 읽습니다(`build/native/cef`가 없으면 헤더 시험은 건너뜀).

- 이름 규칙: `snake_case`, 예약어 밑줄, 접두사 제거
- 타입 분류: 클래스 이름은 선언에서 얻음, 출력 인자 순서(반환값 먼저), `void*`와 크기 쌍, 열거형과 구조체 구분, 지원하지 못하는 타입의 사유, 순수 가상 감지, 기본형과 문자열
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
