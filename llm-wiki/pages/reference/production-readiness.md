---
title: 프로덕션 배포 가능성 (최소 안정 조건 시험)
type: reference
sources:
  - tools/stability/soak.py
  - tools/stability/scenarios.py
  - tools/stability/cycle.py
  - tools/stability/cycle.sh
  - tools/stability/common.py
  - native/cefwrapper/library.cpp
  - CLAUDE.md
updated: 2026-10-13
---

# 프로덕션 배포 가능성 (최소 안정 조건 시험)

cefweaver를 프로덕션에 배포해도 되는지 묻는 요청에 따라, 최소한의 안정 조건을 정하고 실제로 돌려 본 결과입니다. 스크립트는 `tools/stability/`에 있고 다시 돌릴 수 있습니다.

**결론**: 신뢰하는 콘텐츠(자신이 만든 페이지나 내부 시스템)를 보여 주는 용도로, Linux x86_64에서는 아래 조건에서 최소 안정 조건을 통과했습니다. 신뢰할 수 없는 웹 콘텐츠를 여는 용도, 몇 시간 이상 사람 없이 도는 용도, Windows와 macOS는 이 시험으로 허락할 수 없습니다. 이유는 "통과하지 못한 것과 시험하지 못한 것"에 있습니다. 프로젝트 자신도 개발 중이라고 밝힙니다([readme 요약](../summaries/readme-and-claude-md.md)).

## 시험 환경

2026-10-13, Linux x86_64, 가상 X 서버(`xvfb-run`, `WAYLAND_DISPLAY` 해제), CEF 154, 이 저장소의 소스로 만든 `cp311-abi3` wheel을 Python 3.12 가상 환경에 설치해 `python -P`로 실행했습니다. 브라우저는 `ui.Session`과 `HeadlessAdapter`(오프스크린)입니다. 창 모드, GPU 가속, 실제 화면, 네트워크 서비스는 쓰지 않았습니다.

## 최소 안정 조건과 결과

| 조건 | 시험 | 결과 |
| --- | --- | --- |
| 기존 시험 모음 통과 | `python -P -m unittest discover -s tests` | 549개, 144초, 통과(건너뜀 9, 예상된 실패 3) |
| 시작에서 종료까지 반복해도 실패가 없다 | `cycle.sh`: 새 프로세스에서 시작, 브리지 호출, `shutdown`을 반복 | 180회 모두 종료 코드 0이고 stderr에 `stack smashing`, `Segmentation`, `Traceback`이 없었습니다. 남는 `cefsubprocess`는 마지막 100회에서 0개였습니다(앞 80회는 점검 조건이 잘못되어 이 항목은 무효입니다). |
| 오래 돌려도 자원이 늘지 않는다 | `soak.py 1200`: 20분 동안 페이지 4,610번 로드, Python 호출 4,610번, JavaScript 평가 4,609번 | 오류 0, 종료 코드 0. 파일 기술자 334에서 349, 스레드 124에서 129로 거의 변하지 않았고 프로세스 수는 8로 일정했습니다. **RSS는 1,037 MB에서 1,191 MB로 늘었습니다**(+154 MB, 분당 약 6 MB, 20분 안에 멈추지 않았습니다). |
| 렌더러가 죽어도 앱은 산다 | 페이지가 `chrome://crash`로 렌더러를 실제로 죽임 | 앱은 계속 돌았고, 다음 페이지가 로드되고 브리지 호출이 응답했으며 정상 종료했습니다. |
| Python 쪽 예외가 앱을 죽이지 않는다 | 브리지 함수가 예외를 발생, `on_title` 훅이 `ZeroDivisionError` | 브리지의 `Promise`가 거부되었고(`Error: ValueError: ...`) 훅의 예외는 `sys.excepthook`으로 보고되었으며 앱은 계속 동작했습니다. |
| 큰 값을 주고받는다 | 8 MB 문자열을 페이지에서 Python으로 보냈다 되돌림 | 0.22초, 값 유실 없음 |
| 네트워크 실패에 멈추지 않는다 | 풀리지 않는 호스트, 아무도 듣지 않는 포트, 응답하지 않는 서버를 로드 중에 `shutdown` | 로드 실패 후 다음 페이지가 정상이었고, 로드 중 `shutdown`은 0.05초에 끝났습니다. |
| 부모가 죽으면 자식도 사라진다 | 부모를 `SIGKILL` | 5초 안에 `cefsubprocess`가 하나도 남지 않았습니다. |
| 종료 신호를 처리할 수 있다 | `SIGTERM` 핸들러에서 `session.shutdown` | 정상 종료했습니다. |
| 가만히 있을 때 CPU를 쓰지 않는다 | 로드가 끝난 뒤 30초 동안 프로세스 트리의 CPU 시간 | 0.21초(약 0.7%) |

## 통과하지 못한 것과 시험하지 못한 것

- **샌드박스가 없습니다.** 렌더러 프로세스의 `/proc/<pid>/status`에서 `Seccomp: 0`이고 같은 사용자 네임스페이스에 있으며, 명령줄에 `--no-sandbox`가 붙어 있습니다(`native/cefwrapper/library.cpp`의 `settings.no_sandbox = true`). 렌더러의 취약점이 곧 앱 프로세스 권한의 취약점이 될 수 있으므로, 외부 사이트나 사용자가 올린 콘텐츠를 여는 용도에는 쓰지 마십시오. 샌드박스를 켜는 방법은 이 저장소에서 시험하지 않았습니다.
- **메모리가 계속 늘었습니다.** 20분에 +154 MB입니다. 원인(Chromium의 캐시인지, 누수인지)은 확인하지 못했고 더 긴 시험도 하지 않았습니다. 며칠 이상 도는 상시 서비스에는 시험이 부족합니다. 우회책으로 주기적으로 프로세스를 다시 시작하는 설계를 쓸 수 있으나 그 효과는 확인하지 않았습니다.
- **한 브라우저가 약 1 GB를 씁니다.** 프로세스 8개의 RSS 합계입니다(복잡한 페이지를 로드한 상태).
- **다른 스레드에서 호출하면 어떻게 되는지**: 한 번 `load_url`을 다른 스레드에서 불렀을 때 예외 없이 이동했지만, 지원되는 방식이 아닙니다. CEF 호출은 `initialize()`를 부른 스레드에서, 다른 스레드에서는 `adapter.post()`로 넘기십시오.
- **시험하지 않은 것**: 창 모드, GPU 가속 켠 상태(영상 재생은 X11에서 일부 기계가 실패합니다. [known-constraints](known-constraints.md)), Windows와 macOS, 여러 브라우저, 며칠 단위 실행, 동시 부하, 실제 네트워크 서비스, 디스크 캐시의 크기와 정리, 메모리 부족 상황.
- 한 프로세스에서 CEF는 한 번만 초기화됩니다. `shutdown` 뒤 재시작이 필요한 설계(예: 워커 풀)에서는 프로세스를 새로 띄워야 합니다.
- 배포 측면: PyPI 업로드 한도 문제로 첫 배포가 막혀 있고, 버전은 0.1.0입니다.

## 다시 돌리기

```sh
pip install <wheel>                       # 설치된 wheel을 시험합니다 (-P 필수)
tools/stability/cycle.sh 100              # 시작과 종료 반복
PYTHONPATH=tools/stability xvfb-run -a python -P tools/stability/soak.py 1200
PYTHONPATH=tools/stability xvfb-run -a python -P tools/stability/scenarios.py renderer_crash
```

시나리오 이름은 `scenarios.py` 머리말에 있습니다. `soak.py`는 15초마다 프로세스 트리의 RSS, 파일 기술자, 스레드 수를 JSON 한 줄로 찍습니다. 다른 CEF 프로그램이 같이 돌면 `cefsubprocess` 개수 점검이 무의미해집니다.

## 관련 페이지

- [알려진 제약과 미검증 항목](known-constraints.md)
- [프로세스 모델과 스레드](../concepts/process-model-and-threads.md)
- [시험 실행하기](../procedures/run-tests.md)
