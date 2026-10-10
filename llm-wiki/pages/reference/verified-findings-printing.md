---
title: 실행해서 확인한 인쇄 (F94)
type: reference
sources:
  - cefweaver/_cefweaver.pyi
  - native/cefwrapper/cef_wrapper_client_handler.h
  - tests/test_smoke.py
  - examples/print/printing.py
  - examples/print/smoke.py
  - examples/print/quickstart.py
updated: 2026-10-10
---

# 실행해서 확인한 인쇄 (F94)

Linux에서 `PrintHandler`와 CUPS로 인쇄하는 흐름을 이 컴퓨터(CUPS와 프린터가 있음)에서 실행해 확인한 기록입니다. CEF 쪽 근거는 `libcef/browser/printing/print_dialog_linux.cc`입니다.

## F94. 리눅스에서 인쇄: 설정을 채우고 프로세스 밖 인쇄를 꺼야 한다 (2026-10-10)

- **환경**: CUPS가 동작하고 프린터 하나(`Samsung_C43x_Series_...`, idle)가 있는 컴퓨터, 오프스크린 브라우저, `xvfb-run`. `on_print_dialog`와 `on_print_job`은 `False`를 돌려 즉시 취소하게 해서 **실제로 인쇄하지 않았습니다**(`lpstat -o`로 대기열이 비어 있음을 확인).
- **핸들러가 없으면** `host.print()`는 아무 콜백도 오지 않고 아무 일도 없습니다(`Client.get_print_handler()`가 `None`이면 Linux에서 인쇄가 지원되지 않는다는 헤더 문서와 같음).
- **핸들러만 있고 설정을 채우지 않으면** `on_print_start`, `on_print_settings(get_defaults=True)`, `on_print_reset`만 오고 `on_print_dialog`는 오지 않습니다. `get_defaults`일 때 `settings.get_device_name()`이 빈 문자열이고, Chromium이 `print_error_dialog.cc`로 "선택한 프린터가 사용 불가능하거나 올바르게 설치되어 있지 않습니다"를 냅니다. **CEF는 CUPS의 프린터 목록을 쓰지 않습니다.**
- **채우면 진행합니다**: `on_print_settings(get_defaults=True)`에서 `set_device_name(프린터 이름)`, `set_dpi(300)`, `set_orientation(False)`, `set_printer_printable_area((2480, 3508), (0, 0, 2480, 3508), False)`, `set_copies(1)`을 호출하면 `is_valid()`가 `True`이고 `on_print_dialog`까지 옵니다(`on_print_start` → `on_print_settings` → `on_print_dialog` → `on_print_reset`).
- **계속하면 `kFailed`로 실패합니다 (원인 확인)**: `on_print_dialog`에서 `callback.continue_(settings)`를 부르면 Chromium이 `print_job_worker_oop.cc:191 Error rendering printed document via service ... kFailed`와 `print_error_dialog.cc`("인쇄를 시도하는 동안 문제가 발생했습니다")를 내고 `on_print_job`이 오지 않았습니다. 프로세스 밖 인쇄(Out-of-process print drivers) 때문이며, **`app.add_command_line_switch("disable-features", "EnableOopPrintDrivers")`를 주면 해결됩니다**(`PrintCompositorLPAC`를 함께 끄는 것은 필요하지 않았습니다). 이 스위치로 `on_print_start` → `on_print_settings` → `on_print_dialog` → `callback.continue_(settings)` → **`on_print_job(document_name, pdf_file_path, callback)`** → `callback.continue_()` → `on_print_reset`이 차례로 왔습니다.
- **`on_print_job`의 PDF**: `pdf_file_path`가 존재하고(`exists=True`), 복사해 열어 보니 올바른 PDF(`%PDF-1.4`, A4 `594.96 x 841.92 pts`, 1페이지, 본문 텍스트가 맞음)였습니다. 파일은 콜백이 끝나면 지워질 수 있으므로 필요하면 `on_print_job` 안에서 복사하거나 바로 보냅니다(지워지는 시점은 확인하지 않음). `document_name`은 `data:` URL이면 URL을 줄인 문자열(`data_text_html;base64,...`)이었습니다.
- **CUPS로 실제 인쇄 (선생님의 허락, 1회)**: `on_print_job` 안에서 `lp -d <프린터> -n 1 <pdf>`를 불러 `request id is ...-3 (1 file(s))`, 프린터가 `now printing`이 되었다가 약 1분 뒤 대기열이 비고 `completed` 목록에 올라갔습니다(CUPS 쪽 완료). **종이가 실제로 나와 내용이 맞았는지는 사용자가 확인해야 합니다**(이 환경에서는 볼 수 없음).
- **`print_to_pdf`**: `host.print_to_pdf(path, PdfPrintSettings(print_background=1), callback)`가 성공했고(`ok=True`, 9,778바이트, 올바른 PDF 1페이지) **`get_pdf_paper_size`는 불리지 않았습니다.** 헤더 문서는 Linux에서 `get_pdf_paper_size`가 필요하다고 하지만, 용지 크기를 `PdfPrintSettings`에 주지 않아도(`paper_width` 0) 이 환경에서는 PDF가 만들어졌습니다. `get_pdf_paper_size`를 CEF가 부르는 경우는 만들지 못했습니다.
- **설정이 PDF에 미치는 영향 (`on_print_job`의 PDF를 `pdfinfo`와 `pdftotext`로 확인, 용지는 쓰지 않음)**: 문서는 3쪽(쪽마다 `PAGE-n`) + 선택 영역이 있는 한 쪽, 총 4쪽입니다. 설정은 `on_print_settings(get_defaults=True)`와 `on_print_dialog`의 `callback.continue_(settings)`에 모두 같은 값을 줬습니다.

  | 시나리오 | 결과 |
  | --- | --- |
  | `set_orientation(True)`(가로) + 가로 용지 영역 | A4 가로(841.92 x 594.96 pt), 4쪽 |
  | `set_page_ranges([(1, 1)])` | **2쪽만**(`PAGE-2`). 범위는 **0부터 시작**합니다 |
  | `set_copies(3)` | PDF는 **4쪽 그대로**. 부수는 PDF에 반영되지 않으므로 프린터로 보낼 때 `lp -n 3`처럼 앱이 전달해야 합니다 |
  | `set_selection_only(True)` | `on_print_dialog`의 `has_selection`이 `True`이고(페이지에 선택 영역이 있음), PDF에는 선택한 글(`SELECTED-TEXT`)만 있음 |
  | 페이지의 `window.print()` | `host.print()`와 같은 흐름(`on_print_start` → … → `on_print_job` → `on_print_reset`) |

- **취소와 실패는 앱에 오류로 오지 않습니다**:

  | 경우 | 앱이 받는 콜백 |
  | --- | --- |
  | `on_print_dialog`가 `False`를 돌려줌, 또는 `callback.cancel()` | `on_print_start`, `on_print_settings`, `on_print_dialog`, `on_print_reset`(`on_print_job` 없음) |
  | `on_print_job`이 `False`를 돌려줌 | `on_print_job` 뒤 `on_print_reset` |
  | 프로세스 밖 인쇄가 켜진 채 계속함(`kFailed`) | `on_print_dialog` 뒤 `on_print_reset`(`on_print_job` 없음). 오류는 로그(`print_error_dialog.cc`)로만 나옴 |

  **취소와 `kFailed`는 앱에서 구분할 수 없습니다**(둘 다 `on_print_dialog` 뒤에 `on_print_job` 없이 `on_print_reset`). 앱이 알 수 있는 것은 "`on_print_job` 없이 끝났다"뿐입니다.
- **`on_print_job`의 `callback.continue_()`를 늦게 부르는 경우**: 멈춘 채로 두어도 교착은 없었고, 그 사이의 두 번째 `host.print()`도 새 사이클(`on_print_start` → … → `on_print_job`)을 시작했습니다(브라우저당 인쇄 작업 하나라는 문서와 달리 막지 않음). `on_print_reset`은 보관한 콜백으로 `continue_()`를 부른 시점에 왔습니다. 여러 작업이 겹치는 경우의 정확한 규칙은 확인하지 않았습니다(보관하는 콜백을 덮어써서 첫 콜백은 부르지 못함).
- **`get_pdf_paper_size`는 어떤 경로에서도 불리지 않았습니다**: `host.print()`, `window.print()`, `print_to_pdf`(용지 크기 지정 여부 무관), 가로, 범위, 선택 영역, 취소, 실패. CEF 소스에서 호출 지점은 `CefPrintingContextLinuxDelegate::GetPdfPaperSize`(`print_dialog_linux.cc`)이고 Chromium의 `PrintingContextLinux`가 PDF 용지 크기를 물을 때 부르는데, Chromium 소스가 이 컴퓨터에 없어 그 경로를 소스로 확인하지 못했습니다(CEF 위키도 같은 한계를 적음). **이 바인딩에서는 구현하지 않아도 지금까지의 모든 인쇄가 됐습니다.**
- **프린터 목록**: CEF에는 없습니다. `lpstat -e`(프린터 이름 목록), `lpstat -d`(기본값, 이 컴퓨터는 "no system default destination")로 얻고, 시스템 Python의 `pycups`(`cups.Connection().getPrinters()`)도 동작했습니다(프린터 상태 3 = idle). 가상 환경에는 `pycups`가 없고 설치하려면 `libcups2-dev`(`cups.h`)가 필요한데 이 컴퓨터에는 없습니다.
- **하지 않은 것**: 종이가 나온 내용의 확인, 선택 영역이 있을 때 대화상자의 "선택 영역만" 확인란(데모에서는 선택이 없어 비활성 상태만 확인).

### 겹친 작업의 규칙 (CEF 소스와 실험, 2026-10-10)

- **CEF 소스**(`libcef/browser/printing/print_dialog_linux.cc`): 인쇄 한 번마다 `CefPrintDialogLinux`가 **새로** 만들어집니다. `on_print_start`는 그 생성자, `on_print_reset`은 소멸자(마지막 참조가 풀릴 때)에서 불리고, PDF 임시 파일(`path_to_pdf_`)과 두 콜백(`PrintDialogCallback`, `PrintJobCallback`)도 작업마다 따로입니다. 브라우저당 하나라는 클래스 주석과 달리 코드에는 막는 곳이 없습니다.
- **실험**: `host.print()`를 연달아 두 번 부르고 두 `on_print_job`의 콜백과 PDF 경로를 각각 보관했습니다. 경로가 서로 다르고 둘 다 존재했습니다. **두 번째 작업의 `continue_()`를 먼저 부르자** 그 작업의 `on_print_reset`이 오고 그 PDF만 사라졌으며(2초 안에), 첫 작업의 PDF는 남았습니다. 첫 작업의 `continue_()`를 부르자 두 번째 `on_print_reset`이 오고 그 PDF도 사라졌습니다. 두 작업이 모두 끝난 뒤의 세 번째 `print()`도 정상으로 시작했습니다. 즉 **작업은 서로 독립이고 어느 순서로 끝내도 됩니다.** 앞의 "첫 콜백을 부르지 못함"은 시험 코드가 콜백을 한 변수에 덮어써서 생긴 것이었고 규칙이 아닙니다.
- **PDF 파일이 지워지는 시점**: `callback.continue_()`를 부른 뒤(또는 `on_print_job`이 `False`를 돌려준 뒤) 백그라운드에서 삭제합니다(`OnJobCompleted`). 그러므로 `continue_()` 전에 복사하거나 보내야 합니다.

### `get_pdf_paper_size`가 불리는 조건 (Chromium 154.0.8037.98 소스)

Chromium 소스가 이 컴퓨터에 없어서 GitHub 미러(`raw.githubusercontent.com/chromium/chromium/154.0.8037.98/...`)를 `WebFetch`로 읽었습니다. **요약 모델을 거친 인용이므로 중요한 판단 전에는 원문을 다시 확인해야 합니다.**

1. CEF의 `get_pdf_paper_size`는 `CefPrintingContextLinuxDelegate::GetPdfPaperSize`(CEF 소스)가 부르고, 그것은 Chromium의 `PrintingContextLinux::GetPdfPaperSizeDeviceUnits()`(`printing/printing_context_linux.cc`: `return ui::LinuxUi::instance()->GetPdfPaperSize(this);`)에서 옵니다.
2. `GetPdfPaperSizeDeviceUnits()`는 `printing/printing_context.cc`에서 **한 곳**, `SetDefaultPrintableAreaForVirtualPrinters()`(`gfx::Size paper_size(GetPdfPaperSizeDeviceUnits());`)에서만 불립니다.
3. 그 함수는 `PrintingContext::UpdatePrintSettings`가 `printer_type == kPdf || printer_type == kExtension`이고 `!open_in_external_preview`이며 인쇄 가능 영역이 비어 있을 때만 부릅니다.
4. 프린터 종류가 PDF가 되는 경우는 `PrintingContext::UsePdfSettings()`(`kSettingPrinterType = kPdf`, 장치 이름 빈 문자열)입니다. 이것은 `PrinterQuery::GetDefaultSettings(..., want_pdf_settings)`가 `true`일 때만 `GetPdfSettings()`로 불리고, `PrintViewManagerBase::GetDefaultPrintSettings`에서 `want_pdf_settings = analyzing_content_`입니다. `analyzing_content_`는 `set_analyzing_content()`가 정하는 **기업용 콘텐츠 분석**(인쇄 전 검사) 표시입니다.
5. 정리하면 `get_pdf_paper_size`는 (가) 인쇄 미리보기의 "PDF로 저장"이나 확장 프로그램 프린터, (나) 기업용 콘텐츠 분석 중에만 닿습니다. CEF의 일반 `host.print()`는 장치 이름이 있는 일반 프린터라서 닿지 않고, `print_to_pdf`는 DevTools의 `Page.printToPDF` 경로(`print_util.cc`)라서 닿지 않습니다. 앞의 실험에서 불리지 않은 것과 맞습니다.
- **확인하지 못한 것**: CEF의 Alloy 스타일이 (가)나 (나)를 쓰지 않는다는 것은 위 실험과 소스의 부재로 **추정**한 것이고, `set_analyzing_content(true)`를 부르는 곳(Chromium 쪽)은 찾지 못했습니다. 따라서 이 바인딩에서는 `get_pdf_paper_size`를 구현하지 않아도 된다고 보지만, 불리는 경로를 만드는 데는 성공하지 못했습니다.

### 사용자가 용지와 방향을 고르는 대화상자 (앱이 직접 만듦)

- **환경**: Tk(`cefweaver.ui` 어댑터) + `pycups`(시스템에 `libcups2-dev`를 설치해 `uv pip install pycups`가 빌드됨, 이 컴퓨터에서 `sudo apt install libcups2-dev`로 설치, 의존 패키지로 `libjpeg-dev`, `libtiff-dev`, `libcupsimage2-dev` 등이 함께 설치됨) + 가상 X 서버(`Xvfb`)와 `import`로 화면을 캡처. 인쇄는 모의 실행(`lp`를 부르지 않음)으로 했고 대기열은 비어 있음을 확인했습니다.
- **동작**: `on_print_dialog`에서 `True`를 돌려주고 앱의 `Toplevel` 대화상자(프린터, 용지 크기, 방향, 부수, 선택 영역만)를 띄웁니다. 사용자가 "Print"를 누르면 `PrintSettings.create()`에 `set_device_name`, `set_dpi(300)`, `set_orientation`, `set_printer_printable_area`(가로면 두 변을 바꿈), `set_copies`, `set_selection_only`를 채워 `callback.continue_(settings)`를 부르고, "Cancel"이면 `callback.cancel()`입니다. 대화상자가 열려 있는 동안 콜백을 보관해도 문제가 없었습니다(CEF가 기다림). 기본 용지는 `on_print_settings(get_defaults=True)`에서 A4, 세로로 채웁니다.
- **결과**: 기본값(A4, 세로)에서 A5, 가로, 2부로 바꾸고 "Print"를 누르면 `on_print_job`이 받은 PDF가 **A5 가로(594.96 x 420 pt), 2쪽**이었습니다(`pdfinfo`). 부수는 PDF에 반영되지 않으므로(위) `lp -n`으로 보내야 합니다. 화면 캡처는 대화 중에 사용자에게 보냈고 저장소에는 두지 않았습니다.
- **프린터 목록과 용지 이름**: `pycups`의 `conn.getPrinters()`와 PPD의 `PageSize`(`cups.PPD(conn.getPPD(name)).findOption("PageSize").choices`)로 얻습니다. **이 프린터(드라이버리스)의 PPD에는 용지별 크기(`PaperDimension`)가 없어서** `findAttr("PaperDimension", ...)`가 `None`이었고 `getPageSize`도 없었습니다. 이름(`A4`, `A5`, `Letter` 등)을 표준 크기 표로 바꾸고 `4x6`처럼 `NxM`이면 인치로 읽었습니다. 실제 프린터에서는 PPD마다 다를 수 있습니다.
- **예제로 저장소에 추가함 (2026-10-10)**: `examples/print/`(`printing.py`, `quickstart.py`, `smoke.py`, `README.md`)입니다. `smoke.py`는 가상 X 서버에서 대화상자와 작업을 구동해 11개를 점검합니다(대화상자의 기본값, 프린터가 CUPS의 것, 선택 영역이 없을 때 "선택 영역만"이 꺼짐, 취소하면 작업 없음, A5 가로 2부의 PDF가 A5 가로 595 x 420 pt 2쪽이고 선택이 전달됨, 선택 영역이 있으면 "선택 영역만"이 켜지고 PDF가 한 쪽, 정상 종료). **연속 3회 모두 통과**했고 프린터로는 아무것도 보내지 않았습니다(`lpstat -o`가 비어 있음). `quickstart.py`는 12초 동안 오류 없이 떠 있었습니다. 위의 `pdf_info`는 PDF 라이브러리 없이 `/MediaBox`와 `/Type /Page`를 정규식으로 읽습니다(`pdfinfo`의 결과와 같았음).
- **`cefweaver.ui`에 붙이는 방법 (라이브러리 수정 없음)**: `ui.BrowserView.client`(`_Handlers`)에는 `get_print_handler`가 없습니다. **인스턴스에 `get_print_handler`를 붙이면 무시되어** `host.print()`를 눌러도 아무 콜백이 오지 않았습니다(상태가 `ready`로 남음). 서브클래스를 만들어 `canvas.view.client.__class__ = ClientWithPrinting`으로 바꾸면 동작했습니다. 이것은 바인딩이 메서드의 재정의를 인스턴스가 아니라 **클래스**에서 찾는다는 뜻으로 보입니다(원인은 소스에서 확인하지 않음).
- **스위치**: `ui.Session(adapter, switches=[("disable-features", "EnableOopPrintDrivers")])`로 줍니다.

## 관련 페이지

- [실행해서 확인한 핸들러 (F55부터)](verified-findings-handlers.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [Python API 참조](python-api.md)
