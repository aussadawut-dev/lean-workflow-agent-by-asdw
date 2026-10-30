"""Opt-in requirement intake and bounded batches, independent of full-mode leases.

The ledger is a tracker record, not validation evidence. Closure uses the existing
whole-checkout receipt and gate; it never claims task-scoped coverage.
"""
import copy
import contextlib
import json
import re

from .util import LeanError, locked, safe_path, write_text

PATH = 'docs/tracking/INTAKE.md'
KINDS = ('clarification', 'blocker', 'direction', 'feature')
STATES = ('active', 'queued', 'superseded', 'cancelled')
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}')
PREFIX = '# Requirement intake\n\n```json\n'
SUFFIX = '```\n'


def require(condition, message):
    if not condition:
        raise LeanError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def load(root):
    path = safe_path(root, PATH)
    if not path.exists():
        return {'schema': 1, 'requirements': {}, 'batches': {}}
    content = path.read_text()
    require(content.startswith(PREFIX) and content.endswith(SUFFIX), 'invalid intake ledger format')
    from .util import unique_keys
    return json.loads(content[len(PREFIX):-len(SUFFIX)], object_pairs_hook=unique_keys)


def validate(data):
    require(isinstance(data, dict) and data.get('schema') == 1, 'invalid intake schema')
    reqs, batches = data.get('requirements'), data.get('batches')
    require(isinstance(reqs, dict) and isinstance(batches, dict), 'invalid intake records')
    for rid, row in reqs.items():
        require(IDENTIFIER.fullmatch(rid) and isinstance(row, dict), 'invalid requirement ID/record')
        require(row.get('kind') in KINDS and row.get('status') in STATES, f'invalid classification/state: {rid}')
        require(all(text(row.get(k)) for k in ('text', 'task', 'acceptance')), f'missing traceability: {rid}')
        for field in ('dependencies', 'supersedes'):
            links = row.get(field)
            require(isinstance(links, list) and all(isinstance(x, str) for x in links), f'invalid {field}: {rid}')
            require(len(links) == len(set(links)) and all(x in reqs and x != rid for x in links),
                    f'invalid {field} reference: {rid}')
        if row['status'] == 'cancelled':
            require(text(row.get('reason')), f'cancellation requires reason: {rid}')
    for rid, row in reqs.items():
        if row['status'] == 'superseded':
            require(any(rid in other['supersedes'] for other in reqs.values()), f'missing replacement: {rid}')
    visiting, visited = set(), set()

    def visit(rid):
        require(rid not in visiting, 'requirement dependency/supersession cycle')
        if rid in visited:
            return
        visiting.add(rid)
        for dep in reqs[rid]['dependencies'] + reqs[rid]['supersedes']:
            visit(dep)
        visiting.remove(rid)
        visited.add(rid)

    for rid in reqs:
        visit(rid)
    owners, assigned = set(), set()
    for bid, batch in batches.items():
        require(IDENTIFIER.fullmatch(bid) and isinstance(batch, dict), 'invalid batch ID/record')
        require(text(batch.get('controller')), f'missing controller: {bid}')
        require(batch.get('status') in ('implementing', 'paused', 'frozen', 'closed', 'retired'), f'invalid batch state: {bid}')
        require(isinstance(batch.get('history'), list) and all(text(x) for x in batch['history']),
                f'invalid contract history: {bid}')
        members = batch.get('requirements')
        require(isinstance(members, list) and members and all(isinstance(x, str) and x in reqs for x in members),
                f'invalid batch requirements: {bid}')
        require(len(members) == len(set(members)), f'duplicate batch requirements: {bid}')
        if batch['status'] in ('implementing', 'frozen'):
            require(batch['controller'] not in owners, 'one primary batch per Controller; checkpoint first')
            owners.add(batch['controller'])
        if batch['status'] not in ('closed', 'retired'):
            require(not assigned.intersection(members), 'requirement already owned by another batch')
            assigned.update(members)
            require(all(reqs[x]['status'] == 'active' for x in members), f'non-active batch requirement: {bid}')
        if batch['status'] in ('frozen', 'closed'):
            from .guard import parse
            require(text(batch.get('contract')), f'missing frozen contract: {bid}')
            parse(batch.get('contract', ''))
            require(batch.get('snapshot') == {x: reqs[x] for x in members}, f'frozen scope changed: {bid}')
    require({x for x in assigned} == {x for x, r in reqs.items() if r['status'] == 'active'
                                    and not any(b['status'] == 'closed' and x in b['requirements']
                                                for b in batches.values())}, 'active requirement has no batch')


def readiness(root, data, bid):
    from . import evidence, gate
    batch = data['batches'][bid]
    frozen = batch['status'] in ('frozen', 'closed')
    contract = batch.get('contract', '')
    review = 'NOT_RUN'
    if frozen:
        try:
            evidence.check_review(root, contract)
            review = 'PASS'
        except (OSError, ValueError, KeyError, TypeError) as error:
            review = 'NOT_CURRENT: ' + str(error)
            attestation = batch.get('review', {})
            if (not high_review(root, contract) and attestation.get('state') == evidence.review_state(root)
                    and text(attestation.get('evidence')) and text(attestation.get('base'))
                    and evidence.shipping_gap(root, attestation['base']) is None):
                review = 'PASS'
    gate_state = gate.status(root)
    return {'batch': bid, 'implementation': 'READY' if frozen else 'NOT_READY',
            'review': review, 'gate': gate_state, 'coverage': 'whole shipping checkout',
            'can_close': frozen and review == 'PASS' and gate_state == 'PASS'}


def high_review(root, contract):
    from . import evidence, guard
    match = guard.LINE.fullmatch(contract)
    return (not match or match.group(1) == 'HIGH' or match.group(2) == 'VERY_HIGH'
            or bool(evidence.high_risk_changes(root)))


def parser_for(commands):
    intake = commands.add_parser('intake', help='optional requirement ledger, in every mode')
    actions = intake.add_subparsers(dest='action', required=True)
    add = actions.add_parser('add')
    for field in ('id', 'text', 'task', 'acceptance'):
        add.add_argument('--' + field, required=True)
    add.add_argument('--kind', choices=KINDS, required=True)
    add.add_argument('--depends', action='append', default=[])
    add.add_argument('--supersedes', action='append', default=[])
    cancel = actions.add_parser('cancel')
    cancel.add_argument('--id', required=True)
    cancel.add_argument('--reason', required=True)
    actions.add_parser('list')
    actions.add_parser('check')
    batch = commands.add_parser('batch', help='explicit scope, ownership, freeze and readiness')
    actions = batch.add_subparsers(dest='action', required=True)
    for name in ('start', 'checkpoint', 'resume', 'freeze', 'reopen', 'readiness', 'finish', 'scope', 'review', 'retire'):
        sub = actions.add_parser(name)
        sub.add_argument('--id', required=True)
        if name == 'start':
            sub.add_argument('--controller', required=True)
        if name in ('start', 'scope'):
            sub.add_argument('--requirements', nargs='+', required=True)
        if name in ('checkpoint', 'reopen', 'scope', 'retire'):
            sub.add_argument('--reason', required=True)
        if name == 'review':
            sub.add_argument('--evidence', required=True)
        if name == 'freeze':
            sub.add_argument('--contract', required=True)


def command(root, args):
    read_only = (args.command == 'intake' and args.action in ('list', 'check')
                 or args.command == 'batch' and args.action == 'readiness')
    # Atomic replacement makes an unlocked read a consistent snapshot. Inspection
    # must also work before runtime state exists and on read-only installations.
    with contextlib.nullcontext() if read_only else locked(root, 'intake.lock'):
        data = load(root)
        validate(data)
        reqs, batches = data['requirements'], data['batches']
        if args.command == 'intake':
            if args.action == 'list':
                print(json.dumps(data, indent=2))
                return 0
            if args.action == 'check':
                print('intake ok')
                return 0
            if args.action == 'add':
                require(args.id not in reqs, 'requirement ID already exists')
                require(args.kind == 'direction' or not args.supersedes, 'only direction supersedes requirements')
                for rid in args.supersedes:
                    require(rid in reqs and reqs[rid]['status'] == 'queued', 'checkpoint/reopen active scope before superseding')
                reqs[args.id] = {'kind': args.kind, 'text': args.text, 'task': args.task,
                                'acceptance': args.acceptance, 'dependencies': args.depends,
                                'supersedes': args.supersedes, 'status': 'queued'}
                for rid in args.supersedes:
                    reqs[rid]['status'] = 'superseded'
            else:
                require(args.id in reqs and reqs[args.id]['status'] == 'queued', 'only queued requirements can be cancelled')
                require(text(args.reason), 'reason required')
                reqs[args.id].update(status='cancelled', reason=args.reason)
        elif args.action == 'start':
            require(args.id not in batches, 'batch ID already exists; resume paused batches')
            require(all(x in reqs and reqs[x]['status'] == 'queued' for x in args.requirements),
                    'batch requires queued, unowned requirements')
            completed = {x for b in batches.values() if b['status'] == 'closed' for x in b['requirements']}
            require(all(dep in completed or dep in args.requirements for x in args.requirements
                        for dep in reqs[x]['dependencies']), 'unfinished dependencies')
            batches[args.id] = {'controller': args.controller, 'requirements': args.requirements,
                               'status': 'implementing', 'history': []}
            for rid in args.requirements:
                reqs[rid]['status'] = 'active'
        else:
            require(args.id in batches, 'unknown batch')
            batch = batches[args.id]
            status = batch['status']
            if args.action == 'readiness':
                print(json.dumps(readiness(args.evidence_root, data, args.id), indent=2))
                return 0
            if args.action == 'review':
                from . import evidence
                require(status == 'frozen' and text(args.evidence), 'freeze and review evidence required')
                require(not high_review(args.evidence_root, batch['contract']),
                        'HIGH depth requires the independent reviewer receipt; cannot self-attest')
                batch['review'] = {'state': evidence.review_state(args.evidence_root),
                                   'base': evidence.head_tree(args.evidence_root),
                                   'evidence': args.evidence}
            elif args.action == 'scope':
                require(status == 'implementing' and text(args.reason), 'reopen before amending scope; reason required')
                old = batch['requirements']
                require(all(x in reqs and (reqs[x]['status'] == 'queued' or x in old)
                            for x in args.requirements), 'scope requires unowned requirements')
                completed = {x for b in batches.values() if b['status'] == 'closed' for x in b['requirements']}
                require(all(dep in completed or dep in args.requirements for x in args.requirements
                            for dep in reqs[x]['dependencies']), 'unfinished dependencies')
                batch.setdefault('amendments', []).append({'requirements': old, 'reason': args.reason})
                for rid in old:
                    reqs[rid]['status'] = 'queued'
                batch['requirements'] = args.requirements
                for rid in args.requirements:
                    reqs[rid]['status'] = 'active'
            elif args.action == 'retire':
                require(status in ('implementing', 'paused') and text(args.reason),
                        'reopen frozen scope before retiring; reason required')
                batch.update(status='retired', reason=args.reason)
                for rid in batch['requirements']:
                    reqs[rid]['status'] = 'queued'
            elif args.action == 'checkpoint':
                require(status == 'implementing', 'reopen frozen batch before checkpoint')
                require(text(args.reason), 'checkpoint reason required')
                batch.update(status='paused', checkpoint=args.reason)
            elif args.action == 'resume':
                require(status == 'paused', 'only paused batch can resume')
                batch['status'] = 'implementing'
            elif args.action == 'freeze':
                from .guard import parse
                require(status == 'implementing', 'only implementation can freeze')
                contract, _ = parse(args.contract)
                require(contract not in batch['history'], 'invalidated contract: use a new contract after reopening')
                batch.update(status='frozen', contract=contract,
                             snapshot=copy.deepcopy({x: reqs[x] for x in batch['requirements']}))
            elif args.action == 'reopen':
                require(status == 'frozen' and text(args.reason), 'only frozen batch can reopen with a reason')
                batch['history'].append(batch.pop('contract'))
                batch.pop('snapshot')
                batch.pop('review', None)
                batch.update(status='implementing', invalidation=args.reason)
                print('Scope reopened: implementation/review/gate readiness invalidated; freeze with a new contract.')
            elif args.action == 'finish':
                require(status == 'frozen', 'only frozen batch can finish')
                result = readiness(args.evidence_root, data, args.id)
                require(result['can_close'], 'closure requires current whole-checkout review and gate PASS')
                batch.update(status='closed', closure=result)
        validate(data)
        write_text(safe_path(root, PATH), PREFIX + json.dumps(data, indent=2, ensure_ascii=False) + '\n' + SUFFIX)
        print('intake updated; ledger is a tracker attestation, not validation evidence')
    return 0
