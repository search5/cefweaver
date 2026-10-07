"""Prepare native prerequisites before ``uv build --wheel``.

Steps:
  1. Resolve the CEF binary distribution (--cef-root, $CEF_ROOT, --build-cef to
     build CEF from source, or download the prebuilt one).
  2. Configure and build the native targets (cefwrapper, cefsubprocess) with CMake.

On Linux the CEF runtime (libcef.so, resources, cefsubprocess) is copied into the
``cefweaver/`` package directory so that ``uv build --wheel`` packages it; the
copy of libcef.so is stripped (1.4 GB -> ~270 MB) and the CEF distribution itself
is left untouched.

The resolved CEF is linked at ``build/native/cef`` so that pyproject.toml can
reference a fixed relative path (include-dirs, library-dirs), and the result is
recorded in ``build/native/prepare.json``.

Usage:
  python tools/prepare.py                        # download the prebuilt CEF
  python tools/prepare.py --cef-root /path/cef   # use a self-built or extracted CEF
  python tools/prepare.py --build-cef [--dry-run] # build CEF (libcef) from source
  python tools/prepare.py --no-stage              # skip copying the runtime into cefweaver/
  python tools/prepare.py --list-versions [FILTER]
                                                 # list full CEF version names
  python tools/prepare.py --cef-version "120.2.7+g4bc6a59+chromium-120.0.6099.234"
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling modules, also under -I

import build_cef  # noqa: E402

DEFAULT_BUILD_DIR = ROOT / "build" / "native"
MARKER_NAME = "prepare.json"

INDEX_URL = "https://cef-builds.spotifycdn.com/index.json"
INDEX_CACHE_NAME = "cef_index.json"
INDEX_MAX_AGE = 24 * 60 * 60  # seconds


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--cef-root",
        help="Path to an existing CEF binary distribution (cef_binary_*). "
        "Defaults to $CEF_ROOT; if neither is set, the prebuilt is downloaded.",
    )
    parser.add_argument(
        "--cef-version",
        help="Full CEF version name to download when --cef-root is not given, "
        "e.g. 120.1.8+ge6b45b0+chromium-120.0.6099.109 (see --list-versions).",
    )
    parser.add_argument(
        "--list-versions",
        nargs="?",
        const="",
        metavar="FILTER",
        help="List the full names of the available prebuilt CEF versions and exit. "
        "The optional FILTER keeps only versions that start with it (e.g. 120).",
    )
    parser.add_argument("--channel", choices=("stable", "beta"), default="stable",
                        help="Channel shown by --list-versions (default: stable).")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum rows shown by --list-versions (0 = all).")
    parser.add_argument("--platform", dest="cef_platform",
                        help="CEF platform key, e.g. linux64 (default: detected).")
    parser.add_argument("--refresh-index", action="store_true",
                        help="Ignore the cached version index and download it again.")
    parser.add_argument(
        "--build-cef",
        action="store_true",
        help="Build CEF (libcef) from source with automate-git.py instead of "
        "downloading the prebuilt one. Takes hours and ~120 GB of disk; "
        "see tools/build_cef.py and the options below (--dry-run to preview).",
    )
    source = parser.add_argument_group("source build options (with --build-cef)")
    build_cef.add_arguments(source)
    parser.add_argument("--no-stage", action="store_true",
                        help="Do not copy the CEF runtime into the cefweaver/ package directory.")
    parser.add_argument("--no-strip", action="store_true",
                        help="Do not strip the staged libcef.so.")
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--config", choices=("Debug", "Release"), default="Release")
    return parser.parse_args()


def link_cef(build_dir, cef_root):
    """Expose cef_root at the fixed path <build_dir>/cef."""
    link = build_dir / "cef"
    if link.is_symlink() or link.exists():
        if sys.platform == "win32" and link.is_dir() and not link.is_symlink():
            os.rmdir(link)  # junction
        else:
            link.unlink()
    if sys.platform == "win32":
        # A junction needs no administrator privilege, unlike a symlink.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(cef_root)],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        link.symlink_to(cef_root, target_is_directory=True)
    return link


def detect_cef_platform():
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if sys.platform.startswith("linux"):
        return "linuxarm64" if arm else "linux64"
    if sys.platform == "win32":
        return "windowsarm64" if arm else "windows64"
    if sys.platform == "darwin":
        return "macosarm64" if arm else "macosx64"
    sys.exit(f"error: unsupported platform: {sys.platform}")


def default_cef_version():
    """CEF_VERSION default declared in the top-level CMakeLists.txt."""
    text = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(r'set\(CEF_VERSION "([^"]+)"\)', text)
    return match.group(1) if match else None


def load_index(build_dir, refresh=False):
    """Return the CEF builds index, cached in the build directory for a day."""
    cache = build_dir / INDEX_CACHE_NAME
    fresh = cache.is_file() and time.time() - cache.stat().st_mtime < INDEX_MAX_AGE
    if fresh and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    try:
        print(f"Downloading the CEF version index from {INDEX_URL} ...", file=sys.stderr)
        with urllib.request.urlopen(INDEX_URL, timeout=30) as response:
            raw = response.read()
        index = json.loads(raw)
    except (OSError, ValueError) as error:
        if cache.is_file():
            print(f"warning: could not refresh the index ({error}); using the stale cache.",
                  file=sys.stderr)
            return json.loads(cache.read_text(encoding="utf-8"))
        raise SystemExit(f"error: could not download the CEF version index: {error}")

    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_bytes(raw)
    tmp.replace(cache)
    return index


def version_key(entry):
    """Sort key from the leading numbers: '120.1.8+g...' -> (120, 1, 8).

    Old builds look like '3.3683.1920.g9f41a27' (hash after a dot), so only the
    leading run of numeric components is used.
    """
    numbers = re.match(r"\d+(?:\.\d+)*", entry["cef_version"]).group(0)
    return tuple(int(n) for n in numbers.split("."))


def standard_builds(index, cef_platform):
    """(version entry, standard archive entry) pairs, highest version first."""
    if cef_platform not in index:
        sys.exit(f"error: unknown platform {cef_platform!r}; available: "
                 + ", ".join(sorted(index)))
    for entry in sorted(index[cef_platform]["versions"], key=version_key, reverse=True):
        archive = next((f for f in entry["files"] if f["type"] == "standard"), None)
        if archive:
            yield entry, archive


def list_versions(args, build_dir):
    cef_platform = args.cef_platform or detect_cef_platform()
    index = load_index(build_dir, args.refresh_index)
    default = default_cef_version()

    rows = [(e, a) for e, a in standard_builds(index, cef_platform)
            if e["channel"] == args.channel and e["cef_version"].startswith(args.list_versions)]
    if not rows:
        sys.exit(f"No {args.channel} builds for {cef_platform} match {args.list_versions!r}.")

    shown = rows if args.limit <= 0 else rows[:args.limit]
    print(f"{cef_platform}, {args.channel} channel "
          f"({len(shown)} of {len(rows)} matching builds, newest first)\n")
    print(f"  {'CEF version':<56}{'size':>8}")
    for entry, archive in shown:
        mark = "  <- default" if entry["cef_version"] == default else ""
        print(f"  {entry['cef_version']:<56}{archive['size'] // 2**20:>6}MB{mark}")
    if len(shown) < len(rows):
        print(f"\n  ... {len(rows) - len(shown)} more (use --limit 0 or a FILTER)")
    example = shown[0][0]["cef_version"]
    print(f'\nUsage: python tools/prepare.py --cef-version "{example}"')


def validate_cef_version(version, cef_platform, build_dir, refresh):
    """Fail early, with a hint, when the full version name does not exist."""
    try:
        index = load_index(build_dir, refresh)
    except SystemExit as error:
        print(f"warning: skipping version validation ({error})", file=sys.stderr)
        return
    if not any(e["cef_version"] == version for e, _ in standard_builds(index, cef_platform)):
        sys.exit(f"error: {version!r} is not an available {cef_platform} build. "
                 "Use the full name shown by --list-versions.")


PACKAGE_DIR = ROOT / "cefweaver"
STAGED_MANIFEST = "staged_runtime.json"
STAGE_EXCLUDE = {"chrome-sandbox"}  # the wrapper runs with no_sandbox


def stage_runtime(cef_root, build_dir, config, strip):
    """Copy the CEF runtime and cefsubprocess into the cefweaver/ package directory.

    The files sit next to the extension module on purpose: CEF looks for
    icudtl.dat next to libcef.so, and cefsubprocess finds libcef.so through its
    rpath ($ORIGIN). Everything staged is recorded so that the next run can
    remove it first (it is not tracked by git).
    """
    if not sys.platform.startswith("linux"):
        print("note: staging the runtime is implemented for Linux only; skipped.")
        return []

    manifest = build_dir / STAGED_MANIFEST
    if manifest.is_file():
        for name in json.loads(manifest.read_text(encoding="utf-8")):
            target = PACKAGE_DIR / name
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()

    subprocess_exe = build_dir / "native" / "cefsubprocess" / config / "cefsubprocess"
    if not subprocess_exe.is_file():
        sys.exit(f"error: {subprocess_exe} not found; was the native build successful?")

    sources = [p for sub in ("Release", "Resources")
               for p in sorted((cef_root / sub).iterdir())
               if p.name not in STAGE_EXCLUDE]
    sources.append(subprocess_exe)

    staged = []
    for src in sources:
        dst = PACKAGE_DIR / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
            if strip and src.name == "libcef.so":
                subprocess.run(["strip", "--strip-unneeded", str(dst)], check=True)
        staged.append(src.name)

    manifest.write_text(json.dumps(staged, indent=2), encoding="utf-8")
    size = sum(f.stat().st_size for n in staged for f in
               ([PACKAGE_DIR / n] if (PACKAGE_DIR / n).is_file()
                else (PACKAGE_DIR / n).rglob("*")) if f.is_file())
    print(f"Staged {len(staged)} runtime entries into {PACKAGE_DIR} ({size / 2**20:.0f} MB)")
    return staged


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    args = parse_args()

    if args.list_versions is not None:
        list_versions(args, args.build_dir.resolve())
        return

    if args.build_cef:
        if args.cef_root:
            sys.exit("error: --build-cef and --cef-root cannot be used together.")
        built = build_cef.build_cef(args)
        if built is None:  # --dry-run
            return
        args.cef_root = str(built)

    cef_root = args.cef_root or os.environ.get("CEF_ROOT")
    if cef_root:
        cef_root = Path(cef_root).expanduser().resolve()
        if not (cef_root / "cmake" / "FindCEF.cmake").is_file():
            sys.exit(
                f"error: not a valid CEF binary distribution "
                f"(cmake/FindCEF.cmake not found): {cef_root}"
            )

    build_dir = args.build_dir.resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    if args.cef_version and not args.build_cef:
        if cef_root:
            print("warning: --cef-version is ignored because a CEF root is given.",
                  file=sys.stderr)
        else:
            validate_cef_version(args.cef_version,
                                 args.cef_platform or detect_cef_platform(),
                                 build_dir, args.refresh_index)

    configure = ["cmake", "-S", str(ROOT), "-B", str(build_dir),
                 f"-DCMAKE_BUILD_TYPE={args.config}",
                 f"-DPYTHON_EXECUTABLE={sys.executable}"]
    if cef_root:
        configure.append(f"-DCEF_ROOT={cef_root}")
    else:
        # Drop a CEF_ROOT left in the cache by an earlier run with --cef-root.
        configure.append("-UCEF_ROOT")
    if args.cef_version:
        configure.append(f"-DCEF_VERSION={args.cef_version}")
    run(configure)
    run(["cmake", "--build", str(build_dir), "--config", args.config])

    # CMake resolves CEF_ROOT (including a downloaded one); read it back.
    cache = (build_dir / "CMakeCache.txt").read_text(encoding="utf-8")
    resolved = next(
        (line.split("=", 1)[1] for line in cache.splitlines()
         if line.startswith("CEFWEAVER_CEF_ROOT:")),
        str(cef_root or ""),
    )

    if not resolved or not Path(resolved).is_dir():
        sys.exit("error: could not determine CEF_ROOT from the CMake cache")
    link = link_cef(build_dir, Path(resolved))
    staged = [] if args.no_stage else stage_runtime(
        Path(resolved), build_dir, args.config, not args.no_strip)

    marker = {"cef_root": resolved, "cef_link": str(link), "staged": staged, "build_dir": str(build_dir), "config": args.config}
    (build_dir / MARKER_NAME).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    print(f"\nPrepared. CEF_ROOT={resolved}\nLinked:   {link}\nNext: uv build --wheel")


if __name__ == "__main__":
    main()
