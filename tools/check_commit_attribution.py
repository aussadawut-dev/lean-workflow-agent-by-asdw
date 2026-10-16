#!/usr/bin/env python3
"""Reject unpushed commits that carry AI attribution (AGENTS.md Project additions).

Repository development tool; not a portable asset. Only commits that no remote
branch contains are checked: pushed history cannot be fixed by an amend.
"""
import argparse
import re
import subprocess
import sys

ATTRIBUTION = (
    re.compile(r"^\s*co-authored-by:", re.IGNORECASE | re.MULTILINE),
    # An attribution line starts with the phrase, after optional spaces or an emoji;
    # prose that quotes or mentions it mid-line is not attribution.
    re.compile(r"^[\s\U0001F300-\U0001FAFF☀-➿]*generated with \[?(claude|codex)",
               re.IGNORECASE | re.MULTILINE),
)


def unpushed_messages(root):
    """(short hash, message) for commits reachable from HEAD and from no remote branch."""
    output = subprocess.run(["git", "-C", root, "log", "HEAD", "--not", "--remotes", "--format=%h%x00%B%x1e"],
                            check=True, capture_output=True, text=True).stdout
    for record in output.split("\x1e"):
        if record.strip():
            short, _, message = record.strip("\n").partition("\x00")
            yield short, message


def offending(root):
    return [short for short, message in unpushed_messages(root)
            if any(pattern.search(message) for pattern in ATTRIBUTION)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    bad = offending(args.root)
    if bad:
        print("Unpushed commits carry AI attribution (Co-Authored-By or \"Generated with ...\"): "
              + ", ".join(bad) + ". Remove it with `git commit --amend` or a rebase before pushing.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
