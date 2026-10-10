"""Inspect or set procedure intensity; never changes model/runtime settings."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
LEVELS = ('standard', 'high', 'ultra')


def safe_path(root, relative):
    path = root
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f'skill intensity path must not be a symlink: {path}')
    return path


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate settings key: {key}')
        result[key] = value
    return result


def read_settings(path, names):
    if not path.exists():
        return {'default': 'standard', 'skills': {}}
    settings = json.loads(path.read_text(), object_pairs_hook=unique_keys)
    if (not isinstance(settings, dict) or set(settings) != {'default', 'skills'}
            or settings['default'] not in LEVELS or not isinstance(settings['skills'], dict)
            or any(name not in names or level not in LEVELS for name, level in settings['skills'].items())):
        raise ValueError('invalid shared skill intensity settings')
    return settings


@contextlib.contextmanager
def locked(root):
    runtime = safe_path(root, '.agent-runtime')
    runtime.mkdir(exist_ok=True)
    lock = safe_path(root, '.agent-runtime/skill-effort.lock')
    with lock.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def write_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(settings, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='explicit record root; bypass active target selection')
    parser.add_argument('level', nargs='?', choices=(*LEVELS, 'reset'))
    parser.add_argument('skill', nargs='?')
    args = parser.parse_args()
    workflow_root = Path(__file__).resolve().parents[2]
    names = sorted(path.parent.name for path in (workflow_root / '.lean/skills').glob('lean-*/SKILL.md'))
    try:
        if args.root is None:
            from submodule import context
            root = Path(context(workflow_root)['record_root'])
        else:
            root = args.root.resolve(strict=True)
        if args.skill and args.skill not in names:
            raise ValueError(f'unknown Lean skill: {args.skill}')
        path = safe_path(root, '.lean/skill-effort.json')
        if args.level is None:
            settings = read_settings(path, names)
            print('Lean procedure intensity (separate from model reasoning effort):')
            for name in names:
                print(f"{name}: {settings['skills'].get(name, settings['default'])}")
            return 0
        with locked(root):
            path = safe_path(root, '.lean/skill-effort.json')
            settings = read_settings(path, names)
            if args.level == 'reset':
                if args.skill:
                    settings['skills'].pop(args.skill, None)
                else:
                    path.unlink(missing_ok=True)
                    print('All Lean skills: standard procedure intensity (reset).')
                    return 0
            elif args.skill:
                settings['skills'][args.skill] = args.level
            else:
                settings = {'default': args.level, 'skills': {}}
            write_settings(path, settings)
            effective = settings['skills'].get(args.skill, settings['default'])
            print(f"{args.skill or 'All Lean skills'}: {effective} procedure intensity. Model settings unchanged.")
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
