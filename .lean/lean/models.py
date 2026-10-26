"""Project model list: tiers S/M/L/XL per provider, mapped to concrete model IDs and effort.

The list is project-owned evidence. Listing and checking never change runtime or session
settings; an unavailable model is reported, never silently substituted.
"""
import json
import os
from pathlib import Path
import subprocess
import time

from .util import LeanError, WORKFLOW_ROOT, read_json, safe_path

FILE = ".lean/models.json"
TIERS = ("S", "M", "L", "XL")
PROVIDERS = ("claude", "codex", "agy")
PLACEHOLDERS = ("{prompt}", "{model}")
CODEX_CACHE = Path("~/.codex/models_cache.json")
STALE_DAYS = 14


def path(root):
    local = safe_path(root, FILE)
    return local if local.is_file() else WORKFLOW_ROOT / FILE


def load(root):
    data = read_json(path(root))
    problems = validate(data)
    if problems:
        raise LeanError("invalid model list: " + "; ".join(problems))
    return data


def validate(data):
    problems = []
    if not isinstance(data, dict) or data.get("schema") != 1:
        return ["schema must be 1"]
    limit = data.get("max_agents")
    if type(limit) is not int or limit < 1:
        problems.append("max_agents must be a whole number of at least 1")
    providers = data.get("providers")
    if not isinstance(providers, dict) or not providers:
        return problems + ["providers must be a non-empty object"]
    if data.get("default_provider") not in providers:
        problems.append("default_provider must name a configured provider")
    for name, provider in providers.items():
        if name not in PROVIDERS:
            problems.append(f"unknown provider {name!r}; supported: {', '.join(PROVIDERS)}")
            continue
        if not isinstance(provider, dict) or not isinstance(provider.get("command"), str) or not provider["command"]:
            problems.append(f"{name}: command is required")
            continue
        args = provider.get("args")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            problems.append(f"{name}: args must be a list of strings")
        elif not all(any(mark in arg for arg in args) for mark in PLACEHOLDERS):
            problems.append(f"{name}: args must use {{prompt}} and {{model}}")
        tiers = provider.get("tiers")
        if not isinstance(tiers, dict) or set(tiers) != set(TIERS):
            problems.append(f"{name}: tiers must be exactly {', '.join(TIERS)}")
            continue
        for tier, value in tiers.items():
            if (not isinstance(value, dict) or not isinstance(value.get("model"), str) or not value["model"]
                    or not (value.get("effort") is None or isinstance(value.get("effort"), str))):
                problems.append(f"{name}.{tier}: needs a model string and an effort string or null")
    return problems


def detect_provider(data, environment=None):
    """The runtime this session runs in, else the configured default."""
    environment = os.environ if environment is None else environment
    if environment.get("CLAUDECODE") == "1":
        found = "claude"
    elif any(key.startswith("CODEX_") for key in environment):
        found = "codex"
    elif any(key.startswith("ANTIGRAVITY") for key in environment):
        found = "agy"
    else:
        found = data["default_provider"]
    return found if found in data["providers"] else data["default_provider"]


def resolve(data, provider, tier):
    if provider not in data["providers"]:
        raise LeanError(f"provider {provider!r} is not configured in {FILE}")
    if tier not in TIERS:
        raise LeanError(f"unknown size {tier!r}; use {', '.join(TIERS)}")
    value = data["providers"][provider]["tiers"][tier]
    return value["model"], value.get("effort")


def table(data):
    lines = [f"Model list ({FILE}, checked {data.get('checked', 'unknown')}); max_agents={data['max_agents']}, "
             f"default provider={data['default_provider']}"]
    for name, provider in data["providers"].items():
        lines.append(f"{name} ({provider['command']}):")
        for tier in TIERS:
            value = provider["tiers"][tier]
            lines.append(f"  {tier:<2} {value['model']}" + (f" / effort {value['effort']}" if value.get("effort") else ""))
    return "\n".join(lines)


def available(name, provider, timeout=30):
    """(set of available model ids or None, note). None means the runtime cannot list models here."""
    if name == "codex":
        cache = CODEX_CACHE.expanduser()
        try:
            data = json.loads(cache.read_text())
        except (OSError, ValueError):
            return None, f"Codex model cache not found at {cache}; run codex once to refresh it"
        models = {item.get("slug") for item in data.get("models", []) if isinstance(item, dict)}
        note = ""
        fetched = str(data.get("fetched_at", ""))[:10]
        try:
            age = (time.time() - time.mktime(time.strptime(fetched, "%Y-%m-%d"))) / 86400
            if age > STALE_DAYS:
                note = f"Codex model cache is {int(age)} days old"
        except ValueError:
            note = "Codex model cache has no fetch date"
        return models, note
    if name == "agy":
        try:
            result = subprocess.run([provider["command"], "models"], capture_output=True, text=True,
                                    timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as error:
            return None, f"agy models unavailable: {error}"
        if result.returncode:
            return None, f"agy models failed: {result.stderr.strip()[:200]}"
        return {line.split()[0] for line in result.stdout.splitlines() if line.strip() and "\t" in line}, ""
    return None, f"{name} CLI has no model listing; IDs stay unverified until a spawn uses them"


def check(root, live=False):
    """Return (ok, report lines). Without --live only the schema is checked (no subprocess)."""
    try:
        data = load(root)
    except (OSError, ValueError) as error:
        return False, [str(error)]
    lines, ok = [f"model list ok: {', '.join(data['providers'])}"], True
    if not live:
        return ok, lines
    for name, provider in data["providers"].items():
        models, note = available(name, provider)
        if note:
            lines.append(f"{name}: {note}")
        if models is None:
            continue
        for tier in TIERS:
            model = provider["tiers"][tier]["model"]
            if model not in models:
                ok = False
                lines.append(f"{name}.{tier}: {model} is not available; update {FILE} (not substituted)")
    return ok, lines
