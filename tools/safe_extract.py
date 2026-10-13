"""Unpack a tar archive only if no member can write outside the destination.

Usage: python tools/safe_extract.py ARCHIVE DEST

cmake/DownloadCEF.cmake runs it for the CEF binary distribution. `cmake -E tar` writes `../x`, absolute names and
files behind a symbolic link that points out of the destination wherever they lead, and the hash of the archive only
says that it is the archive the server published. Every member is checked before anything is written:

- a name must be relative and must not climb above the destination, also after the symbolic links of earlier
  members are followed (`a/b` -> `..` and then `a/b/..` leaves the destination, though the name looks harmless);
- a symbolic link or a hard link must point inside the destination (an absolute target never does);
- only files, directories and links are unpacked: no device nodes, no FIFOs.

The modes are cut to `mode & 0o755` (no set-uid, set-gid or sticky bit, no write for group and others, as with umask
022), so the result is the same as `cmake -E tar` gave. Python 3.12 and later (and 3.11.4 and later) also get the `data`
filter of `tarfile`; the own checks above make older Pythons safe too.

Exit status: 0 unpacked, 1 an unsafe archive (nothing is unpacked), 2 the archive cannot be read.
"""

import posixpath
import sys
import tarfile
from pathlib import Path

MAX_LINK_STEPS = 64            # symbolic links followed for one name; a loop ends here


class UnsafeArchive(Exception):
    """A member would leave the destination or is of a kind that is not unpacked."""


def _parts(name):
    """The components of a member name; a backslash separates too (Windows)."""
    return [part for part in name.replace("\\", "/").split("/")]


def _resolve(links, base, name):
    """The components of `name` relative to the directory `base` (a list), with the symbolic links in `links` followed.

    Raises UnsafeArchive if the result leaves the destination.
    """
    if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        raise UnsafeArchive("absolute name %r" % name)
    stack = list(base)
    todo = _parts(name)
    steps = 0
    while todo:
        part = todo.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not stack:
                raise UnsafeArchive("%r leaves the destination" % name)
            stack.pop()
            continue
        stack.append(part)
        target = links.get("/".join(stack))
        if target is not None:
            steps += 1
            if steps > MAX_LINK_STEPS:
                raise UnsafeArchive("too many symbolic links in %r" % name)
            stack.pop()                  # the link is replaced by its target, read from the directory of the link
            todo = _parts(target) + todo
    return stack


def check_members(members):
    """The members of a tar archive in order; raises UnsafeArchive for the first one that is not safe."""
    links = {}                           # path of a symbolic link (relative, resolved) -> its target as written
    for member in members:
        name = member.name
        if not (member.isreg() or member.isdir() or member.issym() or member.islnk()):
            raise UnsafeArchive("%r is a special file" % name)
        if member.issym():
            parent = _resolve(links, [], posixpath.dirname(name.replace("\\", "/")))
            target = member.linkname
            if target.startswith(("/", "\\")) or (len(target) > 1 and target[1] == ":"):
                raise UnsafeArchive("%r links to the absolute path %r" % (name, target))
            _resolve(links, parent, target)          # the target must stay inside, however the links lead
            leaf = posixpath.basename(name.replace("\\", "/"))
            links["/".join(parent + [leaf])] = target
        elif member.islnk():
            _resolve(links, [], member.linkname)     # the name of a hard link is relative to the archive root
            _resolve(links, [], name)
        else:
            _resolve(links, [], name)


def safe_extract(archive, dest):
    """Unpack `archive` into the directory `dest` (made if missing) after checking every member."""
    dest = Path(dest)
    with tarfile.open(archive, "r:*") as tar:
        members = tar.getmembers()
        check_members(members)
        for member in members:
            member.mode &= 0o755         # no set-uid, set-gid or sticky bit, no write for group and others (umask 022)
        dest.mkdir(parents=True, exist_ok=True)
        kwargs = {}
        if hasattr(tarfile, "data_filter"):
            kwargs["filter"] = "data"
        tar.extractall(dest, members=members, **kwargs)


def main(argv):
    if len(argv) != 3:
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        return 2
    try:
        safe_extract(argv[1], argv[2])
    except UnsafeArchive as error:
        print("error: unsafe archive, nothing was unpacked: %s" % error, file=sys.stderr)
        return 1
    except (OSError, tarfile.TarError) as error:
        print("error: cannot unpack %s: %s" % (argv[1], error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
