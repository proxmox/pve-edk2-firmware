#!/usr/bin/env python3

import os
import sys

if __name__ == '__main__':
    with open('./debian/binary-check.blacklist', 'r') as f:
        blacklist = list(map(lambda s: s.strip(), f.readlines()))

    for path in blacklist:
        sys.stdout.write("Removing %s\n" % (path))
        os.unlink(path)
