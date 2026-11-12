"""Promote one allowlisted scratch file into an agent's retained artifacts.

Usage: python3 -I promote.py <agent-root> <scratch-relative-path> <max-bytes>

Implements the SKILL.md promotion procedure as trusted parent-side code: every
component is walked from a directory descriptor with O_NOFOLLOW, the leaf must
be a regular file with one link and within the byte bound, the copy is re-checked
with fstat, and the destination is created exclusively.
"""

import os
import stat
import sys

NO_FOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def _walk(base: str, components: list[str], *, create: bool) -> int:
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | NO_FOLLOW)
    for component in components:
        if create:
            try:
                os.mkdir(component, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
        child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | NO_FOLLOW, dir_fd=fd)
        os.close(fd)
        fd = child
    return fd


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_ino, info.st_dev, info.st_size, info.st_nlink, info.st_mode)


def promote(agent_root: str, relative: str, limit: int) -> int:
    parts = relative.split("/")
    if relative.startswith("/") or any(part in ("", ".", "..") for part in parts):
        sys.exit("rejected: unsafe relative path")
    source_dir = _walk(os.path.join(agent_root, "scratch"), parts[:-1], create=False)
    source = os.open(parts[-1], os.O_RDONLY | NO_FOLLOW | os.O_NONBLOCK, dir_fd=source_dir)
    before = os.fstat(source)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
        sys.exit("rejected: not a single-link regular file within the bound")
    data = b""
    while len(data) <= before.st_size:
        chunk = os.read(source, 65536)
        if not chunk:
            break
        data += chunk
    if len(data) != before.st_size or _identity(os.fstat(source)) != _identity(before):
        sys.exit("rejected: file changed while reading")
    target_dir = _walk(os.path.join(agent_root, "artifacts"), parts[:-1], create=True)
    target = os.open(
        parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | NO_FOLLOW, 0o600, dir_fd=target_dir
    )
    created = os.fstat(target)
    if not stat.S_ISREG(created.st_mode) or created.st_nlink != 1:
        sys.exit("rejected: destination is not a fresh regular file")
    os.write(target, data)
    os.close(target)
    return len(data)


if __name__ == "__main__":
    agent_root, relative, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
    sys.stdout.write(f"promoted {relative} {promote(agent_root, relative, limit)}\n")
