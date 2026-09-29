# Project Context

This file describes repository-specific information for agents.

Update it as the project takes shape. "Not defined" is not an error: it means the repository has no convention here yet. Do not invent one; when work establishes a real convention, record it here.

## Purpose

Not defined yet.

## Architecture

Not defined yet.

## Commands

### Install
Not defined.

### Build
Not defined.

### Test
Not defined.

### Lint
Not defined.

### Typecheck
Not defined.

### Quality Gate

Commands run by the Claude `Stop` hook (`.claude/hooks/quality-gate.sh`) before a turn can finish. One command per line, fast checks first. Each must exit non-zero on failure (e.g. `test -z "$(gofmt -l .)"`, not `gofmt -l .`). Empty means the hook does nothing. Add commands once the project has them.

<!-- gate:start -->
```sh
```
<!-- gate:end -->

## Important paths

Not defined.

## High-risk areas

None defined yet.

## Documentation routes

None defined yet.
