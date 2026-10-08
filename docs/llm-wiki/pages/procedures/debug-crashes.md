---
title: 충돌 조사 방법
type: procedure
sources:
  - native/cefsubprocess/cefsubprocess.cc
  - tests/test_smoke.py
  - tools/prepare.py
updated: 2026-10-08
---

# 충돌 조사 방법

CEF는 여러 프로세스로 동작해서 충돌이 하위 프로세스에서 나면 Python 쪽에는 메시지 한 줄(`*** stack smashing detected ***: terminated` 같은)만 보이기도 합니다. 이 페이지는 서브프로세스 종료 오류와 초기 JS 콜백 실패를 조사할 때 **실제로 효과가 있었던 방법**을 순서대로 적습니다. 환경은 Ubuntu 계열 Linux, GCC 15, gdb(배포판 기본)입니다.

## 1. 화면 없이 재현하기

```sh
env -u WAYLAND_DISPLAY xvfb-run -a python -P script.py
```

`ozone-platform=x11`도 지정합니다(`app.add_command_line_switch("ozone-platform", "x11")`). 그렇게 하지 않으면 Chromium이 Wayland를 골라 실제 화면에 창을 엽니다.

## 2. Chromium 로그 켜기

```python
app.add_command_line_switch("enable-logging", "stderr")
app.add_command_line_switch("v", "0")
```

로그에서 흔히 보이는 것들은 대부분 무해합니다. `GLib-GObject ... 'GtkSettings' has no property named 'gtk-modules'`, Wayland 프로토콜 버전 경고, 종료 때의 `GpuControl.CreateCommandBuffer` 오류가 그렇습니다. 오류 수와 종류를 정상 실행과 비교합니다.

## 3. 어느 프로세스가 죽는지 보기

시험 중 `ps -eo pid,ppid,args | grep cefsubprocess`로 자식 프로세스의 `--type=...`을 확인합니다. 렌더러가 목록에 없다면 렌더러가 시작하지 못했거나 죽은 것입니다. 이 방법으로 `--type=utility --utility-sub-type=unzip.mojom.Unzipper`가 종료할 때 죽는다는 것을 알았습니다.

## 4. 스택 보호 실패 위치 찾기

gdb를 쓸 수 없을 때(아래 5번) 다음 공유 라이브러리를 `LD_PRELOAD`로 모든 프로세스에 주입하면 `__stack_chk_fail`이 불릴 때 스택 주소를 출력합니다. SIGABRT 핸들러는 Chromium이 자체 핸들러로 덮어써서 호출되지 않았습니다.

```c
#define _GNU_SOURCE
#include <errno.h>
#include <execinfo.h>
#include <link.h>
#include <stdio.h>
#include <unistd.h>
static unsigned long base;
static int cb(struct dl_phdr_info *i, size_t s, void *d) { base = i->dlpi_addr; return 1; }
void __stack_chk_fail(void) {
  void *frames[40]; char buf[200];
  dl_iterate_phdr(cb, 0);
  int cnt = backtrace(frames, 40);
  int n = snprintf(buf, sizeof buf, "\n=== __stack_chk_fail pid %d exe-base 0x%lx frames:", getpid(), base);
  write(2, buf, n);
  for (int k = 0; k < cnt; k++) { n = snprintf(buf, sizeof buf, " 0x%lx", (unsigned long)frames[k]); write(2, buf, n); }
  write(2, "\n", 1);
  _exit(134);
}
```

```sh
gcc -shared -fPIC -o chkfail.so chkfail.c
LD_PRELOAD=$PWD/chkfail.so env -u WAYLAND_DISPLAY xvfb-run -a python -P script.py 2> out.log
```

`backtrace_symbols_fd`는 Chromium이 `argv`를 바꿔서 실행 파일 이름 대신 명령줄이 찍히므로, 주소에서 실행 파일의 로드 기준 주소(`exe-base`)를 빼서 `nm -n -C cefsubprocess`의 심볼과 비교했습니다. 이렇게 오류가 `main`의 끝(`sub %fs:0x28` 직후의 `jne`)에서 나는 것을 확인했습니다(`objdump -d -C`).

## 5. 환경에서 쓸 수 없었던 방법

- **gdb**: 이 환경의 gdb는 멀티 프로세스를 추적하면 `A fatal error internal to GDB has been detected`로 스스로 종료했고, 그때 `/var/crash`에 372MB 크기의 크래시 덤프가 생겼습니다(지웠습니다). `--renderer-cmd-prefix="gdb ..."`로 렌더러만 gdb 안에서 실행하는 방법도 같은 이유로 쓸 수 없었습니다.
- **apport**: 패키지로 설치되지 않은 바이너리(`cefsubprocess`)의 충돌 보고서는 만들지 않습니다.

## 6. 순정과 비교하기

문제가 우리 코드 때문인지 CEF나 환경 때문인지는 CEF 배포본의 `cefsimple`을 같은 환경에서 빌드해서 비교하면 알 수 있습니다.

```sh
cmake -S build/native/cef -B /tmp/stock -DCMAKE_BUILD_TYPE=Release
make -C /tmp/stock -j12 cefsimple
```

스택 보호 오류는 순정에는 없었고 우리 `main`에만 있었습니다. 순정 `main`의 `%fs:0x28` 검사는 0개였고(`objdump`), 우리 `main`에는 있었습니다. `__attribute__((no_stack_protector))`를 붙이자 같은 시험 3회에서 0건이 되었습니다([cefsubprocess 실행 파일](../components/native-cefsubprocess.md)).

## 7. 최소 시나리오로 줄이기

시험 파일의 `run_cef()`처럼 짧은 스크립트로 문제를 줄이고, 조건을 하나씩 바꿉니다(바인딩 있음 또는 없음, 초기 URL, 대기 시간). 바인딩 없는 페이지에서도 서브프로세스 오류가 났다는 것이 "바인딩 전달 오류"와 "종료 경로 오류"가 서로 다른 문제임을 알려 주었습니다.

## 관련 페이지

- [시험 실행하기](run-tests.md)
- [실험으로 확인한 사실](../reference/verified-findings.md)
- [프로세스 모델과 스레드](../concepts/process-model-and-threads.md)
