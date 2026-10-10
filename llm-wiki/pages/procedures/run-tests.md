---
title: 시험 실행하기
type: procedure
sources:
  - CLAUDE.md
  - tests/test_smoke.py
  - tests/test_generator.py
  - tests/test_ui.py
updated: 2026-10-10
---

# 시험 실행하기

시험의 구성은 [시험](../components/tests.md)에 있습니다.

## 통합 시험과 생성기 시험을 한 번에

```sh
uv build --wheel --python 3.13 -o dist
uv venv --python 3.13 .venv-test
uv pip install --python .venv-test/bin/python dist/cefweaver-*.whl
env -u WAYLAND_DISPLAY xvfb-run -a .venv-test/bin/python -P -m unittest discover -s tests -v
```

기대 결과는 `OK`이고 건너뛴 시험이 없는 것입니다(`skipped`가 없어야 함). 시험 수는 2026-10-10 기준으로 정의된 시험 메서드가 `test_smoke.py` 221개, `test_generator.py` 125개, `test_ui.py` 164개, `test_docs.py` 15개, `test_wiki.py` 2개이고, 전체를 한 번에 돌린 기록은 526개입니다([F108](../reference/verified-findings-opened.md)). 이 페이지를 처음 쓸 때의 `Ran 25 tests`(약 3.6초)는 지금과 맞지 않습니다. 실행에는 세 가지가 중요합니다.

0. **실제 Wayland 화면에 창을 여는 시험은 선택 실행입니다.** `CEFWEAVER_TEST_WAYLAND=1`을 주고 Wayland 세션에서 `env -u WAYLAND_DISPLAY` 없이 실행하면 `WithCefOnWayland` 시험 2개가 실행됩니다(창이 몇 초간 화면에 뜹니다). 기본 실행에서는 건너뜁니다.
0. **실제 GPU가 필요한 공유 텍스처 시험도 선택 실행입니다.** `CEFWEAVER_TEST_GPU=1 DISPLAY=:0 env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE python -P -m unittest discover -s tests -p test_smoke.py -k arrives_as_dmabuf` (오프스크린이라 창은 열리지 않지만 실제 디스플레이에 연결하므로 허락을 받은 뒤에 실행합니다). 스위치는 `CEFWEAVER_TEST_GPU_SWITCHES`로 바꿉니다. 자세한 것은 [공유 텍스처](../reference/shared-textures.md).
1. **`-P`가 필수입니다.** 저장소 루트에서 `-P` 없이 실행하면 소스 트리의 `cefweaver/`(확장 모듈이 없음)가 설치된 wheel을 가려서 `import cefweaver`가 실패하고, CEF 시험이 **건너뛰어진 채 `OK (skipped=...)`로 끝납니다**(처음 확인했을 때는 57개, `OK (skipped=11)`). 성공처럼 보이므로 `Ran ... tests` 뒤에 `skipped`가 있는지 반드시 봅니다. 이 오류가 `CLAUDE.md`와 시험 파일의 안내에 있었고 고쳤습니다.
2. **가상 X 서버(`xvfb-run`)와 `env -u WAYLAND_DISPLAY`**: 시험이 실제 화면에 창을 열지 않게 합니다. Wayland 세션에서는 Chromium이 `WAYLAND_DISPLAY`를 보고 실제 화면에 창을 엽니다. 시험은 `DISPLAY`가 없거나 `WAYLAND_DISPLAY`가 있으면 CEF 시험을 건너뛰도록 되어 있어서, 건너뛴 시험이 있다면 환경부터 확인합니다.
3. **설치된 wheel을 대상으로 합니다.** wheel을 새로 만들었다면 `--reinstall`로 다시 설치합니다.

## macOS

macOS에는 가상 디스플레이가 없어서 `xvfb-run`과 `env -u WAYLAND_DISPLAY` 없이 그대로 실행합니다.

```sh
uv build --wheel -o dist
uv venv .venv-test && uv pip install --python .venv-test/bin/python dist/cefweaver-*.whl
.venv-test/bin/python -P -m unittest discover -s tests -v
```

- **창을 여는 시험(F81을 잴 때 약 41개)은 사용자 화면에 창이 열립니다.** 오프스크린 시험은 열지 않습니다. 창이 거슬리면 `-k`로 이름을 골라 실행하세요. 전체가 약 3분에 끝납니다(F81을 잴 때 `test_smoke.py`는 194개였고 지금은 221개라 시간은 다시 재지 못했습니다, [F81](../reference/verified-findings-macos.md)).
- 건너뛰는 시험이 있습니다(libX11, `xwininfo`, 인쇄, 호스트에 직접 키 이벤트를 보내는 시험, Wayland, GPU). 이유는 시험의 `skipIf` 문구와 [F82](../reference/verified-findings-macos.md)에 있습니다.
- **Cocoa 창 시험은 선택 실행입니다**(`WithCefInACocoaView`, 창이 잠깐 뜸). PyObjC가 설치된 환경에서 `CEFWEAVER_TEST_COCOA=1`을 주면 실행합니다.
- `test_wiki.py`가 다른 컴퓨터의 경로(`/home/jiho/...`) 링크 때문에 실패할 수 있습니다.

## 일부만 실행

```sh
# 생성기 시험(CEF 헤더만 필요, wheel 불필요)
python -P -m unittest discover -s tests -p "test_generator.py" -v

# 한 시험
env -u WAYLAND_DISPLAY xvfb-run -a .venv-test/bin/python -P -m unittest tests.test_smoke.WithCef.test_add_resource_serves_pages_without_a_network -v
```

생성기 시험 가운데 헤더가 필요한 것은 `build/native/cef`가 없으면 건너뜁니다(`python tools/prepare.py`로 만듭니다).

## 여러 Python 버전

버전마다 wheel을 만들고 새 가상 환경에 설치해서 같은 명령을 실행합니다. 3.11, 3.12, 3.13, 3.14에서 통합과 생성기 시험 24개가 모두 통과했습니다(위키 점검 시험을 추가하기 전의 측정이며, 추가한 뒤에는 3.13에서 25개를 확인했습니다).

```sh
for v in 3.11 3.12 3.13 3.14; do
  uv build --wheel --python $v -o dist-$v
  uv venv --python $v .venv-$v && uv pip install --python .venv-$v/bin/python dist-$v/*.whl
  env -u WAYLAND_DISPLAY xvfb-run -a .venv-$v/bin/python -P -m unittest discover -s tests
done
```

## 실패했을 때

- 간헐적으로 실패하는 시험이 알려져 있습니다(`test_a_second_offscreen_browser_paints_on_its_own_and_the_first_is_unaffected`는 20회 중 2회, 철자 메뉴 시험은 전체 실행에서 1회). 단독으로 다시 돌려 보고, 원인은 [F108](../reference/verified-findings-opened.md)에 있습니다.
- 열린 창이 있는 채 `app.shutdown()`을 부르는 시험은 지금 통과합니다(`shutdown()`이 남은 브라우저를 먼저 닫음, [F99](../reference/verified-findings-views.md)). 종료 때 세그멘테이션 오류(139)가 나면 이 경로를 먼저 의심합니다.

- 메시지의 `TimeoutError: timed out waiting for ...`는 시험이 기다린 대상이 오지 않았다는 뜻입니다. 출력의 끝 3,000자가 함께 나옵니다.
- `stack smashing detected`가 stderr에 있으면 서브프로세스가 비정상 종료한 것입니다([충돌 조사 방법](debug-crashes.md)).
- `test_generated_files_are_up_to_date`가 실패하면 `python tools/gen/generate.py`로 생성 파일을 갱신하고 변경을 확인합니다.

## 관련 페이지

- [시험](../components/tests.md)
- [충돌 조사 방법](debug-crashes.md)
- [빌드와 설치](build-and-install.md)
