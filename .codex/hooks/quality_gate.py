"""Codex lifecycle adapter for the shared Lean gate; hook trust remains user-owned."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".lean/scripts"))
from gate_mode import policy, read_mode
from gate_evidence import check_review, state
import contract_guard

MAX_REFUSALS = 3


def current_review_contract(root):
    """Reuse only a review that covers this exact shipping state, never an old receipt."""
    try:
        receipt = json.loads((root / ".agent-runtime/review.json").read_text())
        contract = receipt["contract"]
        if not isinstance(contract, str) or not contract.startswith("Contract:"):
            return None
        check_review(root, contract)
        return contract
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("event", choices=("session-start", "stop", "run"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--contract")
    parser.add_argument("--require-review", action="store_true")
    # Opt-in, as Claude's Stop command opts in: reuse a pass recorded for the same shipping state.
    parser.add_argument("--cache-tree", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        mode, auto, fixloop, _ = read_mode(root)
        payload = json.load(sys.stdin) if args.event == "stop" else {}
        if not isinstance(payload, dict) or type(payload.get("stop_hook_active", False)) is not bool:
            raise ValueError("hook input must be an object with a boolean stop_hook_active")
    except (OSError, ValueError) as error:
        message = f"Codex Quality Gate policy/input invalid: {error}; validation NOT_RUN."
        if args.event == "run":
            print(message, file=sys.stderr)
            return 2
        print(json.dumps({"systemMessage": message}))
        return 0
    if args.event == "session-start":
        clear_session_refusals(root)
        session = payload_session(sys.stdin)
        if session:
            try:
                # Keep the first baseline: a resume or subagent reuses the session id, and
                # rebasing then would absorb undeclared work made earlier in the session.
                if not contract_guard.baseline(root, session):
                    contract_guard.baseline(root, session, state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass  # No baseline: the Stop treats any uncommitted change as this session's work.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": policy(mode)}}))
        return 0
    if args.event == "stop" and not auto:
        print(json.dumps({"systemMessage": policy(mode)}))
        return 0
    command = ["bash", str(root / ".lean/scripts/quality-gate.sh"), "--root", str(root)]
    if args.event == "stop":
        command.append("--quiet")  # No one watches a Stop live, and check times must not change its refusal.
    if args.cache_tree:
        command.append("--cache-tree")
    contract = args.contract
    reviewed = None
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) else ""
    # Without a session id (no hook metadata) the contract cannot be enforced, as with a
    # Claude Stop that carries no transcript.
    if args.event == "stop" and not contract and session:
        try:
            contract = contract_guard.current(root, session)
            if not contract and changed_since_baseline(root, session):
                return refuse(root, payload, "Changed work has no declared Task Contract for this session.\n"
                              + contract_guard.HELP, session=session, is_contract=True, fixloop=fixloop)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            return refuse(root, payload, f"Task Contract state unreadable: {error}",
                          session=session, is_contract=True, fixloop=fixloop)
    if args.event == "stop" and not contract:
        reviewed = current_review_contract(root)
        contract = reviewed
    if contract:
        command.extend(["--contract", contract])
    if session:
        command.extend(["--session", session])  # The runner reads that session's declared contract itself.
    if args.require_review or reviewed:
        command.append("--require-review")
    if args.event == "run":
        return subprocess.run(command, cwd=root).returncode
    result = subprocess.run(command, text=True, capture_output=True, cwd=root)
    if result.returncode == 0:
        clear_refusals(root)
        if session:
            try:
                contract_guard.baseline(root, session, state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
        print(json.dumps({"systemMessage": "Quality Gate checks passed; acceptance and required semantic review remain separate."}))
        return 0
    return refuse(root, payload, (result.stderr + result.stdout)[-12000:],
                  session=session, contract=contract or "", fixloop=fixloop)


def clear_refusals(root):
    for name in ("codex-gate-failed", "codex-gate-refusal"):
        try:
            (root / ".agent-runtime" / name).unlink(missing_ok=True)
        except OSError:
            pass


def clear_session_refusals(root):
    runtime = root / ".agent-runtime"
    try:
        (runtime / "codex-gate-refusal").unlink(missing_ok=True)
        failed = runtime / "codex-gate-failed"
        if failed.is_file() and failed.read_text().startswith("c"):
            failed.unlink(missing_ok=True)
    except OSError:
        pass


def payload_session(stream):
    """The session id from a SessionStart payload, or "" when absent or unreadable."""
    try:
        payload = json.load(stream)
    except ValueError:
        return ""
    session = payload.get("session_id") if isinstance(payload, dict) else None
    return session if isinstance(session, str) and session.strip() and "\n" not in session else ""


def changed_since_baseline(root, session):
    """Whether the shipping state moved since this session started or last passed the gate."""
    recorded = contract_guard.baseline(root, session) if session else None
    if recorded:
        return state(root) != recorded
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True)
    return dirty.returncode != 0 or bool(dirty.stdout.strip())


def refuse(root, payload, detail, session="", contract="", is_contract=False, fixloop=False):
    """Block up to MAX_REFUSALS attempts; release unchanged or capped continued Stops UNVERIFIED."""
    runtime = root / ".agent-runtime"
    failed = runtime / "codex-gate-failed"
    refusal = runtime / "codex-gate-refusal"
    count = 0
    try:
        if not runtime.is_symlink():
            runtime.mkdir(exist_ok=True)
            if payload.get("stop_hook_active") and failed.is_file():
                raw = failed.read_text().strip().lstrip("c")
                count = int(raw) if raw.isdigit() else 0
            count += 1
            failed.write_text(f"{'c' if is_contract else ''}{count}")
            if not is_contract and session:
                try:
                    current = state(root)
                except (OSError, ValueError, subprocess.CalledProcessError):
                    current = ""
                if current:
                    reason = hashlib.sha256(detail.encode()).hexdigest()
                    fingerprint = f"{session} {current} {reason} {contract}"
                    if refusal.is_file() and refusal.read_text() == fingerprint:
                        print(json.dumps({"systemMessage": "Codex Quality Gate refused again with nothing changed since the last refusal; Stop released UNVERIFIED. The work is not DONE; see that refusal."}))
                        return 0
                    refusal.write_text(fingerprint)
    except (OSError, ValueError, subprocess.CalledProcessError):
        count = count or (MAX_REFUSALS + 1 if payload.get("stop_hook_active") else 1)
    if count > MAX_REFUSALS:
        print(json.dumps({"systemMessage": f"Codex Quality Gate still refused after {MAX_REFUSALS} attempts; Stop released UNVERIFIED. The work is not DONE; see the last gate refusal.\n{detail}"}))
        return 0
    if fixloop:
        header = ("Quality Gate UNVERIFIED (fixloop active: fix actionable failures and re-run until the gate passes; "
                  "stop only for a genuine question or missing tool; do not declare DONE).\n")
    else:
        header = "Quality Gate UNVERIFIED. Report BLOCKED; do not declare DONE.\n"
    print(json.dumps({"decision": "block", "reason": header + detail}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
