Title: File Size Limit Request: cefweaver

**Project URL**: https://pypi.org/project/cefweaver/   (TestPyPI: <fill in if requested there as well>)

**Does this project already exist?** Yes (a first release under the default limit was uploaded: <version>). <fill in after the upload>

**Which limit do you want raised?** Both the file size limit and the total project size limit.

**New limits requested**
- File size limit: 250 MiB
- Total project size limit: 30 GiB

**Which indexes**: PyPI (and TestPyPI, if it is used for dry runs)

**Size of the release**: one wheel per platform, about 150 to 175 MB each (measured in CI on 2026-10-12):

| Platform | Wheel |
| --- | --- |
| manylinux_2_28 x86_64 | about 158 MB |
| manylinux_2_28 aarch64 | about 174 MB |
| macOS arm64 / x86_64 | about 147 MB (arm64 measured; x86_64 not yet) |
| Windows x86_64 | not measured yet |

A release has up to 4 to 6 wheels (about 1 GB in total). The wheels use the stable ABI (`cp311-abi3`), so one wheel per platform serves every Python version from 3.11. There is no per-Python-version wheel.

**Description of the project**: cefweaver is a Python binding of the Chromium Embedded Framework (CEF 154) with a GUI toolkit layer (Qt, GTK, wx, pywin32 and others) to embed a Chromium widget in desktop applications. Repository: https://github.com/search5/cefweaver (BSD-3-Clause).

**Reason for the additional size**: each wheel contains the CEF runtime: `libcef` (the Chromium engine, which makes up most of the wheel), the ICU data, the V8 snapshot, the Vulkan/GL support libraries and the resource packs, together with the extension module and a helper subprocess. The engine cannot be split off or downloaded at install time without breaking `pip install` for offline and locked environments, and the runtime must match the bindings exactly (the generated bindings are tied to one CEF version). The wheels are not padded with models or data, and the sizes are those of the CEF binary distribution. We have already kept the system libraries out of the manylinux wheels (`auditwheel repair --exclude`) so that only the CEF runtime remains.

**Release frequency**: low. We expect a release only when the bound CEF version changes or for fixes, a few per year, not nightly builds.

**Other information**: manylinux_2_28 (x86_64, aarch64), macOS (arm64, x86_64) and Windows wheels are built and tested in GitHub Actions and will be published with trusted publishing.
