"""Quality Gate: run PROJECT.md checks with contract, review and drift evidence.

One runner serves direct runs and both providers' lifecycle hooks. A cache is opt-in
(--cache-tree) for checks that depend only on Git-visible files; refusals never become passes.
Local receipts catch drift, not hostile writers.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from . import evidence, guard
from .util import LeanError, in_git, locked, read_json, safe_path, write_json

MODES = ("auto", "manual", "auto_fixloop", "manual_fixloop")
MAX_REFUSALS = 3
LOCK_ENV = "LEAN_GATE_LOCK_FD"
FORCE_ENV = "LEAN_GATE_FORCE"
GATE_FILE = ".lean/gate.json"
HIGH_REVIEW = re.compile(r"Contract: (?:risk=HIGH quality=|risk=(?:LOW|MEDIUM) quality=VERY_HIGH acceptance=)")


# --- Gate automation mode -------------------------------------------------------------------

def read_mode(root):
    """(mode, auto, fixloop, configured); an absent file keeps automatic checks."""
    path = safe_path(root, GATE_FILE)
    if not path.exists():
        return "auto", True, False, False
    config = read_json(path)
    if (not isinstance(config, dict) or "auto" not in config or not set(config) <= {"auto", "fixloop"}
            or type(config["auto"]) is not bool or type(config.get("fixloop", False)) is not bool):
        raise LeanError("gate policy must contain only auto (and optional fixloop) JSON booleans")
    auto, fixloop = config["auto"], config.get("fixloop", False)
    return ("auto" if auto else "manual") + ("_fixloop" if fixloop else ""), auto, fixloop, True


def write_mode(root, mode):
    if mode not in MODES:
        raise LeanError(f"unsupported gate mode: {mode}")
    with locked(root, "gate-mode.lock"):
        read_mode(root)  # Invalid settings need investigation, not silent repair.
        payload = {"auto": mode.startswith("auto")}
        if mode.endswith("_fixloop"):
            payload["fixloop"] = True
        write_json(safe_path(root, GATE_FILE), payload)


def policy(mode):
    run = "python3 .lean/bin/lean gate run"
    if mode == "auto":
        return ("Lean Quality Gate auto=true: run the shared gate at work completion without asking. "
                "DONE still requires acceptance, current validation and required semantic review.")
    if mode == "auto_fixloop":
        return ("Lean Quality Gate mode=auto_fixloop (auto=true, fixloop=true): run the shared gate at work "
                "completion without asking. If any gate check fails, auto-loop: fix all actionable code, test "
                "and lint failures and re-run the gate until it passes without asking the user, stopping only "
                "for genuine requirement/design questions or missing environment tools. DONE still requires "
                "acceptance, current validation and required semantic review.")
    if mode == "manual_fixloop":
        return ("Lean Quality Gate mode=manual_fixloop (auto=false, fixloop=true): automatic validation NOT_RUN. "
                "Run focused checks; always get user authorization (reuse matching approval for this workset or "
                f"batch) before starting the full gate: {run} with --contract and --require-review when "
                "required. Once authorized, if any gate check fails, auto-loop: fix all actionable code, test and "
                "lint failures and re-run the gate until it passes without asking again between rounds, stopping "
                "only for genuine requirement/design questions or missing environment tools. Deferred validation "
                "is not a pass: stay VALIDATING/BLOCKED until the gate and required review cover the shipping state.")
    return ("Lean Quality Gate auto=false: automatic validation NOT_RUN. Run focused checks; get user "
            "authorization (reuse matching approval for this workset or batch) before the full gate: "
            f"{run} with --contract and --require-review when required. Deferred validation is not a pass: "
            "stay VALIDATING/BLOCKED until the gate and required review cover the shipping state.")


# --- Checkout lock ----------------------------------------------------------------------------

def lock_file(root, create=False):
    """A plain, singly linked lock file under the runtime directory, opened without following links."""
    runtime = Path(root) / ".agent-runtime"
    if create:
        runtime.mkdir(exist_ok=True)
    directory = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open("quality-gate.lock", os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if create else 0),
                             0o600, dir_fd=directory)
    finally:
        os.close(directory)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise ValueError("gate lock must be a plain file with one link")
    return descriptor


def inherited_lock(root):
    """Whether this process already holds the checkout lock through an inherited descriptor."""
    opened = None
    try:
        descriptor = int(os.environ.get(LOCK_ENV, ""))
        actual = os.fstat(descriptor)
        opened = lock_file(root)
        expected = os.fstat(opened)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            return False
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, ValueError):
        return False
    finally:
        if opened is not None:
            os.close(opened)


def acquire_lock(root):
    """Hold the checkout lock for this process and its checks; return an error message or None."""
    if inherited_lock(root):
        return None
    try:
        descriptor = lock_file(root, create=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return "Quality Gate busy: another gate is running in this checkout; validation NOT_RUN. Retry after it finishes."
    except (OSError, ValueError) as error:
        return f"Quality Gate lock unavailable: {error}; validation NOT_RUN."
    os.set_inheritable(descriptor, True)
    os.environ[LOCK_ENV] = str(descriptor)
    return None


# --- Runner -----------------------------------------------------------------------------------

def gate_commands(project):
    """Commands between the gate markers; raises LeanError for malformed markers."""
    commands, starts, ends, inside, invalid = [], 0, 0, False, False
    for line in project.read_text().splitlines():
        if "<!-- gate:start -->" in line:
            starts += 1
            inside = True
            continue
        if "<!-- gate:end -->" in line:
            ends += 1
            invalid = invalid or not inside
            inside = False
        if inside and not line.startswith("```") and not re.match(r"[ \t]*(#|$)", line):
            commands.append(line)
    if starts != 1 or ends != 1 or invalid:
        raise LeanError("Quality Gate undefined: malformed gate markers.")
    return commands


def missing_tool(command, status):
    """The plain command name a 127 exit could not resolve, or None (wrappers keep the failure)."""
    if status != 127:
        return None
    lookup = command
    while True:
        match = re.match(r"[ \t]*[A-Za-z_][A-Za-z0-9_]*=\S*[ \t]+(.*)$", lookup)
        if not match:
            break
        lookup = match.group(1)
    first = lookup.split()[0] if lookup.split() else ""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+:@-]*", first):
        return None
    found = subprocess.run(["bash", "-c", 'command -v -- "$1"', "bash", first], capture_output=True)
    return None if found.returncode == 0 else first


class Run:
    """One gate run. `out` collects stdout (hook JSON), `err` the refusal text."""

    def __init__(self, root, hook=False, seed=False, cache_tree=False, require_review=False, quiet=False,
                 contract="", session="", payload=None, show=None):
        self.root = Path(root).resolve()
        self.hook, self.seed, self.cache_tree = hook, seed, cache_tree
        self.require_review, self.quiet = require_review, quiet or hook  # No one watches a Stop live.
        self.contract, self.session = contract, session
        self.payload = payload if payload is not None else {}
        self.show = show  # Optional callable for live progress lines.
        self.out, self.err, self.checks = [], [], 0
        runtime = self.root / ".agent-runtime"
        self.cache, self.failed = runtime / "gate-cache", runtime / "gate-failed"
        self.baseline, self.refusal = runtime / "gate-baseline", runtime / "gate-refusal"
        self.active, self.transcript = False, ""

    def say(self, message):
        self.err.append(message)

    def progress(self, message):
        if not self.quiet:
            line = f"Quality Gate: {message}"
            if self.show:
                self.show(line)
            else:
                print(line, file=sys.stderr, flush=True)

    def refuse(self, kind=""):
        """Record a refusal; return 0 when the Stop is released UNVERIFIED instead of blocked.

        A continuation adds to the count; a fresh Stop starts it at 1. A contract refusal says
        nothing about the code, so it keeps the passing cache. After MAX_REFUSALS continued
        refusals, or the same refusal shown again to this session, the Stop is released so the
        agent can report BLOCKED instead of looping; a release never writes a cache or receipt.
        """
        if kind != "c" and not self.seed:
            self.cache.unlink(missing_ok=True)
        if not self.hook or self.seed:
            return 2
        count = 0
        if self.active and self.failed.is_file():
            raw = self.failed.read_text().lstrip("c")
            count = int(raw) if raw.isdigit() else 0
        count += 1
        self.failed.parent.mkdir(exist_ok=True)
        self.failed.write_text(f"{kind}{count}")
        if kind != "c" and self.session:
            try:
                current = evidence.state(self.root)
            except (OSError, ValueError, subprocess.CalledProcessError):
                current = ""
            if current:
                reason = hashlib.sha256("\n".join(self.err).encode()).hexdigest()
                fingerprint = f"{self.session} {current} {reason} {self.contract}"
                if self.refusal.is_file() and self.refusal.read_text() == fingerprint:
                    self.out.append(json.dumps({"systemMessage": "Lean Quality Gate refused again with nothing "
                                                "changed since the last refusal; Stop released UNVERIFIED. The work "
                                                "is not DONE; see that refusal."}))
                    return 0
                self.refusal.write_text(fingerprint)
        if count > MAX_REFUSALS:
            self.out.append(json.dumps({"systemMessage": f"Lean Quality Gate still refused after {MAX_REFUSALS} "
                                        "attempts; Stop released UNVERIFIED. The work is not DONE; see the last "
                                        "gate refusal."}))
            return 0
        return 2

    def target_checks(self):
        """Run the selected application's gate in its own directory; a refusal code or None."""
        import contextlib
        import io
        from . import target
        captured = io.StringIO()
        try:
            with contextlib.redirect_stderr(captured):
                code = target.gate(self.root, optional=True, quiet=self.quiet, session=self.session)
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
            self.say(captured.getvalue().rstrip() + ("\n" if captured.getvalue() else "") + f"target error: {error}")
            return self.refuse()
        if code:
            self.say(captured.getvalue().rstrip())
            return self.refuse()
        if not self.quiet:
            sys.stderr.write(captured.getvalue())
        return None

    def gate_refused(self):
        return self.failed.is_file() and not self.failed.read_text().startswith("c")

    def execute(self):
        try:
            return self._execute()
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            self.say(f"Gate evidence: {error}")
            return self.refuse()

    def _execute(self):
        root = self.root
        if self.hook and not self.seed:
            active = self.payload.get("stop_hook_active", False)
            if not isinstance(active, bool):
                raise LeanError("stop_hook_active must be a boolean")
            self.active = active
            for name in ("transcript_path", "session_id"):
                value = self.payload.get(name, "")
                if not isinstance(value, str) or "\n" in value:
                    raise LeanError(f"{name} must be a single-line string")
            self.transcript = self.payload.get("transcript_path", "")
            self.session = self.payload.get("session_id", "") or self.session
        elif self.seed:
            value = self.payload.get("session_id", "")
            if not isinstance(value, str) or "\n" in value:
                raise LeanError("session_id must be a single-line string")
            self.session = value or self.session
            if self.session:
                guard.start_session(root, self.session, evidence.state(root))
        # The contract the session declared through the guard; only a receipt for it can accept
        # changed controls. For a hook Stop it is the session's contract; the transcript is a fallback.
        session_contract = (guard.current(root, self.session) or "") if self.session else ""
        declared = ""
        if self.hook and not self.contract and session_contract:
            declared = self.contract = session_contract
        try:
            evidence.guard_controls(root, session_contract or None)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            self.say(f"Gate evidence: {error}")
            try:
                pending = evidence.high_risk_changes(root, self.session)
            except (OSError, ValueError, subprocess.CalledProcessError):
                pending = []
            if pending:
                self.say("After that, HIGH independent review is also required for these High-risk changes:\n"
                         + "\n".join(pending))
            return self.refuse()
        selection = root / ".agent-runtime/active-target.json"
        if not self.seed and (selection.exists() or selection.is_symlink()):
            self.progress("target checks started")
            refused = self.target_checks()
            if refused is not None:
                return refused
            self.progress("target checks passed")
        project = root / ".lean/PROJECT.md"
        if not project.is_file():
            self.say("Quality Gate undefined: missing .lean/PROJECT.md; run /lean-init.")
            return self.refuse()
        try:
            commands = gate_commands(project)
        except LeanError as error:
            self.say(str(error))
            return self.refuse()
        if not commands:
            self.say("Quality Gate undefined: configure checks in .lean/PROJECT.md; no validation passed.")
            return self.refuse()
        self.checks = len(commands)
        git_tree = in_git(root)
        state = evidence.state(root) if self.hook and git_tree else ""
        # A direct --cache-tree run fingerprints the state only for its pass record: it never
        # compares with the session baseline, so the High-risk floor still covers it.
        pass_state = evidence.state(root) if (not self.hook and self.cache_tree and git_tree) else state
        if self.seed:
            # SessionStart records a change baseline, never a passing cache. A new session has not
            # seen any earlier refusal, so its first one blocks again.
            self.refusal.unlink(missing_ok=True)
            if self.gate_refused():
                return 0
            self.failed.unlink(missing_ok=True)
            if state:
                self.baseline.parent.mkdir(exist_ok=True)
                self.baseline.write_text(state)
                head_file = self.baseline.with_name("gate-baseline-head")
                head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"],
                                      capture_output=True, text=True)
                if head.returncode == 0:
                    head_file.write_text(head.stdout)
                else:
                    head_file.unlink(missing_ok=True)
            return 0
        # A baseline can identify chat-only turns; it is never proof of validation.
        changed = not (state and any(path.is_file() and path.read_text() == state
                                     for path in (self.baseline, self.cache)))
        if self.hook and not declared and self.transcript:
            if not os.access(self.transcript, os.R_OK):
                self.say(f"Contract transcript unreadable: {self.transcript}")
                return self.refuse("c")
            try:
                self.contract = evidence.contract_from_transcript(self.transcript)
            except ValueError as error:
                if changed:
                    self.say(f"Gate evidence: {error}")
                    return self.refuse("c")
        if HIGH_REVIEW.match(self.contract or ""):
            self.require_review = True
        # PROJECT.md High-risk areas set a review floor that a self-declared risk cannot lower.
        risky = evidence.high_risk_changes(root, self.session) if (changed or self.session) else []

        def receipt_gap():
            """A refusal for a missing receipt, or None. A HIGH contract needs a receipt for itself;
            the High-risk floor needs only that the shipping state was reviewed at HIGH depth."""
            try:
                if self.require_review:
                    evidence.check_review(root, self.contract)
                elif risky:
                    try:
                        evidence.check_review(root, self.contract)
                    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
                        evidence.check_shipped(root)
                return None
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
                self.say(f"Gate evidence: {error}")
                if risky:
                    self.say("High-risk areas changed; HIGH independent review is required:\n" + "\n".join(risky))
                return self.refuse()

        # Only a real passing run can be cached; contracts and HIGH review are checked first. A direct
        # run's record is marked: it skips the commands but never makes changed work count as unchanged.
        if (self.cache_tree and pass_state and not self.failed.exists() and self.cache.is_file()
                and self.cache.read_text() in (pass_state, f"direct {pass_state}")):
            refused = receipt_gap()
            if refused is not None:
                return refused
            if self.hook:
                self.cache.write_text(pass_state)
            self.progress("checks reused for the unchanged shipping state")
            return 0
        fixloop = False
        try:
            fixloop = read_mode(root)[2]
        except (OSError, ValueError):
            pass
        environment = dict(os.environ)
        for number, command in enumerate(commands, 1):
            self.progress(f"check {number} started ({number}/{len(commands)}) {bar(number - 1, len(commands))}")
            started = time.monotonic()
            result = subprocess.run(["bash", "-c", command], cwd=root, env=environment, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    pass_fds=lock_fds())
            if result.returncode == 0:
                self.progress(f"check {number} passed ({int(time.monotonic() - started)}s) "
                              f"{bar(number, len(commands))}")
                continue
            tail = "\n".join(result.stdout.splitlines()[-40:])
            tool = missing_tool(command, result.returncode)
            if tool:
                self.say(f"Quality Gate could not run: {command}\n{tail}\n'{tool}' is not available in this "
                         "environment, so this check never ran. That is a missing tool, not a failure your change "
                         "caused. Do not edit code, the gate, or the tests to get past it: report BLOCKED, name the "
                         "gate command that could not run and the tool it needs, say the change is unverified by "
                         "that command, and do not declare DONE.")
            elif fixloop:
                self.say(f"Quality Gate failed: {command}\n{tail}\nFixloop mode is active: fix all actionable "
                         "code, test and lint failures and re-run the Quality Gate until it passes without asking "
                         "the user, stopping only for a genuine requirement/design question. Do not declare DONE "
                         "until the gate passes.")
            else:
                self.say(f"Quality Gate failed: {command}\n{tail}\nIf your change caused this, fix it. If it was "
                         "already failing or is outside the task, do not touch it: report BLOCKED and ask. Do not "
                         "declare DONE.")
            return self.refuse()
        refused = receipt_gap()
        if refused is not None:
            return refused
        # A pass ends any standing refusal; a run that fingerprinted the state records the pass.
        if self.hook or pass_state:
            self.failed.unlink(missing_ok=True)
            self.refusal.unlink(missing_ok=True)
        if pass_state:
            self.cache.parent.mkdir(exist_ok=True)
            self.cache.write_text(pass_state if self.hook else f"direct {pass_state}")
        return 0


def lock_fds():
    try:
        return (int(os.environ[LOCK_ENV]),)
    except (KeyError, ValueError):
        return ()


def bar(done, total):
    from .progress import render
    return render(done / total if total else 1.0, width=10, percent=False)


def run(root, **options):
    """Run the gate under the checkout lock; return (exit code, stdout lines, stderr lines)."""
    message = acquire_lock(root)
    if message:
        return 2, [], [message]
    gate = Run(root, **options)
    began = time.monotonic()
    code = gate.execute()
    if not gate.seed:
        from . import activity
        result = "pass" if code == 0 and not gate.out else "released" if code == 0 else "refused"
        reason = next((line for message in gate.err for line in message.splitlines() if line.strip()), "")
        activity.record(gate.root, "gate", result=result, checks=gate.checks, seconds=round(time.monotonic() - began, 1),
                        hook=gate.hook or None, reason=reason[:200] if code else None)
    return code, gate.out, gate.err


def status(root, verify=True):
    """Last recorded gate result from the runner's markers, never a fresh validation.

    Verifying hashes every Git-visible file; a status bar refreshing often passes verify=False and
    reports a recorded pass as LAST_PASS without checking it still matches."""
    runtime = Path(root) / ".agent-runtime"
    failed, cache = runtime / "gate-failed", runtime / "gate-cache"
    if failed.is_file():
        # A "c" marker is a contract refusal, which says nothing about the checks.
        return "CONTRACT_REFUSED" if failed.read_text().startswith("c") else "FAIL"
    if not cache.is_file():
        return "NOT_RUN"
    if not verify:
        return "LAST_PASS"
    try:
        current = evidence.state(Path(root))
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "UNKNOWN"
    # A cached PASS covers only the state it recorded; any later change makes it stale.
    return "PASS" if cache.read_text().strip().removeprefix("direct ") == current else "STALE"
