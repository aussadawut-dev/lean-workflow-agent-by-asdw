"""Codex lifecycle adapter for the shared Lean gate; hook trust remains user-owned."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".lean/scripts"))
from gate_mode import policy, read_auto
from gate_evidence import check_review, state
import contract_guard


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
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        auto, _ = read_auto(root)
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
        session = payload_session(sys.stdin)
        if session:
            try:
                contract_guard.baseline(root, session, state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass  # No baseline: the Stop treats any uncommitted change as this session's work.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": policy(auto)}}))
        return 0
    if args.event == "stop" and not auto:
        print(json.dumps({"systemMessage": policy(auto)}))
        return 0
    command = ["bash", str(root / ".lean/scripts/quality-gate.sh"), "--root", str(root)]
    contract = args.contract
    reviewed = None
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) else ""
    # Without a session id (no hook metadata) the contract cannot be enforced, as with a
    # Claude Stop that carries no transcript.
    if args.event == "stop" and not contract and session:
        try:
            contract = contract_guard.current(root, session)
            if not contract and changed_since_baseline(root, session):
                return refuse(payload, "Changed work has no declared Task Contract for this session.\n"
                              + contract_guard.HELP)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            return refuse(payload, f"Task Contract state unreadable: {error}")
    if args.event == "stop" and not contract:
        reviewed = current_review_contract(root)
        contract = reviewed
    if contract:
        command.extend(["--contract", contract])
    if args.require_review or reviewed:
        command.append("--require-review")
    result = subprocess.run(command, text=True, capture_output=True, cwd=root)
    if args.event == "run":
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode
    if result.returncode == 0:
        if session:
            try:
                contract_guard.baseline(root, session, state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
        print(json.dumps({"systemMessage": "Quality Gate checks passed; acceptance and required semantic review remain separate."}))
        return 0
    return refuse(payload, (result.stderr + result.stdout)[-12000:])


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


def refuse(payload, detail):
    """Block a fresh Stop once; a continued Stop is released UNVERIFIED, never as a pass."""
    message = "Quality Gate UNVERIFIED. Report BLOCKED; do not declare DONE.\n" + detail
    response = {"systemMessage": message} if payload.get("stop_hook_active") else {"decision": "block", "reason": message}
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    sys.exit(main())
