#!/usr/bin/env python3
"""Offline, project-local model catalog proposals. Never changes runtime settings."""
import argparse
import contextlib
from datetime import datetime, timezone
import difflib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

PROVIDERS = ('codex', 'claude')
HOSTS = {'codex': {'developers.openai.com', 'platform.openai.com', 'learn.chatgpt.com'},
         'claude': {'code.claude.com', 'docs.anthropic.com', 'platform.claude.com', 'www.anthropic.com'}}
RUNTIMES = {'codex': {'codex-desktop', 'codex-cli', 'codex-ide'}, 'claude': {'claude-code'}}
EFFORTS = {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}
MAX_AGE_DAYS = 30


def fail(message):
    raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def parse_json(content):
    def duplicate(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        fail('non-finite JSON value: ' + value)
    return json.loads(content, object_pairs_hook=duplicate, parse_constant=invalid)


def load(path):
    return parse_json(path.read_bytes())


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def age_days(value, now):
    if not nonblank(value):
        fail('missing evidence timestamp')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        fail('invalid evidence timestamp')
    if date.tzinfo is None:
        fail('evidence timestamp requires timezone')
    age = (now - date).total_seconds() / 86400
    if age < 0:
        fail('evidence timestamp is in the future')
    return age


def validate(catalog, now=None):
    now = now or datetime.now(timezone.utc)
    if (not isinstance(catalog, dict) or type(catalog.get('version')) is not int
            or catalog['version'] != 1 or not isinstance(catalog.get('models'), list)):
        fail('invalid catalog version/models')
    identities, stale = set(), []
    for entry in catalog['models']:
        if not isinstance(entry, dict):
            fail('model entry must be an object')
        provider = entry.get('provider')
        if not isinstance(provider, str) or provider not in PROVIDERS:
            fail('invalid model provider')
        for field in ('id', 'runtime_version'):
            if not nonblank(entry.get(field)):
                fail('missing model ' + field)
        if not isinstance(entry.get('runtime'), str) or entry['runtime'] not in RUNTIMES[provider]:
            fail('invalid model runtime')
        identity = (provider, entry['runtime'], entry['runtime_version'], entry['id'])
        if identity in identities:
            fail('duplicate model identity')
        identities.add(identity)
        if entry.get('lifecycle') not in ('active', 'deprecated', 'retired'):
            fail('invalid model lifecycle')
        if entry.get('availability') not in ('available', 'unavailable', 'unknown'):
            fail('invalid model availability')
        efforts = entry.get('supported_efforts')
        if (not isinstance(efforts, list) or not all(isinstance(x, str) and x in EFFORTS for x in efforts)
                or len(efforts) != len(set(efforts))):
            fail('invalid supported efforts')
        sources = entry.get('sources')
        if not isinstance(sources, list) or not sources:
            fail('model requires official sources')
        old = False
        for source in sources:
            if not isinstance(source, dict) or not nonblank(source.get('url')):
                fail('invalid source')
            url = urlsplit(source['url'])
            if (url.scheme != 'https' or url.hostname not in HOSTS[provider]
                    or url.username or url.password or url.port not in (None, 443)):
                fail('source must use an official HTTPS host')
            old |= age_days(source.get('checked_at'), now) > MAX_AGE_DAYS
        if entry['availability'] != 'unknown':
            observation = entry.get('runtime_observation')
            if not isinstance(observation, dict) or not nonblank(observation.get('evidence')):
                fail('known availability requires runtime observation')
            old |= age_days(observation.get('checked_at'), now) > MAX_AGE_DAYS
        if 'alias_target' in entry and not nonblank(entry['alias_target']):
            fail('invalid alias target')
        if old:
            stale.append(identity)
    return stale


def current(root):
    path = root / '.lean/model-catalog.json'
    if path.is_symlink():
        fail('catalog must not be a symlink')
    content = path.read_bytes() if path.exists() else None
    catalog = parse_json(content) if content is not None else {'version': 1, 'models': []}
    validate(catalog)
    checksum = hashlib.sha256(content).hexdigest() if content is not None else None
    return catalog, checksum


def selected(provider):
    return set(PROVIDERS) if provider == 'all' else {provider}


def fresh(catalog, providers):
    subset = dict(catalog, models=[x for x in catalog['models'] if x['provider'] in providers])
    if validate(subset):
        fail('selected model evidence is stale; research again before apply')


def preview(root, candidate_path, provider):
    candidate = load(candidate_path)
    validate(candidate)
    providers = selected(provider)
    if {x['provider'] for x in candidate['models']} != providers:
        fail('candidate must contain exactly the selected providers')
    fresh(candidate, providers)
    before, checksum = current(root)
    after = dict(before, models=[x for x in before['models'] if x['provider'] not in providers] + candidate['models'])
    proposal = {'version': 1, 'provider': provider, 'base_sha256': checksum, 'catalog': after}
    return {'proposal': proposal, 'sha256': digest(proposal),
            'diff': ''.join(difflib.unified_diff(encoded(before).decode().splitlines(True),
                         encoded(after).decode().splitlines(True), fromfile='current', tofile='proposed'))}


@contextlib.contextmanager
def locked(root):
    runtime = root / '.agent-runtime'
    if runtime.is_symlink():
        fail('runtime directory must not be a symlink')
    runtime.mkdir(exist_ok=True)
    path = runtime / 'model-catalog.lock'
    if path.is_symlink():
        fail('catalog lock must not be a symlink')
    with path.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def atomic_write(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def apply(root, report_path, approved_digest):
    report = load(report_path)
    proposal = report.get('proposal') if isinstance(report, dict) else None
    if (not isinstance(proposal, dict) or type(proposal.get('version')) is not int
            or proposal['version'] != 1 or proposal.get('provider') not in ('codex', 'claude', 'all')
            or 'base_sha256' not in proposal):
        fail('invalid proposal')
    checksum = digest(proposal)
    if report.get('sha256') != checksum or approved_digest != checksum:
        fail('proposal digest does not match approval')
    target = proposal.get('catalog')
    validate(target)
    providers = selected(proposal['provider'])
    if not providers.issubset({x['provider'] for x in target['models']}):
        fail('proposal lacks selected provider models')
    fresh(target, providers)
    # The only writable destination is the fixed project catalog. No runtime config writes.
    if (root / '.lean').is_symlink() or not (root / '.lean').is_dir():
        fail('project .lean directory must exist and not be a symlink')
    with locked(root):
        before, base = current(root)
        if before == target:
            return {'applied': False, 'unchanged': True}
        if base != proposal['base_sha256']:
            fail('catalog changed since preview; create a new proposal')
        retained = lambda catalog: [x for x in catalog['models'] if x['provider'] not in providers]
        if retained(before) != retained(target):
            fail('proposal modifies unselected provider')
        if {k: v for k, v in before.items() if k != 'models'} != {k: v for k, v in target.items() if k != 'models'}:
            fail('proposal modifies catalog extensions')
        atomic_write(root / '.lean/model-catalog.json', target)
    return {'applied': True, 'unchanged': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    plan = commands.add_parser('preview')
    plan.add_argument('--provider', choices=(*PROVIDERS, 'all'), required=True)
    plan.add_argument('--candidate', type=Path, required=True)
    commit = commands.add_parser('apply')
    commit.add_argument('--proposal', type=Path, required=True)
    commit.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == 'check':
            catalog, checksum = current(root)
            result = {'present': checksum is not None, 'models': len(catalog['models']),
                      'stale': validate(catalog), 'max_age_days': MAX_AGE_DAYS}
        elif args.command == 'preview':
            result = preview(root, args.candidate, args.provider)
        else:
            result = apply(root, args.proposal, args.sha256)
        print(encoded(result).decode(), end='')
    except (ValueError, OSError, TypeError, OverflowError) as error:
        print('model catalog error: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
