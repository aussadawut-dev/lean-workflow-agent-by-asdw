#!/usr/bin/env python3
"""Compare project model evidence with the local Codex CLI cache, without writes or networking."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import model_catalog


def check(root, cache_path, max_cache_days=14):
    root = Path(root)
    catalog_path = root / '.lean/model-catalog.json'
    if not catalog_path.is_file():
        return [], ['no .lean/model-catalog.json; nothing to compare']
    catalog = model_catalog.load(catalog_path)
    drift, notes = [], []
    for provider, runtime, version, model_id in model_catalog.validate(catalog):
        drift.append(f'evidence older than {model_catalog.MAX_AGE_DAYS} days: {provider}/{model_id} '
                     f'({runtime} {version}); run /lean-catalog {provider}')
    cache_file = Path(cache_path)
    if not cache_file.is_file():
        notes.append(f'Codex model cache not found at {cache_file}; Codex models not compared')
        return drift, notes
    cache = model_catalog.load(cache_file)
    if not isinstance(cache, dict) or not isinstance(cache.get('models'), list):
        raise ValueError('Codex cache must contain a models list')
    fetched = cache.get('fetched_at', '')
    try:
        age = model_catalog.age_days(fetched, datetime.now(timezone.utc))
        if age > max_cache_days:
            notes.append(f'Codex model cache is {int(age)} days old; start Codex once to refresh it')
    except ValueError:
        notes.append('Codex model cache has no valid fetched_at')
    live = {}
    for entry in cache['models']:
        if not isinstance(entry, dict) or not model_catalog.nonblank(entry.get('slug')):
            raise ValueError('invalid model in Codex cache')
        slug = entry['slug']
        priority = entry.get('priority', 10**6)
        levels = entry.get('supported_reasoning_levels')
        if (slug in live or type(priority) not in (int, float)
                or not isinstance(levels, list)
                or any(not isinstance(x, dict) or not model_catalog.nonblank(x.get('effort')) for x in levels)):
            raise ValueError('invalid or duplicate model metadata in Codex cache')
        live[slug] = entry
    visible = {slug for slug, entry in live.items() if entry.get('visibility') == 'list'}
    ranks = []
    catalogued = [entry for entry in catalog['models']
                  if entry['provider'] == 'codex' and entry['runtime'] == 'codex-cli']
    for entry in catalogued:
        slug = entry['id']
        if slug not in visible:
            drift.append(f'catalogued Codex model {slug} is no longer listed by Codex')
            continue
        ranks.append(live[slug].get('priority', 10**6))
        efforts = {x['effort'] for x in live[slug].get('supported_reasoning_levels', [])}
        if efforts != set(entry['supported_efforts']):
            drift.append(f"{slug} efforts differ: catalog {sorted(entry['supported_efforts'])}, Codex {sorted(efforts)}")
    if ranks:
        for slug in sorted(visible - {entry['id'] for entry in catalogued}):
            if live[slug].get('priority', 10**6) < max(ranks):
                drift.append(f'Codex lists {slug} ranked above catalogued models; run /lean-catalog codex')
    agents = root / 'AGENTS.md'
    if agents.is_file():
        for slug in sorted(set(re.findall(r'`(gpt-[a-z0-9.\-]+)`', agents.read_text()))):
            if slug not in visible:
                drift.append(f'AGENTS.md names {slug}, which Codex does not list')
    return drift, notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='explicit record root; bypass active target selection')
    codex_home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    parser.add_argument('--codex-cache', type=Path, default=codex_home / 'models_cache.json')
    args = parser.parse_args(argv)
    try:
        if args.root is None:
            from submodule import context
            root = Path(context(Path(__file__).resolve().parents[2])['record_root'])
        else:
            root = args.root.resolve()
        drift, notes = check(root, args.codex_cache)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
        print(f'model drift check could not run: {error}', file=sys.stderr)
        return 2
    for line in notes:
        print('note: ' + line)
    for line in drift:
        print('DRIFT: ' + line)
    print(f'model catalog drift: {len(drift)} issue(s)' if drift else 'model catalog: no drift')
    return 1 if drift else 0


if __name__ == '__main__':
    sys.exit(main())
