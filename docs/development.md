---
title: 개발하기
---

# 개발하기

## 시험

시험은 설치된 wheel을 대상으로 하며 가상 X 서버에서 실행합니다. 저장소 루트에서 다음과 같이 실행합니다.

```sh
uv build --wheel
env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v
```

- **`-P`는 필수입니다.** 없으면 저장소 루트의 소스 `cefweaver/`가 설치된 wheel을 가려서 CEF를 쓰는 시험이 조용히 건너뛰어지고도 `OK`로 끝납니다.
- `env -u WAYLAND_DISPLAY`와 `xvfb-run`은 시험이 실제 화면에 창을 열지 않게 합니다.
- 시험에서 외부 네트워크를 쓰지 않습니다. 가짜 URL의 응답은 `app.add_resource()`로 주고, 조건은 고정 시간이 아니라 `wait_until`로 기다립니다.
- CEF를 띄우는 시험은 시험마다 새 프로세스에서 실행합니다(CEF는 프로세스당 한 번만 초기화됩니다).

툴킷 예제는 각자의 `smoke.py`로 점검합니다. 예를 들어 Qt는 다음과 같습니다.

```sh
cd examples/qt
env -u WAYLAND_DISPLAY QT_QPA_PLATFORM=xcb xvfb-run -a uv run python smoke.py
```

## 바인딩 생성기

CEF API를 손으로 옮기지 않고 CEF 헤더에서 Python 바인딩을 생성합니다(`tools/gen/`).

```sh
python tools/gen/generate.py            # 생성 파일 갱신
python tools/gen/generate.py --check    # 생성 파일이 최신인지 확인 (시험에도 들어 있습니다)
python tools/gen/generate.py --report   # 커버리지 보고서 출력
```

생성된 파일(`native/cefwrapper/generated/`, `cefweaver/cef_api.*`, `cefweaver/api/`, `cefweaver/types/`, `cefweaver/_cefweaver.pyi`)은 직접 고치지 않습니다. CEF 버전을 바꾸면 `prepare.py` 다음에 `generate.py`를 실행합니다. 이름은 PEP 8을 따릅니다(`CefResourceHandler`는 `ResourceHandler`, `GetURL`은 `get_url`).

## 영상과 소리 점검

`tests/playback_check.py`는 실제 YouTube 영상이 재생되는지, 소리가 싱크에 닿는지 확인하는 수동 도구입니다. 시험 모음에는 들어 있지 않습니다(네트워크와 YouTube에 의존합니다). `--audio`로 소리 싱크를, `--loud`로 실제 소리를 확인합니다. `--loud`는 소리가 실제로 나고 실제 화면에 창을 엽니다.

## 위키

이 저장소에는 LLM과 함께 쓰는 작업 위키가 저장소 루트의 [`llm-wiki/`](https://github.com/search5/cefweaver/tree/main/llm-wiki)에 있습니다. 구조 설명, 코드와 설계 결정, 확인한 사실(실험 기록)과 확인하지 못한 것을 담습니다. 이 사이트(`docs/`)와 달리 **게시하지 않는 내부 기록**이고, 코드를 바꾸면 같은 작업에서 맞춥니다. 점검은 `python llm-wiki/lint.py`입니다.
