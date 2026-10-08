---
title: 시험 실행하기
type: procedure
sources:
  - CLAUDE.md
  - tests/test_smoke.py
  - tests/test_generator.py
updated: 2026-10-08
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

기대 결과는 `Ran 25 tests ... OK`(약 3.6초, 건너뛴 시험 없음)입니다. 실행에는 세 가지가 중요합니다.

1. **`-P`가 필수입니다.** 저장소 루트에서 `-P` 없이 실행하면 소스 트리의 `cefweaver/`(확장 모듈이 없음)가 설치된 wheel을 가려서 `import cefweaver`가 실패하고, CEF 시험 34개가 **건너뛰어진 채 `OK (skipped=11)`로 끝납니다.** 성공처럼 보이므로 `Ran 24 tests` 뒤에 `skipped`가 있는지 반드시 봅니다. 이 오류가 `CLAUDE.md`와 시험 파일의 안내에 있었고 고쳤습니다.
2. **가상 X 서버(`xvfb-run`)와 `env -u WAYLAND_DISPLAY`**: 시험이 실제 화면에 창을 열지 않게 합니다. Wayland 세션에서는 Chromium이 `WAYLAND_DISPLAY`를 보고 실제 화면에 창을 엽니다. 시험은 `DISPLAY`가 없거나 `WAYLAND_DISPLAY`가 있으면 CEF 시험을 건너뛰도록 되어 있어서, 건너뛴 시험이 있다면 환경부터 확인합니다.
3. **설치된 wheel을 대상으로 합니다.** wheel을 새로 만들었다면 `--reinstall`로 다시 설치합니다.

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

- 메시지의 `TimeoutError: timed out waiting for ...`는 시험이 기다린 대상이 오지 않았다는 뜻입니다. 출력의 끝 3,000자가 함께 나옵니다.
- `stack smashing detected`가 stderr에 있으면 서브프로세스가 비정상 종료한 것입니다([충돌 조사 방법](debug-crashes.md)).
- `test_generated_files_are_up_to_date`가 실패하면 `python tools/gen/generate.py`로 생성 파일을 갱신하고 변경을 확인합니다.

## 관련 페이지

- [시험](../components/tests.md)
- [충돌 조사 방법](debug-crashes.md)
- [빌드와 설치](build-and-install.md)
