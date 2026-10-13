"""Fetching and unpacking the CEF distribution must not trust what it gets (cmake/DownloadCEF.cmake, tools/safe_extract.py).

The cases come from the review of cefpython's pull request 691: the hash of the archive has to be checked every time
the archive is used, also when it is left over from an earlier run, and unpacking must not write outside the
destination. No CEF and no network are needed: the archives are made here and served with file: URLs.
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import safe_extract  # noqa: E402

CMAKE = shutil.which("cmake")
DISTRIBUTION = "cef_binary_t1_testplatform"


def add_file(tar, name, data=b"x", mode=0o644):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    tar.addfile(info, io.BytesIO(data))


def add_link(tar, name, target, hard=False):
    info = tarfile.TarInfo(name)
    info.type = tarfile.LNKTYPE if hard else tarfile.SYMTYPE
    info.linkname = target
    tar.addfile(info)


def make_archive(path, build):
    with tarfile.open(path, "w:bz2") as tar:
        build(tar)


def good(tar):
    add_file(tar, DISTRIBUTION + "/include/cef_version.h", b"#define X 1\n")
    add_file(tar, DISTRIBUTION + "/Release/run.sh", b"#!/bin/sh\n", mode=0o755)
    add_link(tar, DISTRIBUTION + "/Release/current", "run.sh")                     # a link inside is fine
    add_link(tar, DISTRIBUTION + "/Release/up", "../include")                       # also with ".." inside


class SafeExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dest = self.base / "work" / "dest"
        self.archive = self.base / "a.tar.bz2"

    def escaped(self):
        """Files that exist outside the destination (the archive and the destination are not counted)."""
        found = []
        for path in self.base.rglob("*"):
            if path == self.archive or self.dest in path.parents or path == self.dest or path in self.dest.parents:
                continue
            found.append(path.relative_to(self.base).as_posix())
        return found

    def assert_refused(self, build):
        make_archive(self.archive, build)
        with self.assertRaises(safe_extract.UnsafeArchive):
            safe_extract.check_members(tarfile.open(self.archive).getmembers())
        status = safe_extract.main(["safe_extract", str(self.archive), str(self.dest)])
        self.assertEqual(status, 1)
        self.assertFalse(self.dest.exists(), "nothing may be unpacked from an unsafe archive")
        self.assertEqual(self.escaped(), [])

    def test_a_good_archive_is_unpacked_with_its_links_and_modes(self):
        make_archive(self.archive, good)
        self.assertEqual(safe_extract.main(["safe_extract", str(self.archive), str(self.dest)]), 0)
        root = self.dest / DISTRIBUTION
        self.assertEqual((root / "include" / "cef_version.h").read_bytes(), b"#define X 1\n")
        if os.name == "posix":
            self.assertTrue(os.access(root / "Release" / "run.sh", os.X_OK))
            self.assertTrue((root / "Release" / "current").is_symlink())
            self.assertEqual((root / "Release" / "up" / "cef_version.h").read_bytes(), b"#define X 1\n")

    @unittest.skipUnless(os.name == "posix", "POSIX modes")
    def test_special_mode_bits_and_group_write_are_cleared_and_the_exec_bit_is_kept(self):
        def build(tar):
            add_file(tar, "d/setuid", mode=0o4755)
            add_file(tar, "d/writable", mode=0o666)
            add_file(tar, "d/exec", mode=0o775)
            info = tarfile.TarInfo("d/sub")
            info.type = tarfile.DIRTYPE
            info.mode = 0o2777
            tar.addfile(info)
        make_archive(self.archive, build)
        self.assertEqual(safe_extract.main(["safe_extract", str(self.archive), str(self.dest)]), 0)
        modes = {name: (self.dest / "d" / name).stat().st_mode & 0o7777 for name in ("setuid", "writable", "exec")}
        self.assertEqual(modes, {"setuid": 0o755, "writable": 0o644, "exec": 0o755})
        # a directory gets the mode of the archive or the umask (the data filter of Python 3.12 and later), but
        # never a set-gid bit or write access for others
        self.assertEqual((self.dest / "d" / "sub").stat().st_mode & 0o7002, 0)

    def test_a_name_with_dotdot_is_refused(self):
        self.assert_refused(lambda tar: (good(tar), add_file(tar, "../ESCAPED.txt")))

    def test_a_name_that_climbs_out_in_the_middle_is_refused(self):
        self.assert_refused(lambda tar: add_file(tar, DISTRIBUTION + "/a/../../../ESCAPED.txt"))

    def test_an_absolute_name_is_refused(self):
        target = (self.base / "ESCAPED_absolute.txt").as_posix()
        self.assert_refused(lambda tar: add_file(tar, target))

    def test_a_backslash_name_that_climbs_out_is_refused(self):
        self.assert_refused(lambda tar: add_file(tar, "..\\ESCAPED_backslash.txt"))

    def test_a_symbolic_link_out_of_the_destination_is_refused(self):
        self.assert_refused(lambda tar: add_link(tar, DISTRIBUTION + "/link", "../../.."))

    def test_a_file_written_through_a_link_that_points_out_is_refused(self):
        def build(tar):
            add_link(tar, DISTRIBUTION + "/link", "../../..")
            add_file(tar, DISTRIBUTION + "/link/ESCAPED_via_link.txt")
        self.assert_refused(build)

    def test_a_link_to_an_absolute_path_is_refused(self):
        self.assert_refused(lambda tar: add_link(tar, DISTRIBUTION + "/link", "/etc"))

    def test_a_chain_of_links_that_each_look_harmless_is_refused(self):
        # b -> .. is inside (it points at the root); a name that goes through b and then up once more is outside.
        def build(tar):
            add_link(tar, "a/b", "..")
            add_link(tar, "c", "a/b/..")
            add_file(tar, "c/ESCAPED_chain.txt")
        self.assert_refused(build)

    def test_a_hard_link_out_of_the_destination_is_refused(self):
        self.assert_refused(lambda tar: add_link(tar, DISTRIBUTION + "/h", "../../../etc/passwd", hard=True))

    def test_a_device_node_is_refused(self):
        def build(tar):
            info = tarfile.TarInfo(DISTRIBUTION + "/dev")
            info.type = tarfile.CHRTYPE
            tar.addfile(info)
        self.assert_refused(build)

    def test_a_loop_of_links_is_refused_not_followed_forever(self):
        def build(tar):
            add_link(tar, "a", "b")
            add_link(tar, "b", "a")
            add_file(tar, "a/x.txt")
        self.assert_refused(build)

    def test_an_unreadable_archive_gives_status_2(self):
        self.archive.write_bytes(b"not a tar file")
        self.assertEqual(safe_extract.main(["safe_extract", str(self.archive), str(self.dest)]), 2)


@unittest.skipUnless(CMAKE, "cmake is not installed")
class DownloadCefTests(unittest.TestCase):
    """cmake/DownloadCEF.cmake, run in script mode against a directory that plays the part of the CDN."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.cdn = self.base / "cdn"
        self.cdn.mkdir()
        self.downloads = self.base / "downloads"
        self.name = DISTRIBUTION + ".tar.bz2"

    def serve(self, build, sha1=None):
        archive = self.cdn / self.name
        make_archive(archive, build)
        digest = sha1 if sha1 is not None else hashlib.sha1(archive.read_bytes()).hexdigest()
        (self.cdn / (self.name + ".sha1")).write_text(digest)

    def run_cmake(self, version="t1", platform="testplatform"):
        script = self.base / "run.cmake"
        script.write_text('include("%s")\nDownloadCEF("%s" "%s" "%s")\nmessage(STATUS "CEF_ROOT=${CEF_ROOT}")\n'
                          % ((ROOT / "cmake" / "DownloadCEF.cmake").as_posix(), platform, version,
                             self.downloads.as_posix()))
        return subprocess.run(
            [CMAKE, "-DCEF_DOWNLOAD_BASE_URL=" + self.cdn.as_uri(), "-DPython_EXECUTABLE=" + sys.executable,
             "-P", str(script)], capture_output=True, text=True)

    def test_a_good_archive_is_downloaded_checked_and_unpacked(self):
        self.serve(good)
        result = self.run_cmake()
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.downloads / DISTRIBUTION
        self.assertTrue((root / "include" / "cef_version.h").is_file())
        self.assertFalse(list(self.downloads.glob(".unpack-*")), "the temporary directory is removed")
        self.assertFalse(list(self.downloads.glob("*.part")))

    def test_a_second_run_with_the_unpacked_distribution_does_nothing(self):
        self.serve(good)
        self.assertEqual(self.run_cmake().returncode, 0)
        shutil.rmtree(self.cdn)                                     # nothing to download any more
        self.assertEqual(self.run_cmake().returncode, 0)

    def test_a_wrong_hash_stops_the_run_and_leaves_nothing_behind(self):
        self.serve(good, sha1="0" * 40)
        result = self.run_cmake()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA1 mismatch", result.stderr)
        self.assertFalse((self.downloads / self.name).exists(), "the archive must not stay under its real name")
        self.assertFalse((self.downloads / DISTRIBUTION).exists())

    def test_a_wrong_hash_cannot_be_skipped_by_running_again(self):
        # the flaw of file(DOWNLOAD ... EXPECTED_HASH): the file stays, the next run finds it and skips the check
        self.serve(good, sha1="0" * 40)
        for attempt in (1, 2, 3):
            result = self.run_cmake()
            self.assertNotEqual(result.returncode, 0, "run %d unpacked an archive whose hash does not match" % attempt)
            self.assertFalse((self.downloads / DISTRIBUTION).exists())

    def test_an_empty_or_malformed_sha1_file_is_an_error(self):
        for text in ("", "not a hash", "ab" * 10, "z" * 40):
            self.serve(good, sha1=text)
            result = self.run_cmake()
            self.assertNotEqual(result.returncode, 0, repr(text))
            self.assertFalse((self.downloads / DISTRIBUTION).exists(), repr(text))

    def test_a_left_over_archive_that_does_not_match_is_downloaded_again(self):
        self.serve(good)
        self.downloads.mkdir()
        (self.downloads / self.name).write_bytes(b"left over, damaged or planted")
        (self.downloads / (self.name + ".sha1")).write_text(hashlib.sha1(b"something else").hexdigest())
        result = self.run_cmake()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.downloads / DISTRIBUTION / "include" / "cef_version.h").is_file())

    def test_a_matching_hash_does_not_make_an_archive_that_escapes_safe(self):
        # even a matching hash does not make a path-escaping archive safe
        self.serve(lambda tar: add_file(tar, "../ESCAPED_after_hash.txt"))
        result = self.run_cmake()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / "ESCAPED_after_hash.txt").exists())
        self.assertFalse((self.downloads.parent / "ESCAPED_after_hash.txt").exists())
        self.assertFalse((self.downloads / DISTRIBUTION).exists())

    def test_an_archive_with_a_hostile_member_is_not_unpacked_even_if_its_hash_matches(self):
        absolute = self.base / "ESCAPED_absolute_cmake.txt"
        for build in (lambda tar: add_file(tar, absolute.as_posix()),
                      lambda tar: (add_link(tar, DISTRIBUTION + "/l", "../../.."),
                                   add_file(tar, DISTRIBUTION + "/l/ESCAPED_link_cmake.txt"))):
            self.serve(build)
            result = self.run_cmake()
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.downloads / DISTRIBUTION).exists())
            self.assertFalse(absolute.exists())
            shutil.rmtree(self.downloads, ignore_errors=True)
        self.assertEqual(list(self.base.rglob("ESCAPED_link_cmake.txt")), [])

    def test_an_interrupted_unpacking_is_not_taken_for_a_finished_one(self):
        self.serve(lambda tar: add_file(tar, "wrong_name/readme.txt"))     # unpacks, but not the distribution
        result = self.run_cmake()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.downloads / DISTRIBUTION).exists())
        self.assertFalse(list(self.downloads.glob(".unpack-*")))

    def test_a_version_or_platform_that_is_a_path_is_refused(self):
        self.serve(good)
        for version, platform in (("../x", "testplatform"), ("a/b", "testplatform"), ("t1", "../p"), ("t 1", "p")):
            result = self.run_cmake(version=version, platform=platform)
            self.assertNotEqual(result.returncode, 0, (version, platform))
            self.assertIn("Not a CEF", result.stderr)


if __name__ == "__main__":
    unittest.main()
