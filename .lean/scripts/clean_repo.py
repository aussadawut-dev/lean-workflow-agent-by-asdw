#!/usr/bin/env python3
"""Read-only inventory and approved, externally journaled repository cleanup.

No semantic unused-code inference, Git index changes or command execution from plans.
Run with repository writers stopped. The private session is a trusted local artifact.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return base64.b64encode(value).decode('ascii')


def packed(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True).encode()


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True)
    return result.stdout.decode('utf-8', 'surrogateescape').rstrip('\n')


def repository(root):
    root = Path(root).absolute()
    plain_parents(root)
    if Path(git(root, 'rev-parse', '--show-toplevel')) != root:
        raise ValueError('root must be the repository top level')
    return root


def plain_parents(path):
    for node in (path, *path.parents):
        if node.is_symlink():
            raise ValueError(f'symlink boundary: {node}')


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('invalid relative path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError(f'unsafe path: {name}')
    return name


def location(root, name):
    path = root / relative(name)
    for node in (path, *path.parents):
        if node == root:
            break
        if node.is_symlink():
            raise ValueError(f'symlink boundary: {name}')
        if node.is_dir() and os.path.lexists(node / '.git'):
            raise ValueError(f'nested repository boundary: {name}')
    return path


def registered_assets(root):
    path = root / '.lean/assets.json'
    if not path.exists():
        return set()
    plain_parents(path)
    registry = json.loads(path.read_text())
    if not isinstance(registry.get('files'), list):
        raise ValueError('invalid workflow asset registry')
    return {relative(name).lower() for name in registry['files']}


def protected(name, registered=()):
    # Conservative on case-sensitive hosts; essential for macOS path aliases.
    name = name.lower()
    parts = PurePosixPath(name).parts
    base = parts[-1]
    if name in registered:
        return 'registered active workflow asset'
    if any(p in ('.git', '.agent-runtime', '.ssh', '.gnupg') for p in parts):
        return 'Git, coordination or private state'
    if any(name == p or name.startswith(p + '/') for p in
           ('.agents', '.claude', '.lean/targets', 'docs/tracking')):
        return 'agent configuration, discovery or work records'
    if name in ('agents.md', 'claude.md', '.lean/config.json', '.lean/project.md', '.lean/assets.json'):
        return 'active workflow contract or configuration'
    if any(name == p or name.startswith(p + '/') for p in
           ('.lean/policy', '.lean/skills', '.lean/roles')):
        return 'active workflow instructions'
    if (any(p.startswith('.env') for p in parts) or base in ('credentials', 'credentials.json', 'secrets.json')
            or base.startswith(('settings.local.', 'id_rsa', 'id_ed25519'))
            or base.endswith(('.pem', '.key', '.p12', '.pfx', '.db', '.sqlite', '.sqlite3'))):
        return 'potential credentials, local settings or persistent data'
    if base.startswith(('license', 'copying', 'changelog')):
        return 'license or retained history'
    return None


def generated(name, directory=False):
    parts = PurePosixPath(name).parts
    return ('__pycache__' in parts or
            (not directory and (parts[-1] == '.DS_Store' or parts[-1].endswith('.pyc'))))


def git_state(root):
    tracked = set(git(root, 'ls-files', '-z').split('\0')) - {''}
    dirty = set()
    for args in (('diff', '--name-only', '-z'), ('diff', '--cached', '--name-only', '-z')):
        dirty.update(git(root, *args).split('\0'))
    # An index conflict cannot be interpreted as a clean cleanup candidate.
    for row in git(root, 'ls-files', '--unmerged', '-z').split('\0'):
        if '\t' in row:
            dirty.add(row.split('\t', 1)[1])
    return tracked, dirty


def index_state(root):
    return {row.split('\t', 1)[1]: row.split('\t', 1)[0]
            for row in git(root, 'ls-files', '--stage', '-z').split('\0') if '\t' in row}


def tracked_directories(tracked):
    # Git does not track directories themselves; their tracked descendants do.
    return {parent.as_posix() for name in tracked for parent in PurePosixPath(name).parents
            if parent != PurePosixPath('.')}


def state(path):
    if not os.path.lexists(path):
        return None
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISDIR(info.st_mode):
        return {'kind': 'directory', 'mode': mode}
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f'non-regular file, symlink or hardlink: {path}')
    with path.open('rb') as stream:
        data = stream.read()
    return {'kind': 'file', 'mode': mode, 'size': len(data), 'sha256': digest(data)}


def walk(root, prefix=None, registered=()):
    """Yield paths without following links or entering protected/nested trees."""
    start = root if prefix is None else location(root, prefix)
    if prefix is not None and not start.exists():
        raise ValueError(f'missing scan path: {prefix}')
    pending = [start]
    while pending:
        path = pending.pop()
        if path != root:
            name = path.relative_to(root).as_posix()
            reason = protected(name, registered)
            if path.is_symlink():
                yield name, 'symlink boundary'
                continue
            if path.is_dir() and os.path.lexists(path / '.git'):
                yield name, 'nested repository boundary'
                continue
            yield name, reason
            if reason:
                continue
        if path.is_dir():
            pending.extend(sorted(path.iterdir(), reverse=True))


def scan(root, prefix=None):
    root = repository(root)
    tracked, dirty = git_state(root)
    directories = tracked_directories(tracked)
    rows = []
    for name, reason in walk(root, prefix, registered_assets(root)):
        path = root / name
        if not reason:
            if name in dirty:
                reason = 'uncommitted tracked changes'
            elif name not in tracked | directories and not generated(name, path.is_dir()):
                reason = 'untracked work; preserve'
        row = {'path': name, 'protected': reason, 'tracked': name in tracked}
        if not reason:
            try:
                row.update(state(path))
                row['category'] = 'generated' if generated(name, path.is_dir()) else 'needs semantic evidence'
            except ValueError as error:
                row['protected'] = str(error)
        rows.append(row)
    return {'root': str(root), 'entries': rows, 'read_only': True}


def external(session, root):
    session = Path(session).absolute()
    plain_parents(session)
    if any(os.path.lexists(parent / '.git') for parent in (session, *session.parents)):
        raise ValueError('session cannot be stored in another Git repository')
    workflow = Path(__file__).resolve().parents[2]
    gitdir = Path(git(root, 'rev-parse', '--absolute-git-dir'))
    common = Path(git(root, 'rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = root / common
    for boundary in (root, workflow, gitdir.resolve(), common.resolve()):
        if session == boundary or boundary in session.parents or session in boundary.parents:
            raise ValueError('session must be outside repository, workflow and Git metadata')
    return session


def save(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(packed(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def make_plan(root, session, proposal):
    root = repository(root)
    session = external(session, root)
    tracked, dirty = git_state(root)
    directories = tracked_directories(tracked)
    registered = registered_assets(root)
    if not isinstance(proposal, dict) or not isinstance(proposal.get('items'), list) or not proposal['items']:
        raise ValueError('proposal requires nonempty items')
    operations, selections = [], []
    index = index_state(root)
    for item in proposal['items']:
        name = relative(item['path'])
        if any(name == old or name.startswith(old + '/') or old.startswith(name + '/') for old in selections):
            raise ValueError('overlapping selections')
        selections.append(name)
        action = item.get('action')
        if action not in ('remove', 'replace'):
            raise ValueError('action must be remove or replace')
        for key in ('reason', 'impact'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'missing {key}: {name}')
        for key in ('evidence', 'checks'):
            if not isinstance(item.get(key), list) or not item[key] or not all(isinstance(x, str) and x.strip() for x in item[key]):
                raise ValueError(f'missing {key}: {name}')
        regeneration = item.get('regenerate')
        if regeneration is not None and (not isinstance(regeneration, str) or not regeneration.strip()):
            raise ValueError('regenerate must describe a verified regeneration command')
        path = location(root, name)
        if not path.exists():
            raise ValueError(f'missing selection: {name}')
        names = [(name, protected(name, registered))] if path.is_file() else list(walk(root, name, registered))
        if action == 'replace' and not path.is_file():
            raise ValueError('replace requires a regular tracked text file')
        for leaf, reason in names:
            node = location(root, leaf)
            old = state(node)
            if (reason or leaf in dirty or (leaf not in tracked | directories
                    and (action == 'replace' or not (generated(leaf, old['kind'] == 'directory') or regeneration)))):
                raise ValueError(f'protected or uncommitted work: {leaf}: {reason or "dirty/untracked"}')
            op = {'path': leaf, 'before': old, 'after': None, 'action': action, 'index': index.get(leaf)}
            if old['kind'] == 'file':
                original = node.read_bytes()
                if digest(original) != old['sha256']:
                    raise ValueError(f'changed during planning: {leaf}')
                op['original'] = encoded(original)
            if action == 'replace':
                original.decode('utf-8')
                if '\x00' in original.decode('utf-8') or not isinstance(item.get('replacement'), str):
                    raise ValueError('replacement requires UTF-8 text')
                data = item['replacement'].encode('utf-8')
                op['replacement'] = encoded(data)
                op['after'] = {'kind': 'file', 'mode': old['mode'], 'size': len(data), 'sha256': digest(data)}
            operations.append(op)
    # Descendants before parents for removal; restore uses the reverse order.
    operations.sort(key=lambda op: (-len(PurePosixPath(op['path']).parts), op['path']))
    plan = {'schema': 1, 'root': str(root), 'gitdir': git(root, 'rev-parse', '--absolute-git-dir'),
            'proposal': proposal, 'operations': operations, 'selections': selections}
    plan_id = digest(packed(plan))
    session.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(session / 'plan.json', plan)
    save(session / 'journal.json', {'plan_id': plan_id, 'phase': 'planned', 'done': [], 'pending': None,
                                   'restored': [], 'restore_pending': None})
    return {'session': str(session), 'plan_id': plan_id, 'selected': selections,
            'operations': len(operations), 'bytes': sum(op['before'].get('size', 0) for op in operations)}


def load_session(session):
    session = Path(session).absolute()
    plain_parents(session)
    for name in ('plan.json', 'journal.json', 'lock'):
        path = session / name
        if path.is_symlink() or (path.exists() and path.stat().st_nlink != 1):
            raise ValueError('unsafe session file')
    plan = json.loads((session / 'plan.json').read_text())
    root = repository(plan['root'])
    external(session, root)
    if plan['schema'] != 1 or git(root, 'rev-parse', '--absolute-git-dir') != plan['gitdir']:
        raise ValueError('repository identity changed')
    journal = json.loads((session / 'journal.json').read_text())
    if journal['plan_id'] != digest(packed(plan)):
        raise ValueError('plan changed; obtain fresh approval')
    registered = registered_assets(root)
    for op in plan['operations']:
        relative(op['path'])
        if protected(op['path'], registered):
            raise ValueError('protected plan operation')
        for field, expected in (('original', op['before']), ('replacement', op['after'])):
            if expected and expected['kind'] == 'file':
                data = base64.b64decode(op[field], validate=True)
                if digest(data) != expected['sha256'] or len(data) != expected['size']:
                    raise ValueError('snapshot integrity failure')
    return session, root, plan, journal


def write_file(path, data, mode, exclusive=False):
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, mode)
    else:
        fd, temporary = tempfile.mkstemp(prefix='.lean-clean-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def execute(session, approval=None, restore=False):
    session, root, plan, journal = load_session(session)
    # One session writer at a time. Other repo writers must be stopped by the caller.
    with (session / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session, root, plan, journal = load_session(session)
        if restore:
            if journal['phase'] == 'planned':
                return {'phase': 'planned', 'restored': []}
            return restore_plan(session, root, plan, journal)
        if approval != journal['plan_id']:
            raise ValueError('apply requires the exact approved plan_id')
        if journal['phase'] in ('restoring', 'restored'):
            raise ValueError('restored session cannot be applied again')
        expected = {op['path']: op for op in plan['operations']}
        # Extra files in a selected directory invalidate the entire apply preflight.
        for selection in plan['selections']:
            if (root / selection).is_dir():
                current = {name for name, _ in walk(root, selection)}
                if current - set(expected):
                    raise ValueError(f'new descendants in selection: {selection}')
        _, dirty = git_state(root)
        index = index_state(root)
        for op in plan['operations']:
            name = op['path']
            if index.get(name) != op['index']:
                raise ValueError(f'Git index changed since plan: {name}')
            now = state(location(root, name))
            if name in journal['done']:
                if now != op['after']:
                    raise ValueError(f'changed after cleanup: {name}')
            elif name == journal['pending'] and now == op['after']:
                continue
            elif now != op['before'] or (name in dirty and name != journal['pending']):
                raise ValueError(f'changed since plan: {name}')
        journal['phase'] = 'applying'
        save(session / 'journal.json', journal)
        for op in plan['operations']:
            name = op['path']
            if name in journal['done']:
                continue
            path = location(root, name)
            if name == journal['pending'] and state(path) == op['after']:
                pass  # A prior process applied this operation before recording done.
            else:
                if state(path) != op['before']:
                    raise ValueError(f'changed during apply: {name}')
                journal['pending'] = name
                save(session / 'journal.json', journal)
                if op['action'] == 'replace':
                    write_file(path, base64.b64decode(op['replacement']), op['after']['mode'])
                elif op['before']['kind'] == 'directory':
                    path.rmdir()
                else:
                    path.unlink()
            journal['done'].append(name)
            journal['pending'] = None
            save(session / 'journal.json', journal)
        journal['phase'] = 'applied'
        save(session / 'journal.json', journal)
        return {'phase': 'applied', 'changed': journal['done'], 'session': str(session)}


def restore_plan(session, root, plan, journal):
    changed = set(journal['done'])
    if journal['pending']:
        op = next(op for op in plan['operations'] if op['path'] == journal['pending'])
        now = state(location(root, op['path']))
        if now == op['after']:
            changed.add(op['path'])
        elif now != op['before']:
            raise ValueError('ambiguous interrupted operation; retain snapshot')
    ops = [op for op in reversed(plan['operations']) if op['path'] in changed]
    for op in ops:
        name = op['path']
        now = state(location(root, name))
        if name in journal['restored'] or name == journal['restore_pending']:
            if now == op['before']:
                continue
        if now != op['after']:
            raise ValueError(f'restore would overwrite subsequent work: {name}')
    journal['phase'] = 'restoring'
    save(session / 'journal.json', journal)
    for op in ops:
        name = op['path']
        if name in journal['restored']:
            continue
        path = location(root, name)
        if name == journal['restore_pending'] and state(path) == op['before']:
            pass
        else:
            if state(path) != op['after']:
                raise ValueError(f'changed during restore: {name}')
            journal['restore_pending'] = name
            save(session / 'journal.json', journal)
            if op['before']['kind'] == 'directory':
                path.mkdir(mode=op['before']['mode'])
                os.chmod(path, op['before']['mode'])
            else:
                write_file(path, base64.b64decode(op['original']), op['before']['mode'],
                           exclusive=op['after'] is None)
        journal['restored'].append(name)
        journal['restore_pending'] = None
        save(session / 'journal.json', journal)
    journal['phase'] = 'restored'
    save(session / 'journal.json', journal)
    return {'phase': 'restored', 'restored': journal['restored'], 'session': str(session)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inventory = commands.add_parser('scan')
    inventory.add_argument('--root', required=True)
    inventory.add_argument('--path')
    plan = commands.add_parser('plan')
    plan.add_argument('--root', required=True)
    plan.add_argument('--session', required=True)
    plan.add_argument('--proposal', required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('--session', required=True)
    apply.add_argument('--approval', required=True)
    restore = commands.add_parser('restore')
    restore.add_argument('--session', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'scan':
            result = scan(args.root, args.path)
        elif args.command == 'plan':
            result = make_plan(args.root, args.session, json.loads(Path(args.proposal).read_text()))
        else:
            result = execute(args.session, getattr(args, 'approval', None), args.command == 'restore')
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}; retain session snapshots and inspect journal before retry', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
