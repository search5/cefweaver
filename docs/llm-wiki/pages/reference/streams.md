---
title: 스트림과 ZIP 읽기
type: reference
sources:
  - tools/gen/typesys.py
  - tools/gen/emit_cython.py
  - tools/gen/emit_cpp.py
  - tools/gen/scope.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 스트림과 ZIP 읽기

`CefStreamReader`, `CefStreamWriter`, `CefZipReader`와 이것들의 원천이 되는 `ReadHandler`, `WriteHandler`입니다. C의 `fread`/`fwrite` 규약(`ptr, size, n`)이 있는 메서드를 Python에서 쓰기 편하게 바꾸는 규칙이 이 페이지의 중심입니다. 헤더만으로는 이 규약을 알 수 없어서 생성기에 표로 적어 둡니다(`ITEM_BYTES`, `BYTES_OUT`, `BYTES_IN_COPY`, `SIZED_BUFFERS`, `IGNORED_PARAMS`, `CLAMPED_RETURNS`, 모두 `tools/gen/typesys.py`).

## Python에서 쓰는 방법

```python
writer = cefweaver.StreamWriter.create_for_file(path)
writer.write(b"hello")             # 5: 쓴 항목 수 (항목은 1바이트)
writer.write(b"abcdef", 2)         # 3: 2바이트 항목 셋
writer.flush()

reader = cefweaver.StreamReader.create_for_file(path)
reader.read(5)                     # b"hello": 최대 5개 항목(기본 항목 크기 1)
reader.read(2, 2)                  # 2바이트 항목 둘, 4바이트
reader.eof()
```

| 메서드 | Python | 규칙 |
| --- | --- | --- |
| `StreamWriter.Write(ptr, size, n)` | `write(data, size=1) -> int` | `n = len(data) / size`. 나누어떨어지지 않거나 `size`가 0이면 `ValueError`, 바이트열이 아니면 `TypeError`. 쓴 항목 수를 돌려줍니다. |
| `StreamReader.Read(ptr, size, n)` | `read(n, size=1) -> bytes` | 최대 `n * size` 바이트. 돌려주는 길이는 읽은 항목 수 × `size`. 음수는 `OverflowError`. |
| `StreamReader.CreateForData(data, size)` | `create_for_data(data) -> StreamReader | None` | CEF가 데이터를 복사합니다(`libcef/browser/stream_impl.cc`의 `CefBytesReader::SetData`). 빈 데이터는 `None`. |
| `ZipReader.ReadFile(buffer, bufferSize)` | `read_file(buffer_size) -> bytes` | CEF가 음수를 돌려주면(오류, 예: 열린 파일이 없음) `RuntimeError`, 0이면 `b""`. |
| `ReadHandler.Read(ptr, size, n)` | `read(self, ptr: memoryview, size: int) -> int` | `ptr`는 쓰기 가능한 뷰(길이 `size * n`, 호출이 끝나면 무효). 읽은 **항목 수**를 돌려줍니다. 아이템 수 `n`은 `len(ptr) // size`입니다. |
| `WriteHandler.Write(ptr, size, n)` | `write(self, ptr: memoryview, size: int) -> int` | `ptr`는 읽기 전용 뷰. 쓴 항목 수를 돌려줍니다. |

Python 핸들러가 `n`보다 많은 항목을 돌려주면 프록시가 `n`으로 줄입니다(CEF가 버퍼 밖을 읽지 않게).

## 시험

`test_streams_read_and_write_bytes_in_items`, `test_python_objects_can_be_the_source_and_the_sink_of_a_stream`, `test_a_zip_reader_reads_a_file_of_the_archive`가 CEF를 시작하지 않고 파일, 메모리, Python 핸들러, `zipfile`로 만든 ZIP으로 확인합니다.

## 제약

- `ZipReader.get_file_last_modified`는 날짜 구조체(`CefBaseTime`) 때문에 생성되지 않습니다.
- 스트림을 CEF 내부가 쓰는 경로(예: 리소스 응답으로 `ResourceHandler`에서 스트림을 읽게 하기)는 시험하지 않았습니다.
- 다른 크기가 둘인 포인터(`CefV8Value::CreateArrayBuffer` 등)는 아직 없는 표 항목이라 생성되지 않습니다.

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [Python API 참조](python-api.md)
