"""Build CEF (libcef) from source with CEF's automate-git.py.

The counterpart of cefpython's ``automate.py --build-cef``. It derives the CEF
branch and commit from a full CEF version name, runs upstream's
``automate-git.py`` (which fetches depot_tools, Chromium and CEF, then builds
and creates the binary distribution) and returns the resulting
``cef_binary_*`` directory, i.e. the value for ``prepare.py --cef-root``.

Building needs a lot of resources (roughly 120 GB of disk, 16 GB of RAM and
hours of CPU time). Use ``--dry-run`` to review the plan first.

Usage:
  python tools/build_cef.py --cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98" --dry-run
  python tools/build_cef.py --cef-build-dir /data/cef_src
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CEF_BUILD_DIR = ROOT / "build" / "cef_src"
CEF_GIT_URL = "https://github.com/chromiumembedded/cef.git"
AUTOMATE_URL = ("https://raw.githubusercontent.com/chromiumembedded/cef/"
                "{commit}/tools/automate/automate-git.py")
MIN_FREE_GB = 120
MIN_RAM_GB = 16

# Flags from CEF's automated_build_setup.md (Linux), plus use_allocator=none:
# libcef.so is loaded into a Python process, and cefpython needed the same
# setting (its "issue73") to avoid tcmalloc problems.
GN_DEFINES_OFFICIAL = ("is_official_build=true use_sysroot=true use_allocator=none "
                       "symbol_level=1 is_cfi=false")
GN_DEFINES_FAST = "use_sysroot=true use_allocator=none symbol_level=1 is_cfi=false"
GN_DEFINES_CODECS = "proprietary_codecs=true ffmpeg_branding=Chrome"

# Distribution directories that are not the full one prepare.py needs.
PARTIAL_SUFFIXES = ("_minimal", "_client", "_sandbox", "_tools", "_symbols",
                    "_debug_symbols", "_release_symbols")


def parse_version(version):
    """Return (cef_branch, cef_commit) from a full CEF version name.

    '154.0.34+g14c5a08+chromium-154.0.8037.98' -> ('8037', '14c5a08')
    '3.3683.1920.g9f41a27'                     -> ('3683', '9f41a27')
    """
    match = re.fullmatch(r"\d+\.\d+\.\d+\+g([0-9a-f]+)\+chromium-\d+\.\d+\.(\d+)\.\d+",
                         version)
    if match:
        return match.group(2), match.group(1)
    match = re.fullmatch(r"3\.(\d+)\.\d+\.g([0-9a-f]+)", version)
    if match:
        return match.group(1), match.group(2)
    sys.exit(f"error: not a full CEF version name: {version!r}\n"
             "       expected e.g. 154.0.34+g14c5a08+chromium-154.0.8037.98")


def default_cef_version():
    text = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(r'set\(CEF_VERSION "([^"]+)"\)', text)
    if not match:
        sys.exit("error: could not read the default CEF_VERSION from CMakeLists.txt")
    return match.group(1)


def ram_gb():
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        return pages * os.sysconf("SC_PAGE_SIZE") / 2**30
    except (ValueError, OSError, AttributeError):
        return None


def check_environment(args, build_dir):
    """Return a list of (blocking, message) problems with this machine."""
    problems = []
    if not sys.platform.startswith("linux"):
        problems.append((True, "building CEF from source is implemented for Linux "
                               f"only (this is {sys.platform})."))
    if platform.machine().lower() not in ("x86_64", "amd64"):
        problems.append((True, "only x86_64 hosts are supported "
                               f"(this is {platform.machine()})."))
    for tool in ("git", "python3"):
        if not shutil.which(tool):
            problems.append((True, f"`{tool}` was not found in PATH."))
    if " " in str(build_dir):
        problems.append((True, f"the build directory must not contain spaces: {build_dir}"))

    probe = build_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free_gb = shutil.disk_usage(probe).free / 2**30
    if free_gb < MIN_FREE_GB:
        problems.append((not args.skip_resource_check,
                         f"{free_gb:.0f} GB free on {probe}; about {MIN_FREE_GB} GB is needed."))
    ram = ram_gb()
    if ram is not None and ram < MIN_RAM_GB:
        problems.append((not args.skip_resource_check,
                         f"{ram:.0f} GB of RAM; {MIN_RAM_GB} GB or more is recommended."))
    return problems


def remote_checks(branch, commit):
    """Verify that the branch exists and that its head matches the commit."""
    try:
        out = subprocess.run(
            ["git", "ls-remote", CEF_GIT_URL, f"refs/heads/{branch}"],
            check=True, capture_output=True, text=True, timeout=60).stdout.split()
    except (OSError, subprocess.SubprocessError) as error:
        return f"warning: could not verify the branch online ({error})"
    if not out:
        sys.exit(f"error: CEF has no branch {branch!r} (see {CEF_GIT_URL}).")
    head = out[0]
    note = "is the head of" if head.startswith(commit) else "is NOT the head of (older commit)"
    return f"commit {commit} {note} branch {branch} ({head[:12]})"


def fetch_automate_script(commit, build_dir, dry_run):
    """Download the automate-git.py that belongs to the requested commit."""
    url = AUTOMATE_URL.format(commit=commit)
    script = build_dir / "automate-git.py"
    if dry_run:
        return script, None
    build_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            text = response.read().decode("utf-8")
    except OSError as error:
        sys.exit(f"error: could not download automate-git.py: {error}")
    script.write_text(text, encoding="utf-8")
    return script, text


def gn_defines(args):
    if args.gn_defines is not None:
        return args.gn_defines
    defines = GN_DEFINES_FAST if args.fast_build else GN_DEFINES_OFFICIAL
    if args.proprietary_codecs:
        defines += " " + GN_DEFINES_CODECS
    return defines


def automate_command(args, script, script_text, build_dir, branch, commit):
    """Arguments for automate-git.py. Optional flags are added only when the
    script (taken from the same commit) actually supports them."""
    def supported(flag):
        return script_text is None or flag in script_text

    cmd = [sys.executable, str(script),
           f"--download-dir={build_dir}",
           f"--depot-tools-dir={build_dir / 'depot_tools'}",
           f"--branch={branch}", f"--checkout={commit}",
           "--x64-build", "--no-debug-build", "--build-target=cefsimple",
           "--force-build"]
    for flag in ("--no-chromium-history", "--no-distrib-archive"):
        if supported(flag):
            cmd.append(flag)
    if not args.fast_build and supported("--with-pgo-profiles"):
        cmd.append("--with-pgo-profiles")
    if args.no_depot_tools_update:
        cmd.append("--no-depot-tools-update")
    return cmd


def find_distribution(build_dir):
    """The full cef_binary_*_linux64 directory created by automate-git.py."""
    distrib = build_dir / "chromium" / "src" / "cef" / "binary_distrib"
    if not distrib.is_dir():
        return None
    candidates = [
        p for p in distrib.glob("cef_binary_*_linux64")
        if p.is_dir() and not p.name.endswith(PARTIAL_SUFFIXES)
        and (p / "cmake" / "FindCEF.cmake").is_file()
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def build_cef(args):
    """Run the build and return the cef_binary_* directory (or None for a dry run)."""
    version = args.cef_version or default_cef_version()
    branch, commit = parse_version(version)
    build_dir = Path(args.cef_build_dir).expanduser().resolve()

    print(f"CEF version : {version}")
    print(f"CEF branch  : {branch}")
    print(f"CEF commit  : {commit}")
    print(f"Build dir   : {build_dir}")
    print(f"GN_DEFINES  : {gn_defines(args)}")

    problems = check_environment(args, build_dir)
    for blocking, message in problems:
        print(f"{'error' if blocking else 'warning'}: {message}", file=sys.stderr)
    if any(blocking for blocking, _ in problems) and not args.dry_run:
        sys.exit("Resolve the errors above (or use --skip-resource-check for "
                 "disk and RAM) and try again.")

    if not args.offline:
        print(remote_checks(branch, commit))

    existing = find_distribution(build_dir)
    if existing and not args.rebuild:
        print(f"Existing distribution found, skipping the build: {existing}\n"
              "(use --rebuild to build again)")
        return existing

    script, script_text = fetch_automate_script(commit, build_dir, args.dry_run)
    cmd = automate_command(args, script, script_text, build_dir, branch, commit)
    env = dict(os.environ, GN_DEFINES=gn_defines(args))
    env["PATH"] = str(build_dir / "depot_tools") + os.pathsep + env.get("PATH", "")

    print("\nCommand:\n  GN_DEFINES=\"%s\" \\\n  %s" % (env["GN_DEFINES"], " ".join(cmd)))
    if args.dry_run:
        print("\nDry run: nothing was downloaded or built.")
        return None

    subprocess.run(cmd, check=True, env=env, cwd=build_dir)
    result = find_distribution(build_dir)
    if not result:
        sys.exit("error: the build finished but no cef_binary_*_linux64 directory "
                 f"was found under {build_dir}/chromium/src/cef/binary_distrib")
    print(f"\nCEF distribution: {result}")
    return result


def add_arguments(parser):
    parser.add_argument("--cef-build-dir", default=str(DEFAULT_CEF_BUILD_DIR),
                        help="Directory for depot_tools, Chromium and CEF sources "
                        "and the build (no spaces). Default: build/cef_src.")
    parser.add_argument("--fast-build", action="store_true",
                        help="Skip is_official_build and PGO for a faster, less "
                        "optimized build.")
    parser.add_argument("--proprietary-codecs", action="store_true",
                        help="Enable H.264/AAC (licensing restrictions may apply).")
    parser.add_argument("--gn-defines",
                        help="Replace the default GN_DEFINES entirely.")
    parser.add_argument("--no-depot-tools-update", action="store_true",
                        help="Do not update depot_tools (for old Chromium releases).")
    parser.add_argument("--rebuild", action="store_true",
                        help="Build again even if a distribution already exists.")
    parser.add_argument("--skip-resource-check", action="store_true",
                        help="Only warn when disk space or RAM is below the minimum.")
    parser.add_argument("--offline", action="store_true",
                        help="Do not contact GitHub to verify the branch.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show the plan and the command, download and build nothing.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cef-version",
                        help="Full CEF version name (default: CEF_VERSION of CMakeLists.txt).")
    add_arguments(parser)
    result = build_cef(parser.parse_args())
    if result:
        print(f"Next: python tools/prepare.py --cef-root \"{result}\"")


if __name__ == "__main__":
    main()
