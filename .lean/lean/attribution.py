"""Reject unpushed commits that carry AI attribution (Co-Authored-By or "Generated with ...").

Only commits that no remote branch contains are checked: pushed history cannot be fixed by an amend.
"""
import re
import subprocess

ATTRIBUTION = (
    re.compile(r"^\s*co-authored-by:", re.IGNORECASE | re.MULTILINE),
    # An attribution line starts with the phrase, after optional spaces or an emoji;
    # prose that quotes or mentions it mid-line is not attribution.
    re.compile(r"^[\s\U0001F300-\U0001FAFF☀-➿]*generated with \[?(claude|codex)", re.IGNORECASE | re.MULTILINE),
)


def unpushed_messages(root):
    """(short hash, message) for commits reachable from HEAD and from no remote branch."""
    output = subprocess.run(["git", "-C", str(root), "log", "HEAD", "--not", "--remotes", "--format=%h%x00%B%x1e"],
                            check=True, capture_output=True, text=True).stdout
    for record in output.split("\x1e"):
        if record.strip():
            short, _, message = record.strip("\n").partition("\x00")
            yield short, message


def offending(root):
    return [short for short, message in unpushed_messages(root)
            if any(pattern.search(message) for pattern in ATTRIBUTION)]


def check(root):
    """Return a refusal message, or "" when no unpushed commit carries attribution."""
    if subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"],
                      capture_output=True).returncode:
        return ""
    bad = offending(root)
    if not bad:
        return ""
    return ("Unpushed commits carry AI attribution (Co-Authored-By or \"Generated with ...\"): " + ", ".join(bad)
            + ". Remove it with `git commit --amend` or a rebase before pushing.")
