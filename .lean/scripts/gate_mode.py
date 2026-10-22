"""Shared workspace gate automation policy; absent settings preserve automatic checks."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True


def safe_path(root, relative):
    path = root
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"gate policy must not cross a symlink: {path}")
    return path


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate gate policy key: {key}")
        result[key] = value
    return result


MODES = ("auto", "manual", "auto_fixloop", "manual_fixloop")


def read_mode(root):
    path = safe_path(root, ".codex/quality-gate.json")
    if not path.exists():
        return "auto", True, False, False
    config = json.loads(path.read_text(), object_pairs_hook=unique_keys)
    if (not isinstance(config, dict) or "auto" not in config or not set(config) <= {"auto", "fixloop"}
            or type(config["auto"]) is not bool or type(config.get("fixloop", False)) is not bool):
        raise ValueError("gate policy must contain only auto (and optional fixloop) JSON booleans")
    auto = config["auto"]
    fixloop = config.get("fixloop", False)
    mode = ("auto" if auto else "manual") + ("_fixloop" if fixloop else "")
    return mode, auto, fixloop, True


def read_auto(root):
    _, auto, _, configured = read_mode(root)
    return auto, configured


def policy(mode):
    if isinstance(mode, bool):
        mode = "auto" if mode else "manual"
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
                "batch) before starting the full gate: bash .lean/scripts/quality-gate.sh --root . with "
                "--contract and --require-review when required. Once authorized, if any gate check fails, "
                "auto-loop: fix all actionable code, test and lint failures and re-run the gate until it passes "
                "without asking again between rounds, stopping only for genuine requirement/design questions or "
                "missing environment tools. Deferred validation is not a pass: stay VALIDATING/BLOCKED until the "
                "gate and required review cover the shipping state.")
    return ("Lean Quality Gate auto=false: automatic validation NOT_RUN. Run focused checks; get user "
            "authorization (reuse matching approval for this workset or batch) before the full gate: "
            "bash .lean/scripts/quality-gate.sh --root . with --contract and --require-review when required. "
            "Deferred validation is not a pass: stay VALIDATING/BLOCKED until the gate and required review "
            "cover the shipping state.")


def write_mode(root, mode):
    if mode not in MODES:
        raise ValueError(f"unsupported gate mode: {mode}")
    auto = mode.startswith("auto")
    fixloop = mode.endswith("_fixloop")
    payload = {"auto": auto, "fixloop": True} if fixloop else {"auto": auto}
    runtime = safe_path(root, ".agent-runtime")
    runtime.mkdir(exist_ok=True)
    with safe_path(root, ".agent-runtime/gate-mode.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        read_mode(root)  # Invalid settings require explicit investigation, not silent repair.
        path = safe_path(root, ".codex/quality-gate.json")
        path.parent.mkdir(exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                json.dump(payload, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def write_auto(root, auto):
    write_mode(root, "auto" if auto else "manual")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("mode", nargs="?", choices=MODES)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check-auto", action="store_true", help=argparse.SUPPRESS)
    output.add_argument("--fixloop", action="store_true", help=argparse.SUPPRESS)
    output.add_argument("--policy", action="store_true", help="print policy context without checks")
    args = parser.parse_args()
    if args.mode and (args.check_auto or args.fixloop or args.policy):
        parser.error("inspection flags cannot set a mode")
    try:
        root = args.root.resolve(strict=True)
        mode, auto, fixloop, configured = read_mode(root)
        if args.mode:
            write_mode(root, args.mode)
            mode, auto, fixloop, configured = read_mode(root)
        if args.policy:
            print(policy(mode))
        elif args.fixloop:
            return 0 if fixloop else 1
        elif args.check_auto:
            if not auto:
                print(policy(mode))
                return 3
            if fixloop:
                print(policy(mode))
        else:
            print(json.dumps({"mode": mode, "configured": configured}))
        return 0
    except (OSError, ValueError) as error:
        print(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
