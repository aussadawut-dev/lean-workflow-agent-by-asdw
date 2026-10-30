"""Local drift and review receipts; these records are not a security boundary."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .guard import LINE as CONTRACT, initial_head, parse as parse_contract, start_session
from .util import GitView


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def entries(root, skip=lambda name: False, view=None):
    """Bytes, modes and links of every Git-visible path."""
    names = (view or GitView(root)).visible()
    found = []
    for raw in sorted(names):
        name = os.fsdecode(raw)
        path = root / name
        # A retired index path under a moved symlink is represented by the link itself.
        if skip(name) or any((root / parent).is_symlink() for parent in Path(name).parents):
            continue
        if path.is_symlink():
            value = {"link": os.readlink(path)}
        elif path.is_file():
            value = {"sha256": digest(path.read_bytes()), "mode": path.stat().st_mode & 0o777}
        elif path.is_dir():
            # Gitlinks: include untracked submodule work as well as its commit.
            value = {"submodule": state(path)} if (path / ".git").exists() else {"directory": True}
        else:
            value = None
        found.append([name, value])
    return found


def state(root, view=None):
    """Gate cache and change baseline: HEAD, index and all Git-visible bytes, paths, symlinks and modes.

    `view` shares Git answers with other queries of the same unchanged checkout (`util.GitView`).
    """
    view = view or GitView(root)
    head = view.head_text()
    return digest(json.dumps([head, controls(root), view.stage().hex(), entries(root, view=view)],
                            ensure_ascii=True, sort_keys=True).encode())


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def tracker_record(name):
    """Legacy whole-record exclusions; target TCK files are projected, never excluded."""
    path = Path(name)
    target_intake = (len(path.parts) == 6 and path.parts[:2] == (".lean", "targets")
                     and path.parts[3:] == ("docs", "tracking", "INTAKE.md"))
    return (path.parent == Path("docs/tracking") and path.suffix == ".md") or target_intake


TARGET_TRACKER = re.compile(r"\.lean/targets/[^/]+/docs/tracking/(TCK[0-9]{3,})(?:-[a-zA-Z0-9_-]+)?\.md")
TRACKER_SECTIONS = {"Acceptance criteria", "Tasks", "Evidence", "Next step"}


def tracker_projection(name, data):
    """Canonical target trackers minus closure bookkeeping, or None for raw coverage.

    Keep every byte except a valid Status value, checklist markers in acceptance/tasks, and
    Evidence/Next step bodies. Require the standard title, owner and unique closure/checklist
    sections; retain other sections regardless of their names or order. Parse fenced code as
    content, with unclosed fences and ambiguous headings failing closed to raw coverage.
    """
    match = TARGET_TRACKER.fullmatch(name)
    if not match:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\r" in text:
        return None
    lines = text.splitlines(keepends=True)
    if not lines or not re.fullmatch(r"# " + match[1] + r" — \S[^\n]*\n", lines[0]):
        return None
    fenced, fence = set(), None
    for index, line in enumerate(lines):
        marker = re.match(r"^[ ]{0,3}(`{3,}|~{3,})([^\n]*)\n?$", line)
        if fence is not None:
            fenced.add(index)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            if marker[1][0] == "`" and "`" in marker[2]:
                return None
            fence = marker[1]
            fenced.add(index)
    if fence is not None:
        return None
    if any(index not in fenced and re.match(r"^[ \t]*#{1,2}(?!#)", line) and not line.startswith("## ")
           for index, line in enumerate(lines[1:], 1)):
        return None  # Extra titles and indented/malformed section headings are ambiguous.
    from .records import TRACKER_STATES
    statuses = [index for index, line in enumerate(lines) if index not in fenced and line.startswith("Status:")]
    owners = [index for index, line in enumerate(lines) if index not in fenced and line.startswith("Owner:")]
    headings = [(index, line[3:].rstrip("\n")) for index, line in enumerate(lines)
                if index not in fenced and line.startswith("## ")]
    if not headings or len(statuses) != 1 or len(owners) != 1:
        return None
    status, owner = statuses[0], owners[0]
    if (status >= headings[0][0] or owner >= headings[0][0]
            or lines[status] not in {f"Status: {value}\n" for value in TRACKER_STATES}
            or not re.fullmatch(r"Owner: \S[^\n]*\n", lines[owner])):
        return None
    # Duplicate or misspelled mutable headings are not safe to interpret. Other sections remain
    # meaningful and are retained verbatim, including Goal, Decisions and Evidence guidance.
    titles = [title for _, title in headings]
    if len(set(title.strip().casefold() for title in titles)) != len(titles):
        return None
    standard = {title for title in titles if title.strip().casefold() in
                {section.casefold() for section in TRACKER_SECTIONS}}
    if standard != TRACKER_SECTIONS:
        return None
    projected = list(lines)
    projected[status] = "Status: <closure>\n"
    for position, (index, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        if title in ("Evidence", "Next step"):
            projected[index + 1:end] = [""] * (end - index - 1)
        elif title in ("Acceptance criteria", "Tasks"):
            for number in range(index + 1, end):
                if number not in fenced:
                    projected[number] = re.sub(r"^([ \t]*(?:[-+*]|[0-9]+[.)])[ \t]+\[)[ xX](\])",
                                               r"\1 \2", lines[number])
    return "".join(projected).encode("utf-8")


def local_tracker(root, name):
    """Projected bytes and executable bit for a regular file without symlink ancestors."""
    path = root / name
    if (not TARGET_TRACKER.fullmatch(name) or path.is_symlink()
            or any((root / parent).is_symlink() for parent in Path(name).parents)):
        return None
    if not path.is_file():
        return None
    projected = tracker_projection(name, path.read_bytes())
    return (projected, bool(path.stat().st_mode & 0o111)) if projected is not None else None


def tracker_matches_git(root, name, revision):
    """Compare the same projection against stage zero or a committed blob, preserving modes."""
    local = local_tracker(root, name)
    if local is None:
        return False
    if revision == ":":
        listed = git(root, "ls-files", "--stage", "-z", "--", name).split(b"\0")
    else:
        listed = git(root, "--no-replace-objects", "ls-tree", "-z", revision, "--", name).split(b"\0")
    listed = [entry for entry in listed if entry]
    if len(listed) != 1:
        return False
    meta, raw_name = listed[0].split(b"\t", 1)
    fields = meta.decode().split()
    if os.fsdecode(raw_name) != name or fields[0] not in ("100644", "100755"):
        return False
    if revision == ":":
        mode, blob, stage = fields
        if stage != "0":
            return False
    else:
        mode, kind, blob = fields
        if kind != "blob":
            return False
    projected = tracker_projection(name, git(root, "--no-replace-objects", "cat-file", "blob", blob))
    return projected is not None and local == (projected, mode == "100755")


def review_state(root):
    """The reviewed content: Git-visible bytes, modes, links, paths and gate controls.

    Git bookkeeping is left out, so staging or committing keeps this value; `shipping_gap`
    checks that the index and HEAD ship only that content. Submodules keep their full `state`,
    HEAD included. Legacy tracker records are left out; canonical target trackers retain their
    semantic content and file metadata while allowing closure bookkeeping after review.
    """
    found = [entry for entry in entries(root, tracker_record)
             if entry[1] is not None]  # A missing file reads the same deleted, staged or committed.
    for name, value in found:
        if isinstance(value, dict) and "sha256" in value:
            projected = local_tracker(root, name)
            if projected is not None:
                value["tracker"] = digest(projected[0])
                del value["sha256"]
    return digest(json.dumps(["review", controls(root), found], ensure_ascii=True, sort_keys=True).encode())


def head_tree(root):
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD^{tree}"], capture_output=True)
    return head.stdout.decode().strip() if head.returncode == 0 else EMPTY_TREE


def captured_state(root):
    """What a reviewer captures before reading: the reviewed content and HEAD's tree together.

    Binding HEAD here means a commit between capture and recording is refused, so the recorded
    base is the tree the reviewer actually saw.
    """
    return digest(json.dumps(["capture", review_state(root), head_tree(root)]).encode())


def shipping_gap(root, base):
    """Why the index or HEAD would ship something other than the reviewed content, or None.

    `base` is HEAD's tree when the review began. While HEAD is still there, each staged path must
    hold its reviewed working-tree bytes (or be unchanged). Once HEAD moves, the commits must
    contain the whole reviewed content: a partial commit ships a combination nobody reviewed.
    """
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    def names(*args):
        # core.fileMode=true: compare modes even where the repository hides them.
        out = subprocess.check_output(["git", "-C", str(root), "-c", "core.fileMode=true", *args],
                                      stderr=subprocess.PIPE, env=env)
        return {os.fsdecode(name) for name in out.split(b"\0") if name}
    keep = lambda found: sorted(name for name in found if not tracker_record(name))
    if head_tree(root) == base:
        unstaged = names("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z")
        raw = subprocess.check_output(["git", "-C", str(root), "-c", "core.fileMode=true", "diff", "--no-ext-diff", "--no-renames", "--cached",
                                       "--raw", "--full-index", "-z", base], stderr=subprocess.PIPE, env=env).split(b"\0")
        gaps = []
        for meta, raw_name in zip(raw[0::2], raw[1::2]):
            name = os.fsdecode(raw_name)
            if not meta.startswith(b":") or tracker_record(name):
                continue
            deleted = set(meta.split()[3].decode()) == {"0"}
            if ((deleted and os.path.lexists(root / name)) or (not deleted and name in unstaged)) \
                    and not tracker_matches_git(root, name, ":"):
                gaps.append(name)
        return f"staged content differs from the reviewed working tree: {', '.join(gaps)}" if gaps else None
    pending = keep(names("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", "HEAD")
                   | names("diff", "--no-ext-diff", "--no-renames", "--cached", "--name-only", "-z", "HEAD")
                   | names("ls-files", "--others", "--exclude-standard", "-z"))
    pending = [name for name in pending if not (tracker_matches_git(root, name, "HEAD")
                                               and tracker_matches_git(root, name, ":"))]
    return (f"HEAD moved since review without the whole reviewed content: {', '.join(pending)}"
            if pending else None)


def receipt_gap(root, receipt):
    """Why a receipt does not cover the current shipping state, or None."""
    base = receipt.get("base")
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40,64}", base):
        return "the receipt has no reviewed base; the reviewer re-records it"
    if receipt.get("state") != review_state(root):
        return "the shipping state changed since review"
    return shipping_gap(root, base)


# Every module of the CLI is a control: each `lean` call imports several of them, so any one can
# change what the gate or the guard enforces.
CONTROL_NAMES = (".claude/settings.json", ".codex/hooks.json", ".lean/gate.json", ".lean/bin/lean",
                 ".lean/tests/impact.json")  # The impact map decides which tests the gate runs.
PACKAGE = ".lean/lean/"


def control_names(root):
    return list(CONTROL_NAMES) + sorted(str(path.relative_to(root)) for path in (root / PACKAGE).glob("*.py"))
PROJECT = ".lean/PROJECT.md"
TARGET_PROJECT = re.compile(r"\.lean/targets/[^/]+/\.lean/PROJECT\.md")
TRUSTED_LINE = re.compile(r"(?m)^<!-- trusted-control-refs:(.*?)-->[ \t]*$")
TRUSTED_REF = re.compile(r"refs/remotes/[A-Za-z0-9._/-]+")


def project_controls(values, text):
    """Add the PROJECT.md parts that are gate controls: the gate block and any trusted refs line."""
    values["gate"] = text.split("<!-- gate:start -->", 1)[-1].split("<!-- gate:end -->", 1)[0]
    lines = TRUSTED_LINE.findall(text)
    if lines:
        # Absent unless configured, so projects that do not use it keep their recorded baseline.
        values["trusted_control_refs"] = [line.split() for line in lines]
    return values


def controls(root):
    values = {}
    if (root / ".lean").is_symlink():
        raise ValueError(f"symlink boundary: {root / '.lean'}")
    if (root / PACKAGE).is_symlink():
        raise ValueError(f"symlink boundary: {root / PACKAGE}")
    for name in control_names(root):
        path = root / name
        values[name] = {"sha256": digest(path.read_bytes()), "mode": path.stat().st_mode & 0o777} if path.is_file() else None
    # Retained target records stay protected when another target is selected. Reject directory
    # symlinks before globbing and file symlinks before reading any target control bytes.
    if (root / ".lean/targets").is_symlink():
        raise ValueError(f"symlink boundary: {root / '.lean/targets'}")
    for path in sorted((root / ".lean/targets").glob("*/.lean/PROJECT.md")):
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
            raise ValueError(f"symlink boundary: {path}")
        values[str(path.relative_to(root))] = project_controls({}, path.read_text())
    project = root / PROJECT
    return project_controls(values, project.read_text() if project.is_file() else "")


def controls_at(root, commit, extra=()):
    """The controls() view of a commit's tree, so it can be compared with the working tree.

    `extra` names further files to read, such as controls an older baseline recorded under names
    this version no longer uses."""
    def entry(name):
        listed = git(root, "--no-replace-objects", "ls-tree", "-z", commit, "--", name).split(b"\0")[0]
        if not listed:
            return None, None
        meta, _ = listed.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        if kind != "blob":
            return None, None
        if mode not in ("100644", "100755"):
            return {"unsupported": mode}, None  # A symlink or other entry never matches a local file.
        data = git(root, "--no-replace-objects", "cat-file", "blob", blob)
        return {"sha256": digest(data), "mode": int(mode[-3:], 8)}, data

    modules = [os.fsdecode(name) for name in git(root, "--no-replace-objects", "ls-tree", "-z", "--name-only", commit,
                                                 "--", PACKAGE).split(b"\0")]
    names = list(CONTROL_NAMES) + sorted(name for name in modules if fnmatch.fnmatch(name, PACKAGE + "*.py")
                                         and "/" not in name[len(PACKAGE):])
    names += sorted(set(extra) - set(names) - {PROJECT, "gate", "trusted_control_refs"}
                    - {name for name in extra if TARGET_PROJECT.fullmatch(name)})
    values = {name: entry(name)[0] for name in names}
    targets = git(root, "--no-replace-objects", "ls-tree", "-r", "-z", "--name-only", commit,
                  "--", ".lean/targets/").split(b"\0")
    for name in sorted(set(map(os.fsdecode, targets)) | set(extra)):
        if TARGET_PROJECT.fullmatch(name):
            metadata, text = entry(name)
            values[name] = project_controls({}, text.decode()) if text is not None else metadata
    _, project = entry(PROJECT)
    return project_controls(values, project.decode() if project is not None else "")


def comparable(values):
    """Compare file bytes and the executable bit; other permission bits depend on the local umask."""
    return {name: dict(value, mode=bool(value["mode"] & 0o111)) if isinstance(value, dict) and "mode" in value else value
            for name, value in values.items()}


def trusted_match(root, current):
    """Return (ref, commit) when every control equals a configured trusted ref, else None.

    Only remote-tracking refs are accepted: a local branch, tag, HEAD or commit id is whatever
    the agent last wrote. Replace objects are ignored so the ref's own content is compared.
    This is drift detection, not a security boundary; moving a trusted ref (git update-ref,
    a push) still changes what is trusted.
    """
    refs = current.get("trusted_control_refs")
    if not refs:
        return None
    if len(refs) != 1:
        raise ValueError("PROJECT.md must have at most one trusted-control-refs line")
    for ref in refs[0]:
        if not TRUSTED_REF.fullmatch(ref) or ".." in ref or ref.endswith(("/", ".lock")):
            raise ValueError(f"trusted-control-refs accepts only refs/remotes/* names: {ref}")
    names = control_names(root) + [PROJECT]
    if any((root / name).is_symlink() for name in names):
        return None
    for ref in refs[0]:
        if subprocess.run(["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref]).returncode != 0:
            continue
        resolved = subprocess.run(["git", "-C", str(root), "--no-replace-objects", "rev-parse", "--verify", "--quiet",
                                   ref + "^{commit}"], capture_output=True)
        if resolved.returncode != 0:
            continue  # A ref that is not a commit matches nothing; try the next one.
        commit = resolved.stdout.decode().strip()
        if comparable(controls_at(root, commit)) == comparable(current):
            return ref, commit
    return None


def save(path, value):
    if path.parent.is_symlink() or path.is_symlink() or path.with_suffix(".tmp").is_symlink():
        raise ValueError("Evidence state must not cross a symlink boundary")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def human_turn(entry):
    """A person's prompt; runtime-injected skill, hook, task and compaction text is not."""
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    content = entry.get("message", {}).get("content", [])
    texts = [content] if isinstance(content, str) else [
        block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
    return bool(texts) and not texts[0].lstrip().startswith("<task-notification>")


def contract_from_transcript(path):
    """Use only assistant text in the latest human turn, before known write tools."""
    try:
        entries = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    except ValueError as error:
        raise ValueError("Malformed contract transcript: " + str(error)) from error
    start = 0
    for index, entry in enumerate(entries):
        if human_turn(entry):
            start = index + 1
    for entry in entries[start:]:
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        text_seen = False
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") in {"Edit", "Write", "MultiEdit", "apply_patch"}:
                raise ValueError("Task Contract must precede write tools in the current turn")
            if block.get("type") == "text" and not text_seen:
                text = block.get("text", "")
                if text.strip():
                    text_seen = True
                    try:
                        return parse_contract(text.lstrip("\n").split("\n\n", 1)[0])[0]
                    except ValueError:
                        pass
    raise ValueError("No Task Contract first line found in the current turn transcript")


def high_risk_areas(root):
    """Backticked paths in bullets under PROJECT.md's High-risk areas heading."""
    project = root / ".lean/PROJECT.md"
    areas, inside = [], False
    for line in (project.read_text().splitlines() if project.is_file() else []):
        if line.startswith("## "):
            inside = line.strip() == "## High-risk areas"
        elif inside and line.lstrip().startswith("- "):
            areas += [area.removeprefix("./") for area in re.findall(r"`([^`\s]+)`", line)]
    return [area for area in areas if area.strip("/")]


def changed_paths(root, session="", base=None, view=None):
    """Uncommitted, untracked and session-committed paths relative to the root."""
    view = view or GitView(root)
    names = set(view.others())
    if not view.head():
        names |= set(git(root, "ls-files", "--cached", "-z").split(b"\0"))
    else:
        names |= set(git(root, "diff", "--relative", "--name-only", "--no-renames", "-z", "HEAD").split(b"\0"))
        names |= set(git(root, "diff", "--cached", "--relative", "--name-only", "--no-renames", "-z", "HEAD").split(b"\0"))
        if base is None:
            base = initial_head(root, session) if session else None
        if base is None:  # Legacy/direct callers retain the checkout-wide boundary.
            base_file = root / ".agent-runtime/gate-baseline-head"
            base = (base_file.read_text().strip() or None) if base_file.is_file() else None
        if base == "":  # A session that began in an unborn repository owns its first commit too.
            names |= set(git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD").split(b"\0"))
        elif base is not None and re.fullmatch(r"[0-9a-f]{40,64}", base):
            known = subprocess.run(["git", "-C", str(root), "cat-file", "-e", base + "^{commit}"], capture_output=True)
            if known.returncode == 0:
                names |= set(git(root, "diff", "--relative", "--name-only", "--no-renames", "-z", base, "HEAD").split(b"\0"))
    return sorted(os.fsdecode(name) for name in names - {b""})


def matching_risk(paths, areas):
    """Match application-relative paths against the selected project's declared policy."""
    def risky(path):
        for area in areas:
            if any(mark in area for mark in "*?["):
                if fnmatch.fnmatchcase(path, area):
                    return True
            elif path == area.rstrip("/") or path.startswith(area.rstrip("/") + "/"):
                return True
        return False
    return [path for path in paths if risky(path)] if areas else []


def target_high_risk_changes(root, paths, session=""):
    """Use the parent session's original gitlink, even after target and pointer commits.

    If that tree predates the target registration, its whole Git-visible content is new.
    Without a session boundary use the parent HEAD pin (or the initial indexed pin).
    """
    project = Path(paths["project_root"])
    relative = project.relative_to(root).as_posix()
    base = initial_head(root, session) if session else None
    if base is None:
        baseline = root / ".agent-runtime/gate-baseline-head"
        base = baseline.read_text().strip() if baseline.is_file() else "HEAD"
    pin = b""
    def gitlink(value):
        fields = value.split(b"\t", 1)[0].split()
        if fields and fields[0] == b"160000":
            return fields[2 if fields[1] == b"commit" else 1].decode()
        return ""
    # HEAD is optional in a newly initialized parent; explicit recorded baselines are not.
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD^{commit}"],
                          capture_output=True)
    if base and (base != "HEAD" or head.returncode == 0):
        pin = git(root, "--no-replace-objects", "ls-tree", "-z", base, "--", relative)
    if not pin and base == "HEAD":
        pin = git(root, "ls-files", "--stage", "-z", "--", relative)
    target_base = gitlink(pin)
    areas = high_risk_areas(Path(paths["record_root"]))
    if not (project / ".git").exists():
        # Normal clones retain policy records without initializing every application.
        # Only an unchanged pin can be skipped without inspecting its application content.
        pins = [git(root, "ls-files", "--stage", "-z", "--", relative)]
        if head.returncode == 0:
            pins.append(git(root, "--no-replace-objects", "ls-tree", "-z", "HEAD", "--", relative))
        if not areas or all(gitlink(value) == target_base for value in pins):
            return []
        raise ValueError("Changed target submodule is not initialized; initialize it before validation: " + relative)
    if target_base:
        known = subprocess.run(["git", "-C", str(project), "--no-replace-objects", "cat-file", "-e",
                                target_base + "^{commit}"], capture_output=True)
        if known.returncode:
            raise ValueError("Target change baseline is unavailable; restore its Git objects before validation")
    changed = changed_paths(project, base=target_base)
    return [relative + "/" + name for name in matching_risk(changed, areas)]


def high_risk_changes(root, session="", view=None):
    view = view or GitView(root)
    if not view.in_git():
        return []
    found = matching_risk(changed_paths(root, session, view=view), high_risk_areas(root))
    active = root / ".agent-runtime/active-target.json"
    records = root / ".lean/targets"
    if not any(path.exists() or path.is_symlink() for path in (active, records)):
        return sorted(set(found))
    from .target import context, safe_path
    context(root)  # Invalid active selections must still fail instead of falling back.
    # Policies belong to retained application records, independently of which app is selected.
    records = safe_path(root, ".lean/targets")
    for policy in sorted(records.glob("*/.lean/PROJECT.md")):
        safe_path(root, str(policy.relative_to(root)))
        name = policy.parents[1].name
        project = safe_path(root, "targets/" + name)
        safe_path(root, "targets/" + name + "/.git")
        paths = {"project_root": str(project), "record_root": str(policy.parents[1])}
        found += target_high_risk_changes(root, paths, session)
    return sorted(set(found))


def load_receipt(root):
    """Read strict receipt metadata shared by readiness, shipping and controls checks."""
    from .util import read_json
    receipt = read_json(root / ".agent-runtime/review.json")
    fields = ("contract", "reviewer", "evidence", "state", "base", "verdict")
    if (not isinstance(receipt, dict) or type(receipt.get("schema")) is not int or receipt.get("schema") != 1
            or any(not isinstance(receipt.get(field), str) or not receipt[field].strip() for field in fields)):
        raise ValueError("Review receipt is malformed")
    return receipt


def check_review(root, contract):
    receipt = load_receipt(root)
    reasons = []  # Name what differs, so the reviewer can fix the receipt in one step.
    if receipt.get("verdict") != "PASS":
        reasons.append(f"its verdict is {receipt.get('verdict')!r}, not PASS")
    if receipt.get("contract") != contract:
        reasons.append(f"its contract {receipt.get('contract')!r} is not the exact contract {contract!r}; "
                       "the reviewer re-records with that exact line")
    gap = receipt_gap(root, receipt)
    if gap:
        reasons.append(gap)
    if reasons:
        raise ValueError("Review receipt does not cover the current contract and shipping state: " + "; ".join(reasons))


def check_shipped(root):
    """A PASS receipt for exactly this shipping state, under any contract.

    The High-risk floor asks that the delta which ships was independently reviewed; a later
    contract that changes nothing (a status reply, say) ships that same reviewed state.
    """
    receipt = load_receipt(root)
    contract = CONTRACT.fullmatch(str(receipt.get("contract", "")))
    # Only a review at HIGH depth stands in for the floor: a PASS under a lower contract (a typo or a
    # receipt the author wrote) never required an independent reviewer.
    high = contract and (contract.group(1) == "HIGH" or contract.group(2) == "VERY_HIGH")
    if receipt.get("verdict") != "PASS" or receipt_gap(root, receipt) or not high:
        raise ValueError("No HIGH-depth PASS review receipt covers the current shipping state")


def reviewed_controls(root, old, current, contract):
    """(reviewer, contract, state) of a PASS receipt for `contract` that reviewed the whole control change, or None.

    The receipt must be for the session contract at HIGH depth. The contract guard stops the
    author's main thread recording a receipt for the contract it has declared, not one for a
    contract it declares later, so this is attestation-level evidence like any receipt. Its state binds the current control bytes, and its base is
    HEAD's tree when the review began, so the reviewed diff runs from base to now. Each changed
    control must start that diff at its accepted value and be visible to Git: a control change
    committed before the review began (edited again or not) or an ignored control is not
    accepted. The receipt is attestation-level evidence, like any receipt; the manual
    accept-controls procedure stays for an unreviewed change.
    """
    if not contract or not isinstance(old, dict):
        return None
    try:
        check_shipped(root)
        check_review(root, contract)
        receipt = load_receipt(root)
        names = set(current) | set((old.get("controls") or {}))
        base = comparable(controls_at(root, receipt["base"], names))
    except (OSError, ValueError, AttributeError, TypeError, KeyError, subprocess.CalledProcessError):
        return None
    now, accepted = comparable(current), comparable(old.get("controls") or {})
    for name in set(now) | set(base) | set(accepted):
        if now.get(name) == accepted.get(name):
            continue
        # The reviewed diff runs from base to now, so it shows the whole change only when it starts
        # at the accepted value and Git shows the file at all (an ignored control never appears).
        path = PROJECT if name in ("gate", "trusted_control_refs") else name
        if base.get(name) != accepted.get(name) or not git_visible(root, path):
            return None
    return str(receipt.get("reviewer")), str(receipt.get("contract")), str(receipt.get("state", ""))


def git_visible(root, name):
    """Whether Git shows this path in a diff: tracked, or untracked and not ignored."""
    try:
        listed = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", name)
        deleted = git(root, "ls-tree", "-z", "--name-only", "HEAD", "--", name)
    except subprocess.CalledProcessError:
        return False
    return bool(listed.strip(b"\0") or deleted.strip(b"\0"))


class ControlsChanged(ValueError):
    """Controls differ from the accepted ones and nothing (trusted ref, HIGH receipt) covers them yet."""


def guard_controls(root, contract=None, reason=None):
    """Refuse changed controls before running checks; reason records existing user approval."""
    path = root / ".agent-runtime/gate-controls.json"
    current = controls(root)
    if reason is not None:
        if not reason.strip():
            raise ValueError("User approval reason is required")
        old = json.loads(path.read_text()) if path.exists() else None
        history = old.get("history", []) if old else []
        history.append({"before": old.get("controls") if old else None,
                        "after": current, "reason": reason})
        save(path, {"schema": 1, "controls": current, "history": history})
    elif not path.exists():
        save(path, {"schema": 1, "controls": current, "history": []})
    else:
        old = json.loads(path.read_text())
        if old.get("controls") != current:
            match = trusted_match(root, current)
            if match is not None:
                ref, commit = match
                reason = f"automatic: controls match trusted ref {ref} at {commit}"
                note = f"Gate evidence: protected gate controls accepted; they match {ref} ({commit[:12]})."
            else:
                reviewed = reviewed_controls(root, old, current, contract)
                if reviewed is None:
                    hint = (" No trusted-control-refs entry matches them." if current.get("trusted_control_refs") else "")
                    raise ControlsChanged("Protected gate controls changed. Inspect the diff; use accept-controls --reason "
                                     "only for an already user-approved change, or let an independent HIGH-depth "
                                     "PASS review cover the change." + hint)
                reviewer, contract, receipt_state = reviewed
                reason = (f"automatic: independent HIGH-depth review PASS by {reviewer} for {contract} covers "
                          f"these controls (receipt state {receipt_state[:12]})")
                note = (f"Gate evidence: protected gate controls accepted; an independent HIGH-depth PASS review "
                        f"by {reviewer} covers them.")
            history = old.get("history", []) + [{"before": old.get("controls"), "after": current, "reason": reason}]
            save(path, {"schema": 1, "controls": current, "history": history})
            print(note, file=sys.stderr)


class StrictParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(prog="lean evidence", description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", type=Path, default=root or Path.cwd())
    # Subcommand parsers take the same class: an abbreviation such as --contr must not stand in for
    # --contract, whose exact value the contract guard compares.
    commands = parser.add_subparsers(dest="command", required=True, parser_class=StrictParser)
    guard = commands.add_parser("guard-controls")
    guard.add_argument("--contract", help="the session's Task Contract, so a review receipt for it can accept drift")
    accept = commands.add_parser("accept-controls")
    accept.add_argument("--reason", required=True)
    commands.add_parser("state", help="the shipping state a review receipt covers")
    commands.add_parser("gate-state", help="the state a gate cache and change baseline cover")
    high_risk = commands.add_parser("high-risk")
    high_risk.add_argument("--session", default="")
    seed = commands.add_parser("seed-session")
    seed.add_argument("--session", required=True)
    commands.add_parser("check-shipped")
    transcript = commands.add_parser("contract")
    transcript.add_argument("--transcript", required=True)
    field = commands.add_parser("hook-field")
    field.add_argument("--field", choices=("stop_hook_active", "transcript_path", "session_id"), required=True)
    for name in ("record-review", "check-review"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--contract", required=True)
        if name == "record-review":
            cmd.add_argument("--reviewer", required=True)
            cmd.add_argument("--evidence", required=True)
            cmd.add_argument("--verdict", choices=("PASS", "REWORK"), required=True)
            cmd.add_argument("--state", required=True, help="SHA-256 state captured before review")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command in {"guard-controls", "accept-controls"}:
            guard_controls(root, args.contract if args.command == "guard-controls" else None,
                           args.reason if args.command == "accept-controls" else None)
        elif args.command == "state":
            print(captured_state(root))
        elif args.command == "gate-state":
            print(state(root))
        elif args.command == "seed-session":
            start_session(root, args.session, state(root))
        elif args.command == "check-shipped":
            check_shipped(root)
        elif args.command == "high-risk":
            for path in high_risk_changes(root, args.session):
                print(path)
        elif args.command == "contract":
            print(contract_from_transcript(args.transcript))
        elif args.command == "hook-field":
            payload = json.load(sys.stdin)
            value = payload.get(args.field, False if args.field == "stop_hook_active" else "")
            if args.field == "stop_hook_active":
                if not isinstance(value, bool):
                    raise ValueError("stop_hook_active must be a boolean")
                print("1" if value else "0")
            else:
                if not isinstance(value, str) or "\n" in value:
                    raise ValueError(f"{args.field} must be a single-line string")
                print(value)
        else:
            if not CONTRACT.fullmatch(args.contract):
                raise ValueError("A real Task Contract is required")
            if args.command == "record-review":
                if not args.reviewer.strip() or not args.evidence.strip():
                    raise ValueError("Reviewer identity and review evidence are required")
                if args.state != captured_state(root):
                    raise ValueError("Shipping state or HEAD changed since review began; review the new delta "
                                     "(capture it with `lean evidence state`)")
                current, base = review_state(root), head_tree(root)
                save(root / ".agent-runtime/review.json", {"schema": 1, "contract": args.contract,
                     "state": current, "base": base, "reviewer": args.reviewer, "verdict": args.verdict,
                     "evidence": args.evidence})
                from . import activity
                activity.record(root, "review", verdict=args.verdict, reviewer=args.reviewer, contract=args.contract)
            else:
                check_review(root, args.contract)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.CalledProcessError) as error:
        print("Gate evidence: " + str(error), file=sys.stderr)
        return 2
    return 0

