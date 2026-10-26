"""Codex lifecycle adapter for the shared Lean gate; hook trust remains user-owned."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".lean/scripts"))
IMPORT_FAILURE = None  # why the shared modules could not be imported; only a Stop turns it into a block


class _Unavailable:
    """Stands in for a shared module name that failed to import: using it re-raises the import failure."""

    def __init__(self, name):
        self._name = name

    def _fail(self):
        raise IMPORT_FAILURE

    def __call__(self, *args, **kwargs):
        self._fail()

    def __getattr__(self, attribute):
        if attribute.startswith("__"):
            raise AttributeError(attribute)
        self._fail()


try:
    from gate_mode import policy, read_mode
    from gate_evidence import check_review, state
    import contract_guard
except (Exception, SystemExit) as failure:
    # A missing, stale or broken shared module must not crash before the Stop handler's fail-closed
    # wrapper exists: main() blocks a Stop; session-start and run still fail as before when they use
    # a name. A non-zero exit is not a pass and propagates now; KeyboardInterrupt is never caught.
    if isinstance(failure, SystemExit) and failure.code not in (None, 0):
        raise
    IMPORT_FAILURE = failure
    policy, read_mode, check_review, state, contract_guard = (
        _Unavailable(n) for n in ("policy", "read_mode", "check_review", "state", "contract_guard"))
try:
    import lean_core
except (Exception, SystemExit):  # partial upgrade: a missing, stale or broken lean_core.py must degrade, not crash
    lean_core = None  # (a core that exits at import must not end this hook with a silent pass)
BLOCK = getattr(lean_core, "BLOCK", "block")
RELEASE_UNCHANGED = getattr(lean_core, "RELEASE_UNCHANGED", "release_unchanged")
RELEASE_CAPPED = getattr(lean_core, "RELEASE_CAPPED", "release_capped")

MAX_REFUSALS = 3
# Fixed stderr prefixes of a runner that could not take the gate lock (gate_lock.py).
BUSY_PREFIXES = ("Quality Gate busy", "Quality Gate lock unavailable")


def valid_session_key(key):
    """A session key is exactly 16 lowercase hex characters; anything else is never a path component."""
    return (isinstance(key, str) and len(key) == 16 and key.isascii()
            and all(c in "0123456789abcdef" for c in key))


def marker_names(session):
    """The Codex refusal file names for a session: keyed, or the legacy names without a session id
    (or when lean_core is missing)."""
    try:
        key = getattr(lean_core, "session_key", lambda _s: None)(session) if lean_core else None
    except (Exception, SystemExit):  # a stale or broken core: legacy names, as when the core is missing
        key = None
    suffix = f".{key}" if valid_session_key(key) else ""
    return f"codex-gate-failed{suffix}", f"codex-gate-refusal{suffix}"


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


STOP_UNDECIDED = "Codex Quality Gate could not decide; validation NOT_RUN; report BLOCKED"


def main():
    """Fail closed: any unexpected error while deciding a Stop is a block, never an empty stdout."""
    if "stop" in sys.argv[1:]:
        try:
            if IMPORT_FAILURE is not None:
                raise OSError("shared gate modules could not be imported")
            return run_hook()
        except Exception:
            print(json.dumps({"decision": "block", "reason": STOP_UNDECIDED}))
            return 0
        except SystemExit as stop:
            if stop.code not in (None, 0):
                raise  # a non-zero exit (usage error) is not a pass; let it propagate unchanged
            print(json.dumps({"decision": "block", "reason": STOP_UNDECIDED}))  # exit 0 without a decision is a silent pass
            return 0
    return run_hook()


def run_hook():
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
        session = payload_session(sys.stdin)
        clear_session_refusals(root, session)
        if session:
            try:
                # Keep the first baseline: a resume or subagent reuses the session id, and
                # rebasing then would absorb undeclared work made earlier in the session.
                contract_guard.start_session(root, session, state(root))
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
        clear_refusals(root, session)
        if session:
            try:
                contract_guard.baseline(root, session, state(root))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
        print(json.dumps({"systemMessage": "Quality Gate checks passed; acceptance and required semantic review remain separate."}))
        return 0
    busy = result.returncode == 2 and result.stderr.startswith(BUSY_PREFIXES)
    if busy and result.stderr.startswith(BUSY_PREFIXES[1]):
        busy = "unavailable"  # truthy: counted like a busy gate, worded as a lock that could not be taken
    return refuse(root, payload, (result.stderr + result.stdout)[-12000:],
                  session=session, contract=contract or "", fixloop=fixloop, busy=busy)


def clear_refusals(root, session=""):
    names = marker_names(session)
    if names[0] != "codex-gate-failed":
        names += ("codex-gate-failed", "codex-gate-refusal")  # a keyed pass also drops the legacy files
    for name in names:
        try:
            (root / ".agent-runtime" / name).unlink(missing_ok=True)
        except OSError:
            pass


def clear_session_refusals(root, session=""):
    runtime = root / ".agent-runtime"
    failed_name, refusal_name = marker_names(session)
    try:
        (runtime / refusal_name).unlink(missing_ok=True)
        failed = runtime / failed_name
        if failed.is_file() and failed.read_text().startswith("c"):
            failed.unlink(missing_ok=True)
        if failed_name != "codex-gate-failed":  # keyed session: legacy markers are dropped once
            (runtime / "codex-gate-failed").unlink(missing_ok=True)
            (runtime / "codex-gate-refusal").unlink(missing_ok=True)
        prune_markers(runtime)
    except OSError:
        pass


def prune_markers(runtime, max_age=86400):
    """Delete keyed Codex marker files untouched for a day; legacy and unrelated names are kept."""
    now = time.time()
    for pattern in ("codex-gate-failed.", "codex-gate-refusal."):
        for path in runtime.glob(pattern + "[0-9a-f]" * 16):
            try:
                if path.is_file() and now - path.stat().st_mtime > max_age:
                    path.unlink(missing_ok=True)
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


def refuse(root, payload, detail, session="", contract="", is_contract=False, fixloop=False, busy=False):
    """Block up to MAX_REFUSALS attempts; release unchanged or capped continued Stops UNVERIFIED.

    A busy gate lock is counted like Claude's busy_stop: capped, and never released as unchanged."""
    runtime = root / ".agent-runtime"
    failed_name, refusal_name = marker_names(session)
    failed = runtime / failed_name
    refusal = runtime / refusal_name
    continued = bool(payload.get("stop_hook_active"))
    action = decided = None
    try:
        if not runtime.is_symlink():
            runtime.mkdir(exist_ok=True)
            previous = failed.read_text() if continued and failed.is_file() else ""
            fingerprint = ""
            if not is_contract and not busy and session:
                try:
                    current = state(root)
                except (OSError, ValueError, subprocess.CalledProcessError):
                    current = ""
                if current:
                    reason = hashlib.sha256(detail.encode()).hexdigest()
                    fingerprint = f"{session} {current} {reason} {contract}"
            same = readable = False
            if fingerprint:
                try:
                    same = refusal.is_file() and refusal.read_text() == fingerprint
                    readable = True
                except (OSError, ValueError):
                    pass  # an unreadable record only skips the unchanged check; the count below still stands
            decide = getattr(lean_core, "gate_refusal", None)
            if decide is None:
                raise OSError("shared refusal core missing")  # use the fallback below
            try:
                decided, marker = decide(previous, continued, is_contract, same)
            except (Exception, SystemExit) as error:  # a stale or broken core is treated as a missing one
                if isinstance(error, SystemExit) and error.code not in (None, 0):
                    raise  # a non-zero exit is not a pass; let it propagate
                raise OSError(f"shared refusal core failed: {error!r}")
            if (failed.exists() or failed.is_symlink()) and not failed.is_file():
                raise OSError("refusal marker is not a regular file")  # unusable: never open a directory or FIFO
            failed.write_text(marker)
            action = decided  # a marker that cannot be kept decides nothing: the fallback below applies
            if readable and action != RELEASE_UNCHANGED:
                refusal.write_text(fingerprint)
    except (OSError, ValueError, subprocess.CalledProcessError):
        pass  # keep a decision already made; otherwise fall back below
    if action == RELEASE_UNCHANGED:
        print(json.dumps({"systemMessage": "Codex Quality Gate refused again with nothing changed since the last refusal; Stop released UNVERIFIED. The work is not DONE; see that refusal."}))
        return 0
    if action is None:
        # The shared decision could not run (unwritable runtime): a continued Stop is released, a fresh one blocks once.
        action = RELEASE_CAPPED if continued else BLOCK
    if action == RELEASE_CAPPED and busy == "unavailable":
        print(json.dumps({"systemMessage": f"Codex Quality Gate could not take its lock (gate lock unavailable in this checkout) after {MAX_REFUSALS} attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED."}))
        return 0
    if action == RELEASE_CAPPED and busy:
        print(json.dumps({"systemMessage": f"Codex Quality Gate stayed busy (another gate is running in this checkout) after {MAX_REFUSALS} attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED."}))
        return 0
    if action == RELEASE_CAPPED:
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
