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


def read_auto(root):
    path = safe_path(root, ".codex/quality-gate.json")
    if not path.exists():
        return True, False
    config = json.loads(path.read_text(), object_pairs_hook=unique_keys)
    if not isinstance(config, dict) or set(config) != {"auto"} or type(config["auto"]) is not bool:
        raise ValueError("gate policy must contain only an auto JSON boolean")
    return config["auto"], True


def policy(auto):
    if auto:
        return ("Lean Quality Gate auto=true: run the shared gate at work completion without asking. "
                "DONE still requires acceptance, current validation and required semantic review.")
    return ("Lean Quality Gate auto=false: automatic validation NOT_RUN. Run focused checks; get user "
            "authorization (reuse matching approval for this workset or batch) before the full gate: "
            "bash .lean/scripts/quality-gate.sh --root . with --contract and --require-review when required. "
            "Deferred validation is not a pass: stay VALIDATING/BLOCKED until the gate and required review "
            "cover the shipping state.")


def write_auto(root, auto):
    runtime = safe_path(root, ".agent-runtime")
    runtime.mkdir(exist_ok=True)
    with safe_path(root, ".agent-runtime/gate-mode.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        read_auto(root)  # Invalid settings require explicit investigation, not silent repair.
        path = safe_path(root, ".codex/quality-gate.json")
        path.parent.mkdir(exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                json.dump({"auto": auto}, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("mode", nargs="?", choices=("auto", "manual"))
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--check-auto", action="store_true", help=argparse.SUPPRESS)
    output.add_argument("--policy", action="store_true", help="print policy context without checks")
    args = parser.parse_args()
    if args.mode and (args.check_auto or args.policy):
        parser.error("inspection flags cannot set a mode")
    try:
        root = args.root.resolve(strict=True)
        auto, configured = read_auto(root)
        if args.mode:
            write_auto(root, args.mode == "auto")
            auto, configured = read_auto(root)
        if args.policy:
            print(policy(auto))
        elif args.check_auto:
            if not auto:
                print(policy(auto))
                return 3
        else:
            print(json.dumps({"mode": "auto" if auto else "manual", "configured": configured}))
        return 0
    except (OSError, ValueError) as error:
        print(f"Gate policy invalid/unavailable: {error}; validation NOT_RUN.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
