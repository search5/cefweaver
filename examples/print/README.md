# 인쇄 (Linux, CUPS)

cefweaver로 띄운 페이지를 인쇄하는 예제입니다. Linux의 CEF에는 **인쇄 대화상자도 프린터 목록도 없으므로** 앱이 직접 처리합니다. 이 예제는 Tk로 대화상자(프린터, 용지, 방향, 부수, 선택 영역만)를 그리고 CUPS에는 `pycups`로 묻습니다.

| 파일 | 내용 |
| --- | --- |
| `printing.py` | CUPS의 프린터와 용지(`printers()`, `paper_sizes()`), 설정 채우기(`fill()`), 대화상자(`PrintDialog`), CEF의 `PrintHandler`(`Printing`), CUPS로 보내기(`send_to_cups()`), 뷰에 붙이기(`attach()`) |
| `quickstart.py` | 페이지와 `Print...` 단추가 있는 가장 작은 프로그램 |
| `smoke.py` | 가상 X 서버에서 대화상자와 작업을 구동해 점검하는 스크립트(11개). 프린터로는 아무것도 보내지 않습니다 |

## 흐름

```
Print...  ->  host.print()
  on_print_start
  on_print_settings(get_defaults=True)   앱이 기본값을 채움: 프린터 이름, DPI, 용지, 방향, 부수
  on_print_dialog(has_selection, callback)   앱의 대화상자를 띄우고 True를 돌려줌
        사용자가 Print  ->  callback.continue_(settings)       Cancel  ->  callback.cancel()
  on_print_job(document_name, pdf_file_path, callback)   CEF가 만든 PDF가 옴: 복사하거나 CUPS로 보냄
        callback.continue_()       (이 뒤에 CEF가 PDF 파일을 지웁니다)
  on_print_reset
```

핵심은 네 가지입니다.

- **`on_print_settings`에서 설정을 채워야 합니다.** `get_defaults`일 때 장치 이름이 비어 있으면 CEF가 "프린터를 사용할 수 없다"고 하며 `on_print_dialog`까지 오지 않습니다. 프린터 목록은 CEF가 주지 않으므로 CUPS에 묻습니다.
- **`disable-features=EnableOopPrintDrivers`로 CEF를 시작해야 합니다**(`printing.SWITCHES`). 프로세스 밖 인쇄가 켜져 있으면 `on_print_dialog`에서 계속한 뒤 `kFailed`로 실패하고 `on_print_job`이 오지 않습니다.
- **부수(`copies`)는 PDF에 들어가지 않습니다.** 방향, 용지, 페이지 범위, 선택 영역은 PDF에 반영됩니다. 부수와 용지는 CUPS로 보낼 때(`lp -n`, `-o media=`) 앱이 줍니다.
- **`cefweaver.ui`의 뷰에는 인쇄 핸들러가 없습니다.** `attach()`가 클라이언트의 서브클래스로 `get_print_handler`를 더합니다. 인스턴스에 속성으로 붙이면 CEF가 보지 못합니다.

## 환경 (uv)

`pycups`는 소스에서 빌드하므로 CUPS 개발 파일이 필요합니다.

```sh
sudo apt install libcups2-dev          # pycups를 빌드하는 데 필요 (Ubuntu)
# 저장소 루트에서 wheel을 만든 뒤 (CPython 3.13용)
uv build --wheel
cd examples/print
uv sync --python 3.13
```

wheel을 다시 만들었으면 `uv sync --upgrade-package cefweaver --reinstall-package cefweaver`를 실행하십시오. 프린터는 CUPS에 하나 이상 있어야 합니다(`lpstat -e`).

## 실행과 점검

```sh
uv run python quickstart.py                     # 모의 실행: PDF만 만들고 프린터로는 보내지 않음
REALLY_PRINT=1 uv run python quickstart.py      # 선택한 프린터로 lp를 실행 (용지가 나옴)
env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE xvfb-run -a -s "-screen 0 1000x640x24" uv run python smoke.py [스크린샷 디렉터리]
```

`smoke.py`가 점검하는 것: 대화상자의 기본값(A4, 세로, 1부), 프린터가 CUPS의 것인지, 선택 영역이 없으면 "선택 영역만"이 꺼져 있는지, 취소하면 작업이 없는지, A5 가로 2부로 바꾸면 PDF가 A5 가로(595 x 420 pt) 2쪽이고 선택이 전달되는지, 선택 영역이 있으면 "선택 영역만"이 켜지고 PDF가 한 쪽인지, 정상 종료. 실제 프린터로는 아무것도 보내지 않습니다.

## 알아 둘 것

- **취소와 실패를 구분할 수 없습니다.** `on_print_dialog`에서 취소하든 `kFailed`로 실패하든 앱은 `on_print_job` 없이 `on_print_reset`을 받을 뿐이고, 실패의 오류는 로그로만 나옵니다.
- **작업은 서로 독립입니다.** `host.print()`를 겹쳐 불러도 작업마다 대화상자 객체, 콜백, PDF 파일이 따로이고 어느 순서로 끝내도 됩니다. PDF는 `callback.continue_()` 뒤에 지워지므로 그 전에 복사하십시오(`Printing`이 복사해서 `job_done`에 줍니다).
- **용지 크기는 PPD에서 얻지 못했습니다.** 이 예제의 프린터(드라이버리스)의 PPD에는 용지 이름(`PageSize`)만 있고 크기(`PaperDimension`)가 없어서, 표준 이름의 크기를 `printing.KNOWN` 표로 줍니다. PPD에 크기가 있는 프린터라면 그것을 읽는 편이 낫습니다.
- **`get_pdf_paper_size`는 구현하지 않았습니다.** 일반 인쇄에서 불리지 않았고(인쇄 미리보기의 "PDF로 저장"이나 기업용 콘텐츠 분석에서만 닿는 것으로 Chromium 소스에서 읽음), 어떤 경로로도 불리는 것을 보지 못했습니다.
- **종이로 나온 결과의 내용은 확인하지 못했습니다.** 점검은 모의 실행으로 합니다. 별도의 시험에서 `on_print_job`의 PDF를 `lp`로 한 장 보내 CUPS가 작업을 받고 완료하는 것까지 확인했지만(`REALLY_PRINT=1`로 이 예제를 실행해 본 것은 아님), 종이의 내용은 사람이 봐야 합니다.
- Tk는 한 위젯에 브라우저 하나이고, 대화상자의 위치는 고정입니다(`+300+140`).
- 확인한 환경은 Linux x86_64, CPython 3.13, CEF 154입니다. CEF의 `PrintHandler`는 Linux 전용이라 macOS는 이 예제의 대상이 아닙니다(macOS에서 `host.print()`는 90초 안에 끝나지 않았습니다).
