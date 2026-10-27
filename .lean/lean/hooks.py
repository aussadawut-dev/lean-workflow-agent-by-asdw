"""Provider lifecycle adapters: Claude and Codex hooks call `lean hook <provider> <event>`.

Both providers share the guard and the gate runner; only input and output formats differ.
Claude refuses a Stop with JSON {"decision": "block"} on exit 0, because headless `claude -p`
feeds a Stop reason back to the model only in that form and treats exit 2 as a hook error.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

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


def notices(root):
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
    current = progress.load(root)
    if current and current.get("phase") != "done":
        lines.append("Lean progress: " + progress.line(current))
    return lines


def mode_context(root):
    """The gate policy line for SessionStart, or raise for an invalid policy."""
    mode, auto, fixloop, _ = gate.read_mode(root)
    return gate.policy(mode) if (not auto or fixloop) else ""


def claude_session_start(root, stdin):
    # Kept quiet: this hook's stdout becomes Claude's context.
    try:
        gate.run(root, hook=True, seed=True, payload=payload_of(stdin))
    except (OSError, ValueError, subprocess.CalledProcessError):
        pass
    try:
        lines = [mode_context(root)] + notices(root)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return 2, "", f"Lean SessionStart: {error}; validation NOT_RUN."
    return 0, "\n".join(line for line in lines if line), ""


def claude_stop(root, stdin, cache_tree):
    try:
        mode, auto, _, _ = gate.read_mode(root)
    except (OSError, ValueError) as error:
        return 0, block(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN."), ""
    if not auto and not os.environ.get(gate.FORCE_ENV):
        return 0, "", gate.policy(mode)
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
        stdout = status_message(root)
    return code, stdout, reason


def status_message(root):
    """A pass's systemMessage, with the progress bar when a task is being tracked."""
    current = progress.load(root)
    if not current:
        return ""
    return json.dumps({"systemMessage": "Lean progress: " + progress.line(current)})


# --- Codex ------------------------------------------------------------------------------------

def codex_session_start(root, stdin):
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
    context = "\n".join([gate.policy(mode)] + notices(root))
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
        current = progress.load(root)
        if current:
            message += "\nLean progress: " + progress.line(current)
        return 0, json.dumps({"systemMessage": message}), ""
    return codex_refuse(root, payload, "\n".join(err)[-REASON_LIMIT:], session=session, contract=contract,
                        fixloop=fixloop)


def clear_codex_refusals(root):
    for name in ("codex-gate-failed", "codex-gate-refusal"):
        try:
            (root / ".agent-runtime" / name).unlink(missing_ok=True)
        except OSError:
            pass


def clear_codex_session_refusals(root):
    runtime = root / ".agent-runtime"
    try:
        (runtime / "codex-gate-refusal").unlink(missing_ok=True)
        failed = runtime / "codex-gate-failed"
        if failed.is_file() and failed.read_text().startswith("c"):
            failed.unlink(missing_ok=True)
    except OSError:
        pass


def codex_refuse(root, payload, detail, session="", contract="", is_contract=False, fixloop=False):
    """Block up to MAX_REFUSALS attempts; release unchanged or capped continued Stops UNVERIFIED."""
    runtime = root / ".agent-runtime"
    failed, refusal = runtime / "codex-gate-failed", runtime / "codex-gate-refusal"
    count = 0
    try:
        if not runtime.is_symlink():
            runtime.mkdir(exist_ok=True)
            if payload.get("stop_hook_active") and failed.is_file():
                raw = failed.read_text().strip().lstrip("c")
                count = int(raw) if raw.isdigit() else 0
            failed.write_text(f"{'c' if is_contract else ''}{count + 1}")
            count += 1
            if not is_contract and session:
                try:
                    current = evidence.state(root)
                except (OSError, ValueError, subprocess.CalledProcessError):
                    current = ""
                if current:
                    reason = hashlib.sha256(detail.encode()).hexdigest()
                    fingerprint = f"{session} {current} {reason} {contract}"
                    if refusal.is_file() and refusal.read_text() == fingerprint:
                        return 0, json.dumps({"systemMessage": "Codex Quality Gate refused again with nothing changed "
                                              "since the last refusal; Stop released UNVERIFIED. The work is not "
                                              "DONE; see that refusal."}), ""
                    refusal.write_text(fingerprint)
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
