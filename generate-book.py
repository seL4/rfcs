#!/usr/bin/env python3

# SPDX-License-Identifier: MIT
# Copyright Rust Language Community

# Based on https://github.com/rust-lang/rfcs

"""
This auto-generates the mdBook SUMMARY.md file based on the layout on the filesystem.

Most RFCs should be kept to a single chapter. However, in some rare cases it
may be necessary to spread across multiple pages. In that case, place them in
a subdirectory with the same name as the RFC. For example:

    0120-my-awesome-feature.md
    0120-my-awesome-feature/extra-material.md

It is recommended that if you have static content like images that you use a similar layout:

    0120-my-awesome-feature.md
    0120-my-awesome-feature/diagram.svg

The chapters are presented in sorted-order.
"""

import os
import subprocess

exceptions = ["README.md"]

def main():
    with open('src/SUMMARY.md', 'w') as summary:
        summary.write('[Introduction](introduction.md)\n\n')
        summary.write('# Implemented RFCs\n\n')
        collect(summary, 'src/implemented', 0)
        summary.write('\n# Active RFCs\n\n')
        collect(summary, 'src/active', 0)
        summary.write('\n# Deferred RFCs\n\n')
        collect(summary, 'src/deferred', 0)

    subprocess.call(['mdbook', 'build'])

def collect(summary, path, depth):
    entries = [e for e in os.scandir(path) if e.name.endswith('.md')]
    entries.sort(key=lambda e: e.name)
    for entry in entries:
        if entry.name in exceptions:
            continue
        indent = '    '*depth
        name = entry.name[:-3]
        title = get_title(entry) or name
        link_path = entry.path[4:]
        summary.write(f'{indent}- [{title}]({link_path})\n')
        maybe_subdir = os.path.join(path, name)
        if os.path.isdir(maybe_subdir):
            collect(summary, maybe_subdir, depth+1)

def get_title(path):
    with open(path, 'r') as f:
        line = f.readline()
        while line and not line.startswith('#'):
            line = f.readline()
        if not line:
            return None
        else:
            return line[2:]

if __name__ == '__main__':
    main()
