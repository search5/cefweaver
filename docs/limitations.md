---
title: 한계와 알려진 제약
---

# 한계와 알려진 제약

아직 안 되는 것과 알려진 제약입니다. 각 항목에 원인을 확인했는지 적었습니다.

## 플랫폼

| 항목 | 상태 |
| --- | --- |
| Linux x86_64 | 개발하고 시험하는 플랫폼입니다 |
| Windows | 검증하지 못했습니다 |
| macOS arm64 | 빌드하고 시험했습니다. 아래 "macOS" 절의 차이가 있습니다 |
| macOS x86_64 | Rosetta에서 빌드하고 구동했습니다. 실제 Intel Mac은 아닙니다 |
| 창 모드 + Wayland | 코드로 닫을 수 없고 종료할 때 죽습니다. CEF의 한계로 확인했습니다([Wayland와 GPU](wayland-gpu.md)) |
| X11 + GPU | 일부 기계에서 영상이 안 나옵니다. 원인은 찾지 못했습니다(같은 쪽) |

## macOS

Apple Silicon에서 확인한 범위입니다. 오프스크린과 네이티브 창, Cocoa 창 안의 `NSView`(`parent_view`), JavaScript 바인딩, 종료, Tk 위젯, 헤드리스 어댑터와 메뉴, 편집 키가 동작합니다.

| 항목 | 상태 |
| --- | --- |
| 편집 키(Backspace, 화살표, Delete) | 호스트 API(`send_key_event`)로 직접 보낼 때는 mac 가상 키코드(`native_key_code`)를 주어야 하고, KEYUP에는 `character`(Cocoa 문자)가 있어야 합니다. 없으면 편집 키가 무시되거나 두 번 편집됩니다. `cefweaver.ui`의 `BrowserView.key()`는 이를 채웁니다 |
| Command 조합 | 오프스크린에서 Command+A/Z/Shift+Z는 `Frame` 명령으로, Command+C/X/V는 툴킷 클립보드로 처리합니다(CEF에 Edit 메뉴가 없어 키로는 안 됩니다). 네이티브 뷰(`parent_view`)는 CEF가 처리합니다 |
| 새 탭 요청 | Ctrl+클릭은 오른쪽 클릭이 됩니다. Command+클릭을 쓰세요 |
| 공유 텍스처 | 없습니다. `on_accelerated_paint`의 평면은 비어 있습니다 |
| 인쇄 | `print()`가 끝나지 않았습니다(원인 미조사) |
| 맞춤법 추천 | 추천 단어가 오지 않았습니다. macOS의 `NSSpellChecker`로 검사합니다(원인 미조사) |
| 컨텍스트 메뉴 | 기본 메뉴에 뒤로와 앞으로가 없었습니다 |
| 툴킷 | Tk, Qt, wx, SDL2는 확인했습니다. GTK 3(시스템에 없음)와 Kivy(Python 3.14용 창 제공자가 없음)는 확인하지 못했습니다. Cocoa나 SwiftUI에 붙일 때는 `parent_view`를 쓰세요([시작하기](quickstart.md)) |
| `parent_view` | PyObjC로 만든 Cocoa 창, Swift의 `NSViewRepresentable`, Qt(`winId()`), wx(`GetHandle()`)에서 확인했습니다. Tk의 `winfo_id()`는 `NSView`가 아니어서 죽습니다(창의 content view는 됨, 창 전체를 채움) |
| 한 창에 브라우저 여러 개 | 각자의 뷰에 붙고 크기를 따라갑니다. 그중 하나만 닫으면 `on_before_close`가 `shutdown()` 때에야 옵니다 |
| 종료 감시 | 네이티브 arm64 Python에서는 `shutdown()`이 0.1초 안에 끝납니다. Rosetta(x86_64)와 Swift 실행 파일에 임베드한 Python에서는 `CefShutdown()`이 끝나지 않아 Chromium의 감시가 10초 뒤 종료 코드 2로 프로세스를 죽였습니다(원인 미확인) |
| macOS x86_64 | Rosetta에서 빌드하고 구동했습니다(위 종료 문제 포함). 실제 Intel Mac은 아닙니다 |
| 창 제목 | 확인하지 못했습니다 |
| 서명 | CEF 프레임워크와 도우미 앱은 ad hoc 서명입니다. 배포하려면 직접 서명과 공증이 필요합니다 |

## 기능

| 항목 | 상태 |
| --- | --- |
| 인쇄 | **Linux에서는 앱이 직접 처리하면 됩니다.** CEF에는 인쇄 대화상자도 프린터 목록도 없어서 `PrintHandler`에서 설정을 채우고(`on_print_settings`) 자체 대화상자를 띄우고(`on_print_dialog`) 받은 PDF를 CUPS로 보냅니다. `disable-features=EnableOopPrintDrivers`가 필요합니다. 전체 예는 `examples/print/`에 있습니다. `cefweaver.ui`의 어댑터에는 들어 있지 않아 메뉴의 `인쇄`는 동작하지 않습니다. macOS는 `print()`가 끝나지 않았습니다 |
| SDL2, Kivy의 오른쪽 클릭 메뉴 | 없습니다. 두 툴킷에 네이티브 메뉴 위젯이 없습니다(공식 문서로 확인). 이 두 툴킷에서는 `view.on_context_menu`도 불리지 않습니다 |
| Tk의 한영 전환 | 되지 않습니다. 원인은 확인하지 못했습니다 |
| 앱이 소리와 영상을 직접 대는 방식 | 없습니다. 마이크와 카메라는 Chromium이 시스템 장치에서 직접 받습니다 |
| 한 세션에 브라우저 하나 | `ui.Session`은 브라우저 하나만 다룹니다 |
| CEF 초기화 | 프로세스당 한 번만 됩니다. `shutdown()` 뒤에도 다시 못 합니다 |

## 미디어

- **코덱**: VP9, AV1, Opus는 재생되고 **H.264(`avc1`)와 AAC(`mp4a`)는 재생되지 않습니다.** 표준 CEF 빌드는 독점 코덱을 넣지 않기 때문입니다. YouTube는 VP9와 Opus를 내려 주어 재생됩니다. H.264만 내려 주는 사이트는 재생되지 않을 것으로 보입니다(직접 확인하지는 않았습니다). 독점 코덱이 필요하면 CEF를 직접 빌드하세요(`python tools/prepare.py --build-cef --proprietary-codecs`).
- **마이크**: 시스템에서 음소거이면 장치는 열리지만 소리가 들어오지 않습니다([소리, 마이크, 카메라](media.md)).

## API

- **`bridge.evaluate`**: 페이지에 컨텍스트가 만들어지기 전에 보낸 식과, 답하기 전에 페이지를 떠난 식에는 콜백이 오지 않습니다(`ready()` 같은 신호를 받은 뒤에 보내세요). 식은 블록 안에서 실행되어 `"use strict"` 지시문이 효과가 없고, `Symbol`과 `BigInt` 결과는 `TypeError`로 옵니다.
- **`DragData.get_file_name()`**: 파일 내용이 있는 드래그에서만 부르세요. 없을 때 부르면 프로세스가 죽습니다. CEF가 확인 없이 Chromium의 함수를 부르고 그 안의 `CHECK`가 실패합니다(CEF의 한계로 확인했습니다).
- **Views**: **`MessagePump`(외부 메시지 펌프)로는 CEF 창의 마우스와 키 입력이 오지 않으므로** `do_message_loop_work()`를 자주 부르는 폴링 루프를 쓰세요. Linux X11에서만 확인했습니다([Views](views.md)).
- **`Image`**: CEF를 초기화한 뒤에만 만들 수 있습니다(`Image.create_image()`가 `RuntimeError`). 초기화 전에 만들면 객체가 사라질 때 프로세스가 죽는 것을 확인했습니다.
- **아직 열지 않은 것**: `on_certificate_error`는 `ssl_info`를 넘기지 않습니다(인증서는 `get_visible_navigation_entry().get_ssl_status()`로 읽습니다). `OnBeforeDevToolsPopup`, `ResourceBundleHandler`, `TaskRunner`도 아직 없습니다. 렌더러에서 Python을 실행하는 것은 구조상 되지 않고, [렌더러 이벤트](events.md)로 알림만 받습니다.
- **캐시 폴더**: 캐시 경로를 주지 않으면 CEF가 작업 폴더에 `cache/`를 만듭니다.

## 시험의 범위

- macOS의 시험은 창 모드를 포함해 모두 돌렸습니다(`test_smoke.py` 194개가 약 3분, 창이 열립니다). 한 번은 전체 실행 중 시험 하나가 일시적으로 실패했는데 원인을 확인하지 못했습니다.
- 툴킷의 점검은 가상 X 서버에서 실제 X 이벤트로 합니다. 실제 입력기(ibus, fcitx)로 한글을 입력해 본 것은 GTK 3뿐입니다.
- 툴킷 자체를 네이티브 Wayland로 쓰는 경우(GTK나 Qt의 Wayland 백엔드)는 시험하지 못했습니다. 시험은 툴킷 창은 X11, CEF는 Wayland였습니다.
- 데스크톱 환경은 GNOME(mutter) 한 곳, GPU 구성은 한 기계에서만 확인했습니다.
