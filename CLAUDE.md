# CLAUDE.md

이 문서는 이 저장소에서 작업하는 Claude Code에 주는 지침입니다.

## 코드 기록은 각 프로젝트의 llm-wiki를 우선합니다

다른 프로젝트의 코드나 동작을 조사할 때, 해당 프로젝트의 `docs/llm-wiki/`를 가장 먼저 참조합니다. 소스를 직접 검색하기 전에 위키에서 관련 페이지를 찾고, 위키가 가리키는 원본 파일(각 페이지 frontmatter의 `sources`)을 확인하는 순서로 진행합니다.

| 프로젝트 | llm-wiki 위치 |
| --- | --- |
| cefpython | `/home/jiho/cef_framework/cefpython/docs/llm-wiki/` |
| java-cef | `/home/jiho/cef_framework/java-cef/docs/llm-wiki/` |
| CEF (cef_origin) | `/home/jiho/cef_framework/cef_origin/docs/llm-wiki/` |

참조 방법은 다음과 같습니다.

1. 위키의 `index.md`에서 관련 페이지를 찾습니다. 위키의 구조와 규칙은 `SCHEMA.md`, 안내는 `README.md`에 있습니다.
2. 페이지의 `sources`에 적힌 원본 파일을 확인해서 위키 내용이 현재 소스와 맞는지 검증합니다.
3. 위키에 없는 내용은 소스에서 직접 확인합니다.
4. 위키와 원본이 다르면 원본을 따르고, 차이를 사용자에게 알립니다. 각 위키의 `README.md`도 같은 원칙을 정하고 있습니다.

이 저장소(cefweaver)에는 아직 llm-wiki가 없습니다.

## 빌드와 시험

```sh
python tools/prepare.py          # CEF 확보, 네이티브 빌드, 런타임 스테이징 (Linux)
uv build --wheel                 # Cython 확장 빌드 (인자 없는 `uv build`는 sdist 단계에서 실패)
env -u WAYLAND_DISPLAY xvfb-run -a python -m unittest discover -s tests -v
```

- 시험은 설치된 wheel을 대상으로 하며, 가상 X 서버에서 실행해야 합니다. Wayland 환경에서는 Chromium이 실제 화면에 창을 열 수 있습니다.
- 지원 플랫폼은 Linux x86_64입니다. Windows는 미검증이고 macOS는 지원하지 않습니다.

## 시험 작성 원칙

java-cef의 시험(`java/tests/junittests/`, 위키의 `run-and-test.md`)을 참고해서 정한 원칙입니다.

- **조건을 기다립니다.** 고정 시간만큼 기다리지 않고, 기다리는 사건을 `wait_until(app, 조건, "설명")`으로 지정합니다. 시간 제한은 상한일 뿐이며, 초과하면 무엇을 기다렸는지 밝히는 `TimeoutError`로 실패합니다. java-cef의 `awaitCompletion()`(`CountDownLatch`)에 해당합니다.
- **CEF를 띄우는 시험은 프로세스를 분리합니다.** CEF는 프로세스당 한 번만 초기화할 수 있습니다. java-cef는 `TestSetupExtension`으로 JVM 하나에서 CEF를 공유하지만, 우리는 한 시험의 크래시가 다른 시험을 막지 않도록 시험마다 새 프로세스에서 실행합니다. 시험이 많아져 비용이 커지면 공유 방식을 검토합니다.
- **외부 네트워크를 쓰지 않습니다.** 지금은 `data:` URL을 씁니다. java-cef처럼 가짜 URL과 리소스 핸들러(`addResource`)로 응답을 주는 방식은 C++ 래퍼에 해당 API가 생긴 뒤에 도입합니다.
- **정상 종료까지 확인합니다.** 종료 코드가 0이고 stderr에 `stack smashing`이 없어야 합니다(서브프로세스 종료 결함의 회귀 방지).
