"""Provider lifecycle adapters: Claude and Codex hooks call `lean hook <provider> <event>`.

Both providers share the guard and the gate runner; only input and output formats differ.
Claude refuses a Stop with JSON {"decision": "block"} on exit 0, because headless `claude -p`
feeds a Stop reason back to the model only in that form and treats exit 2 as a hook error.
"""
import contextlib
import hashlib
import json
import os
import stat
from pathlib import Path
import subprocess
import time

from . import evidence, gate, guard, progress
from .util import LeanError, read_json

REASON_LIMIT = 12000


def block(reason):
    reason = reason[-REASON_LIMIT:].strip() or "Lean Quality Gate refused; report BLOCKED and do not declare DONE."
    return json.dumps({"decision": "block", "reason": reason})


def run_hook(root, provider, event, stdin, cache_tree=False):
    """Return (exit code, stdout, stderr) for one hook call."""
    root = Path(root).resolve()
    if event in ("pre-tool", "prompt"):
        code, message = guard.hook(root, event, stdin)
        return code, "", message
    if provider == "claude":
        if event == "session-start":
            return claude_session_start(root, stdin)
        if event == "stop":
            return claude_stop(root, stdin, cache_tree)
    if provider == "codex":
        if event == "session-start":
            return codex_session_start(root, stdin)
        if event == "stop":
            return codex_stop(root, stdin, cache_tree)
    return 2, "", f"unknown hook: {provider} {event}"


def payload_of(stdin):
    try:
        payload = json.loads(stdin) if stdin.strip() else {}
    except ValueError as error:
        raise LeanError(f"hook input is not JSON: {error}") from error
    if not isinstance(payload, dict):
        raise LeanError("hook input must be a JSON object")
    return payload


def notices(root, session=None):
    """Onboarding notes for SessionStart context; they never validate anything."""
    selection = root / ".agent-runtime/active-target.json"
    if selection.exists() or selection.is_symlink():
        from . import target
        paths = target.context(root)  # An invalid selection fails the hook rather than falling back.
        return ["Lean target context (start from the Lean root; application commands use project_root):",
                json.dumps(paths, indent=2),
                "Read the selected project_file and target instructions. Workflow records stay in record_root. "
                "Run the target gate as well as the Lean gate."]
    lines = []
    config = root / ".lean/config.json"
    try:
        configured = config.is_file() and read_json(config).get("configured") is True
    except (OSError, ValueError):
        configured = False
    if not configured:
        lines.append("Lean Workflow: choose standard, tracker, or full with /lean-init; direct execution is the "
                     "default, delegated is optional.")
    project = root / ".lean/PROJECT.md"
    try:
        defined = project.is_file() and bool(gate.gate_commands(project))
    except LeanError:
        defined = False
    if not defined:
        lines.append("Lean Quality Gate undefined: configure checks in .lean/PROJECT.md with /lean-init; no "
                     "validation is enforced yet.")
    if project.is_file():
        text = project.read_text()
        purpose = text.split("## Purpose", 1)[-1].split("\n## ", 1)[0] if "## Purpose" in text else ""
        if "Not defined yet" in purpose:
            lines.append("Lean Workflow: .lean/PROJECT.md is not filled in yet. If the repository has code, "
                         "suggest running /lean-init once.")
    current = progress.load(root, session)
    if current and current.get("phase") != "done":
        lines.append("Lean progress: " + progress.shown(root, session))
    return lines


def mode_context(root):
    """The gate policy line for SessionStart, or raise for an invalid policy."""
    mode, auto, fixloop, _ = gate.read_mode(root)
    return gate.policy(mode) if (not auto or fixloop) else ""


def claude_session_start(root, stdin):
    # Kept quiet: this hook's stdout becomes Claude's context.
    session = None
    sweep_stale_markers(root)
    try:
        payload = payload_of(stdin)
        session = progress.valid_session(payload.get("session_id")) or None
        gate.run(root, hook=True, seed=True, payload=payload)
    except (OSError, ValueError, subprocess.CalledProcessError):
        pass
    try:
        lines = [mode_context(root)] + notices(root, session)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return 2, "", f"Lean SessionStart: {error}; validation NOT_RUN."
    return 0, "\n".join(line for line in lines if line), ""


def claude_stop(root, stdin, cache_tree):
    try:
        mode, auto, _, _ = gate.read_mode(root)
    except (OSError, ValueError) as error:
        return 0, block(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN."), ""
    if not auto and not os.environ.get(gate.FORCE_ENV):
        # Claude shows a Stop hook's stderr to no one on exit 0; the full policy arrives at SessionStart.
        return 0, json.dumps({"systemMessage": f"Lean Quality Gate NOT_RUN ({mode}): run `python3 .lean/bin/lean "
                                               "gate run` once the user authorizes it."}), ""
    try:
        payload = payload_of(stdin)
    except LeanError as error:
        return 0, block(str(error)), ""
    code, out, err = gate.run(root, hook=True, cache_tree=cache_tree, payload=payload)
    reason = "\n".join(err)
    if code == 2:
        return 0, block(reason), ""
    stdout = "\n".join(out)
    if code == 0 and not out:
        stdout = status_message(root, progress.valid_session(payload.get("session_id")) or None)
    return code, stdout, reason


def status_message(root, session=None):
    """A pass's systemMessage, with the progress bar when a task is being tracked."""
    text = progress.shown(root, session)
    if not text:
        return ""
    return json.dumps({"systemMessage": "Lean progress: " + text})


# --- Codex ------------------------------------------------------------------------------------

def codex_session_start(root, stdin):
    sweep_stale_markers(root)
    clear_codex_session_refusals(root)
    try:
        mode = gate.read_mode(root)[0]
    except (OSError, ValueError) as error:
        return 0, json.dumps({"systemMessage": f"Codex Quality Gate policy/input invalid: {error}; validation "
                                               "NOT_RUN."}), ""
    try:
        session = payload_of(stdin).get("session_id")
    except LeanError:
        session = None
    if isinstance(session, str) and session.strip() and "\n" not in session:
        try:
            # Keep the first baseline: a resume or subagent reuses the session id, and rebasing
            # then would absorb undeclared work made earlier in the session.
            guard.start_session(root, session, evidence.state(root))
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass  # No baseline: the Stop treats any uncommitted change as this session's work.
    context = "\n".join([gate.policy(mode)] + notices(root, progress.valid_session(session) or None))
    return 0, json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}), ""


def current_review_contract(root):
    """Reuse only a review that covers this exact shipping state, never an old receipt."""
    try:
        receipt = json.loads((root / ".agent-runtime/review.json").read_text())
        contract = receipt["contract"]
        if not isinstance(contract, str) or not contract.startswith("Contract:"):
            return None
        evidence.check_review(root, contract)
        return contract
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        return None


def changed_since_baseline(root, session):
    """Whether the shipping state moved since this session started or last passed the gate."""
    recorded = guard.baseline(root, session) if session else None
    if recorded:
        return evidence.state(root) != recorded
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True)
    return dirty.returncode != 0 or bool(dirty.stdout.strip())


def codex_stop(root, stdin, cache_tree):
    try:
        mode, auto, fixloop, _ = gate.read_mode(root)
        payload = payload_of(stdin)
        if type(payload.get("stop_hook_active", False)) is not bool:
            raise LeanError("hook input must be an object with a boolean stop_hook_active")
    except (OSError, ValueError) as error:
        return 0, json.dumps({"systemMessage": f"Codex Quality Gate policy/input invalid: {error}; validation "
                                               "NOT_RUN."}), ""
    if not auto:
        return 0, json.dumps({"systemMessage": gate.policy(mode)}), ""
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) else ""
    contract, require_review = "", False
    # Without a session id (no hook metadata) the contract cannot be enforced.
    if session:
        try:
            contract = guard.current(root, session) or ""
            if not contract and changed_since_baseline(root, session):
                return codex_refuse(root, payload, "Changed work has no declared Task Contract for this session.\n"
                                    + guard.HELP, session=session, is_contract=True, fixloop=fixloop)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            return codex_refuse(root, payload, f"Task Contract state unreadable: {error}",
                                session=session, is_contract=True, fixloop=fixloop)
    if not contract:
        contract = current_review_contract(root) or ""
        require_review = bool(contract)
    # The runner reads that session's declared contract itself; Stop output is quiet.
    code, out, err = gate.run(root, cache_tree=cache_tree, quiet=True, contract=contract, session=session,
                              require_review=require_review, stop=True)
    if code == 0 and out:
        # Released for a marked pending review: not a pass, so the refusal markers and session
        # baseline stay as they are.
        return 0, out[-1], ""
    if code == 0:
        clear_codex_refusals(root)
        if session:
            try:
                guard.baseline(root, session, evidence.state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
        message = "Quality Gate checks passed; acceptance and required semantic review remain separate."
        text = progress.shown(root, progress.valid_session(session) or None)
        if text:
            message += "\nLean progress: " + text
        return 0, json.dumps({"systemMessage": message}), ""
    return codex_refuse(root, payload, "\n".join(err)[-REASON_LIMIT:], session=session, contract=contract,
                        fixloop=fixloop)


@contextlib.contextmanager
def codex_markers(root, create=False):
    """The runtime folder as a directory descriptor, opened without following a link (raises OSError)."""
    runtime = Path(root) / ".agent-runtime"
    if create and not runtime.is_symlink():
        runtime.mkdir(exist_ok=True)
    descriptor = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def marker_open(directory, name, flags):
    """A marker opened inside `directory` only as a plain file with one link; never through a link."""
    descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise OSError(f"refusal marker {name} must be a plain file with one link")
    return descriptor


def marker_read(directory, name):
    try:
        descriptor = marker_open(directory, name, os.O_RDONLY)
    except FileNotFoundError:
        return ""
    with os.fdopen(descriptor) as stream:
        return stream.read()


def marker_write(directory, name, value):
    descriptor = marker_open(directory, name, os.O_WRONLY | os.O_CREAT)
    with os.fdopen(descriptor, "w") as stream:
        stream.truncate(0)
        stream.write(value)


def marker_remove(directory, name):
    try:
        os.unlink(name, dir_fd=directory)  # Removes a link itself, never what it points to.
    except FileNotFoundError:
        pass


def sweep_stale_markers(root):
    """Remove Codex refusal markers left untouched for a week; a live session rewrites its own."""
    try:
        with codex_markers(root) as directory:
            for name in ("codex-gate-failed", "codex-gate-refusal"):
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if time.time() - info.st_mtime > progress.KEEP_SECONDS:
                        marker_remove(directory, name)
                except OSError:
                    pass
    except OSError:
        pass


def clear_codex_refusals(root):
    try:
        with codex_markers(root) as directory:
            for name in ("codex-gate-failed", "codex-gate-refusal"):
                try:  # Each on its own: one marker that cannot be removed must not keep the other.
                    marker_remove(directory, name)
                except OSError:
                    pass
    except OSError:
        pass


def clear_codex_session_refusals(root):
    try:
        with codex_markers(root) as directory:
            try:  # Each on its own: one marker that cannot be removed must not keep the other.
                marker_remove(directory, "codex-gate-refusal")
            except OSError:
                pass
            try:
                if marker_read(directory, "codex-gate-failed").startswith("c"):
                    marker_remove(directory, "codex-gate-failed")
            except (OSError, ValueError):
                pass
    except OSError:
        pass


def codex_refuse(root, payload, detail, session="", contract="", is_contract=False, fixloop=False):
    """Block up to MAX_REFUSALS attempts; release unchanged or capped continued Stops UNVERIFIED."""
    count = 0
    try:
        # A symlinked runtime folder or marker cannot be kept safely, so the count is unknown.
        with codex_markers(root, create=True) as directory:
            if payload.get("stop_hook_active"):
                raw = marker_read(directory, "codex-gate-failed").strip().lstrip("c")
                count = int(raw) if raw.isdigit() else 0
            marker_write(directory, "codex-gate-failed", f"{'c' if is_contract else ''}{count + 1}")
            count += 1
            if not is_contract and session:
                try:
                    current = evidence.state(root)
                except (OSError, ValueError, subprocess.CalledProcessError):
                    current = ""
                if current:
                    reason = hashlib.sha256(detail.encode()).hexdigest()
                    fingerprint = f"{session} {current} {reason} {contract}"
                    if marker_read(directory, "codex-gate-refusal") == fingerprint:
                        return 0, json.dumps({"systemMessage": "Codex Quality Gate refused again with nothing changed "
                                              "since the last refusal; Stop released UNVERIFIED. The work is not "
                                              "DONE; see that refusal."}), ""
                    marker_write(directory, "codex-gate-refusal", fingerprint)
    except (OSError, ValueError, subprocess.CalledProcessError):
        # A marker that cannot be written leaves the count unknown: release continued Stops, not loop.
        count = gate.MAX_REFUSALS + 1 if payload.get("stop_hook_active") else 1
    if count > gate.MAX_REFUSALS:
        return 0, json.dumps({"systemMessage": f"Codex Quality Gate still refused after {gate.MAX_REFUSALS} attempts; "
                              f"Stop released UNVERIFIED. The work is not DONE; see the last gate refusal.\n{detail}"}), ""
    if fixloop:
        header = ("Quality Gate UNVERIFIED (fixloop active: fix actionable failures and re-run until the gate passes; "
                  "stop only for a genuine question or missing tool; do not declare DONE).\n")
    else:
        header = "Quality Gate UNVERIFIED. Report BLOCKED; do not declare DONE.\n"
    return 0, json.dumps({"decision": "block", "reason": header + detail}), ""
