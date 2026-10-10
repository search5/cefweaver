---
title: CEF 버전 올리기
type: procedure
sources:
  - CMakeLists.txt
  - tools/prepare.py
  - tools/gen/generate.py
  - llm-wiki/pages/reference/coverage-report.md
  - tests/test_generator.py
updated: 2026-10-10
---

# CEF 버전 올리기

기본 CEF 버전은 `CMakeLists.txt`의 `set(CEF_VERSION "...")` 한 곳에 있습니다. `tools/prepare.py`와 `tools/build_cef.py`가 이 줄을 정규식으로 읽어서 기본값으로 씁니다.

## 절차

1. **후보 고르기**: `python tools/prepare.py --list-versions`로 전체 이름을 확인합니다. 메이저 버전이 크게 바뀌면 API가 바뀌어 빌드가 깨질 수 있습니다.
2. **기본값 바꾸기**: `CMakeLists.txt`의 `CEF_VERSION`을 새 전체 이름으로 바꿉니다.
3. **CEF 확보와 네이티브 빌드**: `python tools/prepare.py`. 같은 `build/native`에서 해도 옛 버전이 고정되지 않습니다.
4. **바인딩 다시 생성**: `python tools/gen/generate.py`. 생성 파일 머리의 `Generated from CEF <버전>`이 바뀌고, 헤더의 변경(추가, 제거된 메서드와 클래스)이 생성 파일과 [커버리지 보고서](../reference/coverage-report.md)의 차이로 드러납니다. 차이를 읽어서 의도한 변화인지 확인합니다. 헤더에 `added=N`, `removed=N`이 붙은 메서드는 생성기가 API 버전(`tools/gen/model.py`의 `API_VERSION`)에 맞춰 거르므로 새 버전에서 걸러지는 메서드가 달라질 수 있습니다. 손으로 쓴 메서드(`tools/gen/extras/`)가 기대는 CEF 메서드와 `scope.py`의 `NEEDS_CEF_RUNNING` 목록도 새 헤더에 맞는지 확인합니다(다른 버전에서 확인하지 못했습니다).
5. **wheel 빌드와 시험**: `uv build --wheel`, 설치, [시험 실행하기](run-tests.md).
6. **문서 갱신**: `CMakeLists.txt`와 `README.rst`의 버전 예시, 그리고 위키에서 옛 버전 문자열을 찾아 고칩니다.

   ```sh
   grep -rn "154.0.34" README.rst CLAUDE.md llm-wiki tools --include=* | grep -v COVERAGE
   ```

7. 커밋. 생성 파일과 `CMakeLists.txt`의 변경은 같은 커밋에 넣습니다.

## 지난 번 변경에서 관찰한 것 (120.1.8에서 154.0.34로)

- 래퍼 코드(`native/`)는 **소스 수정 없이** 빌드되었습니다. 컴파일러 표준만 C++17에서 C++20(`-std=c++20`)으로 바뀌었습니다. 확장 모듈의 컴파일 인자도 이에 맞춰 `-std=c++20`입니다.
- 배포본의 파일 구성이 달라졌습니다. 120에는 `libEGL.so`, `libGLESv2.so`, `snapshot_blob.bin`이 있었고 154의 `Release/`에는 없습니다. 스테이징이 `Release/`와 `Resources/`의 모든 항목을 복사하는 방식이라 코드 수정이 필요하지 않았습니다.
- 이때 옛 `CEF_ROOT`가 CMake 캐시에 고정되어 154를 요청해도 120이 쓰이는 결함을 발견해서 고쳤습니다([CEF 확보 방식](../concepts/cef-acquisition.md)).
- 생성기는 154 헤더에서 처음 실행했으므로, **다른 버전의 헤더에서 생성이 되는지는 확인하지 못했습니다.** 파서(CEF master 복사본)가 새 헤더의 문법을 모르면 `generate.py`가 실패하거나 잘못 읽을 수 있고, 그 경우 `tools/gen/vendor/`를 새 CEF 소스에서 다시 복사합니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [CEF 확보하기](obtain-cef.md)
- [생성되는 파일](../components/generated-files.md)
- [빌드와 설치](build-and-install.md)
