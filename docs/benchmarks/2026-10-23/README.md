# Lean 4.7.0 versus current dirty — Casetodian local experiment

Baseline `6525301363f0fd6da90e75c118e3641dee2b0528`; current base `668fa81dac6d1c9dc2870bb24d6f353cfe21cbb0` plus the retained dirty snapshot. Casetodian `develop` is pinned to `592a15eba686ef2955cf5d3874c82df0baf8a2f4`. No model sessions or workers were launched for this benchmark.

All heavy runs were sequential. Full gates use the same application checkout and commands: `pnpm run lint`, `pnpm run test --maxWorkers=1`, `pnpm run build`. The isolated workflow fixtures use these application checks instead of Lean repository self-tests. They do not exercise submodule routing. Dependencies and an initial build were prepared before measurement.

Input-context counts below use `o200k_base`, summing the text of each listed file separately. They exclude message wrappers, runtime/system prompts and actual model usage. The JSON artifacts also include `cl100k_base` and exact file lists.

| Fixed context profile | 4.7.0 | Current dirty | Change |
|---|---:|---:|---:|
| Required startup text | 2,030 | 2,213 | +9.01% |
| Fixed workflow task read set | 10,186 | 11,146 | +9.42% |
| All skill documents (inventory only) | 26,664 | 26,784 | +0.45% |
| Worker: bounded instructions + source | 6,438 | 6,677 | +3.71% |
| Worker: full delegation skill + source | 7,192 | 7,997 | +11.19% |

The worker packet is a read-only investigation of the Gmail callback stale-configuration race, with four source files pinned to the same older Casetodian commit. See [worker-task.txt](worker-task.txt). `lean-multi-agent` maps to `lean-agents`. These are partial fixed input profiles: application PROJECT text, workflow CLI output, dynamically discovered dependencies and inherited controller history are excluded. They do not establish worker completion, actual usage or savings from fresh-context delegation.

The optional deployment skill/templates add 2,185 tokens when explicitly read in current dirty. They are absent in 4.7.0; absence is not a zero-cost deployment implementation.

| Full uncached application gate: one run per version | Wall time | Lint | Tests | Build | Residual outside timed commands |
|---|---:|---:|---:|---:|---:|
| v4.7.0 | 1215.147s | 104.712s | 1011.428s | 98.260s | 0.747s |
| current-dirty | 914.858s | 15.034s | 796.858s | 102.550s | 0.416s |

Both full gates passed. Baseline: 10,265 passed / 53 skipped; current: 10,266 passed / 52 skipped, out of 10,318 tests in 661 files. Five opt-in files were skipped in both runs. A runtime `ctx.skip()` based on project ordering is consistent with the one-test difference; default reporter output does not prove the individual skipped-test identity. Existing live AI/S3/container opt-ins were not enabled. No tests or guards were weakened.

These full-gate observations are not a controlled causal speedup estimate: there is one run per arm, fixed version order, shared-host activity, warm-up/cache effects and a one-test outcome difference. Most wall time is inside application checks. The residual includes process/logging overhead, not a precise engine-only CPU profile.

| Synthetic runner test (0.5s check latency) | 4.7.0 median | Current median | Verified behavior |
|---|---:|---:|---|
| Uncached, 3 runs | 0.7669s | 0.7390s | Check runs in both arms |
| Direct --cache-tree repeat, 3 runs | 0.7349s | 0.3366s | Old: check runs each time; current: zero check invocations |

A changed tracked input reran the check in both versions. This demonstrates direct-runner cache behavior on a Git-visible synthetic fixture, not a Casetodian speedup. In both source versions, selected target checks run before the Lean cache, so the synthetic cache benefit cannot be applied to the complete target gate.

Local deployment/rollback exercised the same mechanical plan twice, sequentially under the version labels. 4.7.0 has no lean-playbook, so its run is an externally supplied manual-plan baseline; this is not an autonomous agent deployment comparison. Images use the application production Dockerfiles, with a small web release-marker layer for verification. A is Casetodian 0.56.2 (`7f76ac426784c3665e891a192cfd00d88af1af98`), B is 0.57.0 (`592a15eba686ef2955cf5d3874c82df0baf8a2f4`). Their schema, migrations and lockfile are identical; compiled backend hashes differ.

For each label: A deploy, B deploy, rollback A, reject B with an intentionally bad database endpoint (503), recover A. All eight healthy transitions passed; both injected failures were rejected as expected. Checks cover API/MCP/worker readiness and image identity, localhost web health/HTML, served JavaScript hash, direct and proxied anonymous API rejection (401), and unchanged synthetic database sentinel.

Backend/DB use an internal Docker network. Only web uses a separate ingress bridge with a loopback binding. This is application artifact rollback with downtime; it does not test authenticated user journeys, Keycloak deployment, schema rollback, data restoration, zero-downtime rollout or autonomous playbook compliance.

Preflight failures are retained separately: invalid pnpm argument routing, a database name rejected by the existing test guard, Docker internal-only port publication, and a missing synthetic Keycloak audience. These are excluded from successful timing/transition results. Images were reused after infrastructure/configuration fixes; application code and assertions were not changed.

Evidence: [context counts](context-tokens.json), [worker counts](worker-context-tokens.json), [full gate times](gate-timings.json), [cache runs](gate-overhead-cache.json), [validation excerpts](validation-excerpts.txt), [deployment plan](local-deployment-plan.md), [deployment attempts](deployment-results.json), [artifact identities](deployment-artifacts.json), [run metadata](deployment-run-metadata.json), [source preservation](source-preservation.json), [cleanup record](cleanup.json). Snapshot archives and per-file inventories retain both workflow inputs. Cleanup records are created only after successful experiment checks and resource removal; final Lean repository gate and review are reported in the session.

Retained Python executors are provenance artifacts. They were run from `.agent-runtime/benchmark-20261023/`; their paths assume that location and the matching experimental checkout. Do not run them directly from this documentation folder. Shared pnpm/Docker build caches are preserved. No commit or push is part of this task.
