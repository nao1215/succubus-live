#!/usr/bin/env python3
"""size.py DIR LIMIT: print the bytes of the regular files under DIR and fail past LIMIT.

Symlinks are not followed and not counted; a file or folder that cannot be read fails it. It is Python rather than du, as du -b is GNU only
(macOS's du has no -b) and du counts disk blocks, not the bytes a site or a zip holds.
"""
import os
import stat
import sys


def fail(err):
    raise err


def size(root):
    total = 0
    for top, dirs, files in os.walk(root, onerror=fail):
        dirs[:] = [d for d in dirs if not stat.S_ISLNK(os.lstat(os.path.join(top, d)).st_mode)]
        for name in files:
            st = os.lstat(os.path.join(top, name))
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    return total


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: size.py DIR LIMIT')
    root, limit = sys.argv[1], int(sys.argv[2])
    if not os.path.isdir(root):
        sys.exit(f'{root}: not a directory')
    try:
        total = size(root)
    except OSError as err:
        sys.exit(f'{root}: {err}')
    print(f'{root}: {total} bytes (limit {limit})')
    if total > limit:
        sys.exit(f'{root} is {total - limit} bytes over the limit')


if __name__ == '__main__':
    main()
