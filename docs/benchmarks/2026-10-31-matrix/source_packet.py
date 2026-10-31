"""Prepare exact, cited source blocks from known entry paths, companions and named imports.

Heuristic retrieval only: explicit omissions are not proof that a dependency or behavior is absent.
No model, network, application execution or source writes. Stdlib only.
"""
import argparse
from collections import deque
from pathlib import Path
import re

EXPORT = re.compile(r'\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|const|class|enum)\s+(\w+)')
IMPORT = re.compile(r'import\s+(?!type\b)\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']', re.S)
SUFFIX = re.compile(r'(?:\.test|\.controller|\.service|\.repository|\.usecases|\.module)$')


def family(path):
    stem = path.stem
    while True:
        shorter = SUFFIX.sub('', stem)
        if shorter == stem:
            return stem.removeprefix('prisma-').removesuffix('-admin').removesuffix('-removed').replace('identities', 'identity')
        stem = shorter


def entries_for(root, question):
    entries = re.findall(r'(?:apps|packages|prisma)/[A-Za-z0-9_./-]+\.(?:ts|sql)', question)
    if entries:
        directory = Path(entries[0]).parent
        for short in re.findall(r'(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+\.(?:ts|sql))', question):
            candidate = (directory / short).as_posix()
            if candidate not in entries and (root / candidate).is_file():
                entries.append(candidate)
    return entries


def collect(root, entries, line_budget=2200, depth=1, identifiers=()):
    root = root.resolve()
    files = sorted(path for path in root.rglob('*') if path.is_file() and not path.is_symlink() and path.suffix in ('.ts', '.tsx', '.sql')
                   and not path.name.endswith('.d.ts')
                   and not any(part in ('node_modules', '.git', 'generated', 'generated-prisma', 'dist', 'build', 'coverage', '.next') for part in path.relative_to(root).parts))
    # Read text once; no source excerpts are synthesized or paraphrased.
    text = {path: path.read_text(errors='replace') for path in files}
    exports = {}
    for path, content in text.items():
        for match in EXPORT.finditer(content):
            exports.setdefault(match.group(1), []).append(path)
    queue = deque()
    include_web = any(entry.startswith('apps/web/') for entry in entries)
    for entry in entries:
        path = (root / entry).resolve()
        if not path.is_relative_to(root) or path not in text:
            raise ValueError(f'Entry must be an existing source file under root: {entry}')
        queue.append((path, 0, 'known entry'))
        key = family(path)
        # Exact family companions, including tests; no task-answer/rubric knowledge.
        for companion in files:
            companion_family = family(companion)
            same_family = companion_family == key or (len(key) >= 4 and ('-' + key + '-') in ('-' + companion_family + '-'))
            is_web = companion.relative_to(root).as_posix().startswith('apps/web/')
            if key and key not in ('migration', 'index', 'schema', 'app') and same_family and (include_web or not is_web):
                queue.append((companion, depth, f'filename companion: {key}'))
    for path, content in text.items():
        if any(re.search(r'\b' + re.escape(identifier) + r'\b', content) for identifier in identifiers):
            queue.append((path, 0, 'literal identifier from question'))
    selected, omitted, unresolved = [], [], set()
    seen = set()
    used = 0
    while queue:
        queue = deque(sorted(queue, key=lambda item: item[1]))
        path, level, reason = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        content = text[path]
        count = len(content.splitlines())
        if used + count > line_budget:
            omitted.append((path, f'{count} complete lines exceeds remaining retrieval budget'))
            continue
        used += count
        selected.append((path, content, reason))
        if level >= depth:
            continue
        for match in IMPORT.finditer(content):
            package = match.group(2)
            if not (package.startswith('.') or package.startswith('@casetodian/')):
                continue
            for spec in match.group(1).split(','):
                spec = spec.strip()
                if not spec or spec.startswith('type '):
                    continue
                name = spec.split(' as ')[0].strip()
                candidates = exports.get(name, [])
                if package.startswith('@casetodian/'):
                    owner = package.split('/')[1]
                    candidates = [candidate for candidate in candidates if candidate.relative_to(root).as_posix().startswith('packages/' + owner + '/')]
                elif package.startswith('.'):
                    expected = (path.parent / package).with_suffix('.ts').resolve()
                    exact = [candidate for candidate in candidates if candidate == expected]
                    if exact:
                        candidates = exact
                if not include_web:
                    candidates = [candidate for candidate in candidates if not candidate.relative_to(root).as_posix().startswith('apps/web/')]
                if not candidates:
                    unresolved.add(f'{path.relative_to(root)} imports {name} from {package}')
                for dependency in candidates:
                    queue.append((dependency, level + 1, f'named import {name} from {path.relative_to(root)}'))
    output = ['# Exact source retrieval packet', '',
              'Heuristic aid, not a complete dependency graph or safety proof. Original files remain available.',
              'Read omitted/unresolved or deeper dependencies when material to a requested conclusion.',
              f'Included {len(selected)} complete files, {used} lines. Depth limit={depth}.', '']
    for path, content, reason in selected:
        rel = 'application/' + path.relative_to(root).as_posix()
        output.extend([f'## {rel}', f'Retrieval: {reason}', '```text'])
        output.extend(f'{index}: {line}' for index, line in enumerate(content.splitlines(), 1))
        output.extend(['```', ''])
    output.append('## Omitted complete files (not absence evidence)')
    output.extend(f'- application/{path.relative_to(root)}: {reason}' for path, reason in omitted)
    output.append('## Unresolved named imports (not absence evidence)')
    output.extend('- ' + item for item in sorted(unresolved))
    return '\n'.join(output) + '\n', {'files': len(selected), 'lines': used, 'omitted': len(omitted), 'unresolved': len(unresolved)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--entry', action='append', required=True)
    parser.add_argument('--line-budget', type=int, default=2200)
    args = parser.parse_args()
    packet, _ = collect(args.root, args.entry, args.line_budget)
    print(packet, end='')


if __name__ == '__main__':
    main()
