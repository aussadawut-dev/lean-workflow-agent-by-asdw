# Changelog

Versions follow `MAJOR.MINOR.PATCH`: MAJOR changes existing workflow rules or required paths, MINOR adds rules, files or enforcement, and PATCH clarifies wording.

Older entries describe the workflow at the time. For current installation and upgrade instructions, see [CUSTOMIZING.md](CUSTOMIZING.md).

Token highlights come from the [historical smoke-test notes](https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw/blob/v4.8.0/.lean/CHANGELOG.md#450--2026-10-18) and [TCK303 replay notes](https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw/blob/v4.8.0/.lean/CHANGELOG.md#480--2026-10-19). Approximate percentages are calculated from the reported totals, not new benchmarks. Compare results within the same workload; they are not guaranteed savings. The original smoke-test runs were not retained. `-` means no version comparison was recorded.

## 5.2.0 — 2026-10-27

**Token highlight:** - · **Compared with:** -

Refresh the model list from evidence. No token or speed saving is claimed for the workflow itself.

**Added**

- `/lean-model-update`: research the models each provider offers, agree an eval plan and a token cap with the user, run the eval, have an independent reviewer check the results, and write `.lean/models.json` only for the proposal the user approved. It never edits provider permission settings; for agy it gives the user the allow rules to add.
- `lean models eval --plan FILE --budget TOKENS [--estimate N] [--out DIR]`: runs each candidate (provider, model, effort) on the task bank in throwaway Git copies outside the repository, with the `models.json` command shapes, eval-only flags (Claude may run `python3 -m unittest`) and metered API keys removed, and scores hidden tests per subtest. Each run reserves the larger of the largest token count seen and `--estimate` (default 250000), starts only while spent plus reservations fit the budget and otherwise waits for running ones, so only a run that uses more than its reservation can go over; a CLI that never started costs nothing and is retried, an unknown count costs exactly its run's reservation, and a run that fails in any step is recorded and releases its reservation. Tokens follow one rule for every provider (input + cache writes + output, cache reads apart; Codex reports one total); an unknown count is charged like a reservation. Writes `results.jsonl` (a rerun resumes), `summary.md`, `proposal.json` (per provider and size, the fastest candidate with a full score) and raw `logs/`. Permission denials are reported as notes.
- `lean models apply --proposal FILE --sha256 DIGEST`: writes only the proposed sizes, refuses a proposal that changed since its digest was shown, and validates the list.
- `lean models bank` and the task bank in `.lean/evals/` (workflow-owned, shipped with every installation): one task per size, from a one-line bug fix (3S) to a single-flight thread-safe cache (3XL), each with a reference solution that scores full marks and a stub that does not.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`; `.lean/evals/` arrives with the release. The changed gate controls (`.lean/lean/evals.py`, `models.py`, `cli.py`, `structure.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

ปรับรายชื่อ model จากหลักฐานจริง ไม่ได้อ้างว่า workflow ประหยัด token หรือเร็วขึ้น

**เพิ่ม**

- `/lean-model-update`: ค้นว่าแต่ละ provider มี model อะไร ตกลงแผน eval และเพดาน token กับผู้ใช้ รัน eval ให้ reviewer อิสระตรวจผล แล้วเขียน `.lean/models.json` เฉพาะข้อเสนอที่ผู้ใช้อนุมัติ skill นี้ไม่แก้ settings สิทธิ์ของ provider เอง สำหรับ agy จะให้คำสั่ง allow rule ให้ผู้ใช้เพิ่มเอง
- `lean models eval --plan FILE --budget TOKENS [--estimate N] [--out DIR]`: รัน candidate แต่ละตัว (provider, model, effort) กับชุดงานในสำเนา Git ที่ทิ้งได้นอก repository ด้วย command แบบเดียวกับ `models.json` บวก flag เฉพาะ eval (Claude รัน `python3 -m unittest` ได้) และลบ API key ที่คิดเงินออก ให้คะแนนด้วย hidden test ราย subtest แต่ละ run จองค่าที่มากกว่าระหว่างจำนวน token สูงสุดที่เคยเห็นกับ `--estimate` (ค่าเริ่มต้น 250000) เริ่มได้เฉพาะเมื่อยอดที่ใช้บวกยอดจองยังไม่เกินงบ ไม่อย่างนั้นจะรอ run ที่กำลังทำงานอยู่ จึงเกินงบได้เฉพาะ run ที่ใช้มากกว่ายอดจอง ส่วน CLI ที่เริ่มไม่ได้จะไม่ถูกคิด token และรันใหม่ได้ จำนวนที่ไม่รู้คิดเท่ายอดจองของ run นั้นพอดี และ run ที่ error ไม่ว่าขั้นไหนจะถูกบันทึกและคืนยอดจอง นับ token แบบเดียวกันทุก provider (input + cache write + output แยก cache read; Codex รายงานยอดเดียว) ถ้าไม่รู้จำนวนจะคิดเหมือนยอดจอง เขียน `results.jsonl` (รันซ้ำแล้วทำต่อจากเดิม), `summary.md`, `proposal.json` (เลือก candidate ที่เร็วที่สุดที่ได้คะแนนเต็มต่อ provider และ size) และ `logs/` ดิบ การถูกปฏิเสธสิทธิ์รายงานเป็นหมายเหตุ
- `lean models apply --proposal FILE --sha256 DIGEST`: เขียนเฉพาะ size ที่เสนอ ปฏิเสธข้อเสนอที่เปลี่ยนไปหลังแสดง digest และตรวจความถูกต้องของ list
- `lean models bank` และชุดงานใน `.lean/evals/` (workflow เป็นเจ้าของ ส่งไปกับทุกการติดตั้ง): size ละหนึ่งงาน ตั้งแต่แก้บั๊กบรรทัดเดียว (3S) ถึง cache แบบ single-flight ที่ปลอดภัยต่อ thread (3XL) แต่ละงานมีเฉลยที่ได้คะแนนเต็มและ stub ที่ไม่ได้เต็ม

**เมื่ออัปเกรด:** `python3 .lean/bin/lean update preview` ตรวจแผนแล้ว `update apply` โดย `.lean/evals/` มากับ release gate controls ที่เปลี่ยน (`.lean/lean/evals.py`, `models.py`, `cli.py`, `structure.py`) ต้องมี HIGH review ที่ครอบคลุม หรือ `lean gate accept-controls` ไม่ต้องย้าย configuration หรือข้อมูล

</details>

## 5.1.0 — 2026-10-27

**Token highlight:** - · **Compared with:** -

Eight spawn sizes instead of four. No token or speed saving is claimed for the workflow itself; the size mapping follows the [2026-10-27 model eval](../docs/benchmarks/2026-10-27-models/README.md).

**Added**

- Sizes `3S`, `2S`, `S`, `M`, `L`, `XL`, `2XL`, `3XL`, smallest first: two cheaper sizes for locating and small mechanical work, two stronger ones for work `XL` could not do. `lean models`, `lean models check [--live]` and `lean spawn plan` know all eight.
- The shipped `.lean/models.json` (checked 2026-10-27) maps them per provider. Claude: Haiku low/medium, Sonnet low/medium, Opus high/xhigh, Fable high/max. Codex: `gpt-6-luna` low, `gpt-6.1-terra` low/medium, `gpt-6.1-sol` medium/high, `gpt-6-astra` high/xhigh/max. agy: Gemini 3.8 Flash low/medium/high, Gemini 4 Argon low/medium/high (high for `XL` to `3XL`). Codex `ultra` effort is not used.

**Changed**

- Changed mappings in the shipped list (old → new): Claude `S` Haiku low → Sonnet low, `XL` Fable high → Opus xhigh (Fable is now `2XL`/`3XL`); Codex `S` `gpt-6-luna` low → `gpt-6.1-terra` medium (Luna is now `3S`); agy `S` Flash low → Flash high, `M` Flash high → Argon low. Every other `S`/`M`/`L`/`XL` mapping is unchanged. The old `S` is closest to the new `3S`; the old Claude `XL` is the new `2XL`.

**Upgrade:** `S`, `M`, `L` and `XL` stay required and the new sizes are optional, so a project's 5.0 `models.json` keeps working; a task sized with a size the project does not define is refused with a message (an explicit `--model` still runs). To use the new sizes, copy the `tiers` you want from the release's `.lean/models.json` and run `lean models check --live`. The changed gate controls (`.lean/lean/models.py`, `spawn.py`) need a covering HIGH review or `lean gate accept-controls`.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

ขนาดของ agent ที่ spawn เพิ่มจากสี่เป็นแปด ไม่ได้อ้างว่า workflow ประหยัด token หรือเร็วขึ้น การจับคู่ขนาดกับ model อ้างอิง[ผลประเมิน model วันที่ 2026-10-27](../docs/benchmarks/2026-10-27-models/README.md)

**เพิ่ม**

- ขนาด `3S`, `2S`, `S`, `M`, `L`, `XL`, `2XL`, `3XL` เรียงจากเล็กไปใหญ่ เพิ่มสองขนาดที่ถูกกว่าสำหรับงานหาตำแหน่งและงานกลไกเล็กๆ และสองขนาดที่แรงกว่าสำหรับงานที่ `XL` ทำไม่ได้ `lean models`, `lean models check [--live]` และ `lean spawn plan` รู้จักครบทั้งแปด
- `.lean/models.json` ที่มากับ release (ตรวจ 2026-10-27) จับคู่ขนาดกับ model ของแต่ละ provider: Claude ใช้ Haiku low/medium, Sonnet low/medium, Opus high/xhigh, Fable high/max; Codex ใช้ `gpt-6-luna` low, `gpt-6.1-terra` low/medium, `gpt-6.1-sol` medium/high, `gpt-6-astra` high/xhigh/max; agy ใช้ Gemini 3.8 Flash low/medium/high และ Gemini 4 Argon low/medium/high (high สำหรับ `XL` ถึง `3XL`) ไม่ใช้ effort `ultra` ของ Codex

**เปลี่ยน**

- การจับคู่ที่เปลี่ยนใน list ที่มากับ release (เดิม → ใหม่): Claude `S` Haiku low → Sonnet low, `XL` Fable high → Opus xhigh (Fable ย้ายไป `2XL`/`3XL`); Codex `S` `gpt-6-luna` low → `gpt-6.1-terra` medium (Luna ย้ายไป `3S`); agy `S` Flash low → Flash high, `M` Flash high → Argon low ส่วน `S`/`M`/`L`/`XL` ที่เหลือไม่เปลี่ยน `S` แบบเดิมใกล้กับ `3S` ใหม่ และ Claude `XL` แบบเดิมคือ `2XL` ใหม่

**เมื่ออัปเกรด:** `S`, `M`, `L` และ `XL` ยังต้องมีทุก provider ส่วนขนาดใหม่ไม่บังคับ `models.json` ของโปรเจกต์ที่เขียนสำหรับ 5.0 จึงใช้ได้ต่อ งานที่ระบุขนาดที่โปรเจกต์ไม่ได้กำหนดจะถูกปฏิเสธพร้อมข้อความ (ถ้าระบุ `--model` เองยังรันได้) ถ้าจะใช้ขนาดใหม่ ให้ก๊อป `tiers` ที่ต้องการจาก `.lean/models.json` ของ release แล้วรัน `lean models check --live` gate controls ที่เปลี่ยน (`.lean/lean/models.py`, `spawn.py`) ต้องมี HIGH review ที่ครอบคลุม หรือ `lean gate accept-controls`

</details>

## 5.0.2 — 2026-10-27

**Token highlight:** - · **Compared with:** -

Follow-ups from the 5.0.1 release work. No token or speed saving is claimed.

**Fixed**

- In Claude, `lean contract declare` exits 2 with "NOT bound" when no session holds the contract it was given, as when the contract comes through a shell variable or after another command and the guard's hook does not bind it. It used to print the contract as if bound while the session kept its earlier one. Other runtimes (Codex without trust, agy) still only validate, and `lean spawn run` no longer passes Claude's `CLAUDECODE` marker to its workers.
- `lean lint` reports a routed document that is not UTF-8 text instead of stopping with a Python error.
- `lean update preview` reads a symlinked routed document the way lint does when the link resolves inside the project, and never one that points outside it; it notes a routed document that is not UTF-8 text, which lint reports.
- A busy-gate Stop is counted per session, so another session's fresh Stop no longer restarts this session's count; counters older than a day are removed.
- REVIEW.md: request the HIGH review before committing changed gate controls; a receipt cannot accept a control change committed before the review began.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`. The changed gate controls (`.lean/lean/gate.py`, `guard.py`, `cli.py`, `spawn.py`, `structure.py`, `update.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

งานต่อเนื่องจากการออก 5.0.1 ไม่ได้อ้างว่าประหยัด token หรือเร็วขึ้น

**แก้ไข**

- ใน Claude คำสั่ง `lean contract declare` จบด้วย exit 2 และข้อความ "NOT bound" เมื่อไม่มี session ใดถือ contract ที่ส่งมา เช่น ส่งผ่าน shell variable หรือมีคำสั่งอื่นนำหน้า ซึ่ง hook ของ guard ไม่ผูกให้ ก่อนหน้านี้คำสั่งพิมพ์ contract เหมือนผูกแล้ว ทั้งที่ session ยังใช้ contract เดิม runtime อื่น (Codex ที่ยังไม่ trust, agy) ยังตรวจรูปแบบอย่างเดียวเหมือนเดิม และ `lean spawn run` ไม่ส่งตัวแปร `CLAUDECODE` ของ Claude ต่อให้ worker อีก
- `lean lint` รายงานเอกสาร routed ที่ไม่ใช่ข้อความ UTF-8 แทนการหยุดด้วย Python error
- `lean update preview` อ่านเอกสาร routed ที่เป็น symlink แบบเดียวกับ lint เมื่อ link ชี้อยู่ในโปรเจกต์ และไม่อ่าน link ที่ชี้ออกนอกโปรเจกต์ และแจ้งเอกสาร routed ที่ไม่ใช่ข้อความ UTF-8 ซึ่ง lint จะรายงาน
- Stop ที่เจอ gate busy นับแยกตาม session แล้ว Stop ใหม่ของ session อื่นจึงไม่ทำให้ตัวนับของ session นี้เริ่มใหม่ และลบตัวนับที่เก่ากว่าหนึ่งวัน
- REVIEW.md: ให้ขอ HIGH review ก่อน commit การเปลี่ยน gate controls เพราะ receipt ยอมรับการเปลี่ยน controls ที่ commit ไปก่อนเริ่ม review ไม่ได้

**เมื่ออัปเกรด:** `python3 .lean/bin/lean update preview` ตรวจแผนแล้ว `update apply` gate controls ที่เปลี่ยน (`.lean/lean/gate.py`, `guard.py`, `cli.py`, `spawn.py`, `structure.py`, `update.py`) ต้องมี HIGH review ที่ครอบคลุม หรือ `lean gate accept-controls` ไม่ต้องย้าย configuration หรือข้อมูล

</details>

## 5.0.1 — 2026-10-27

**Token highlight:** - · **Compared with:** -

Fixes found upgrading a real 4.16 project to 5.0.0, and the Low findings from the 5.0.0 reviews. No token or speed saving is claimed.

**Fixed**

- Lean's own tests pass in an installation whose PROJECT.md names its own `.lean/` files (such as `.lean/LOCAL-EXTENSIONS.md`): the release copy the tests build now brings the project files those documents name. A routing test no longer assumes PROJECT.md ends inside its Documentation routes section. Before, `unit/test_structure.py` failed 4 tests there.
- `lean update preview` names what `lean lint` would reject after the update: a project's own file inside a workflow-owned folder (kept, never deleted) and 4.x paths in the documents PROJECT.md routes to (such as README.md).
- A Codex Stop with a symlinked `.agent-runtime` blocks a fresh Stop and releases continued Stops UNVERIFIED instead of blocking them without end.
- `lean test` takes a tier name (`lean test e2e`) and repository paths (`.lean/tests/hooks/test_gate.py`) as well as `hooks/test_gate.py`, and names an unknown file instead of a Python error.
- A review-pending marker releases control drift only when the contract it was matched with is the session's HIGH-depth contract; a Stop run by hand with another `--contract` still blocks.

**Upgrade:** `python3 .lean/bin/lean update preview`, review the plan, then `update apply`. The changed gate controls (`.lean/lean/gate.py`, `hooks.py`) need a covering HIGH review or `lean gate accept-controls`. No configuration or data migration.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

แก้ปัญหาที่เจอตอนอัปเกรดโปรเจกต์จริงจาก 4.16 เป็น 5.0.0 และ Low findings จาก review ของ 5.0.0 ไม่ได้อ้างว่าประหยัด token หรือเร็วขึ้น

**แก้ไข**

- test ของ Lean ผ่านในโปรเจกต์ที่ PROJECT.md อ้างไฟล์ `.lean/` ของตัวเอง (เช่น `.lean/LOCAL-EXTENSIONS.md`) เพราะชุดไฟล์ที่ test สร้างจะก๊อปไฟล์ของโปรเจกต์ที่เอกสารอ้างถึงมาด้วย และ test เรื่อง routing ไม่สันนิษฐานว่า PROJECT.md จบในหัวข้อ Documentation routes อีก ก่อนหน้านี้ `unit/test_structure.py` fail 4 test
- `lean update preview` บอกสิ่งที่ `lean lint` จะปฏิเสธหลังอัปเกรด: ไฟล์ของโปรเจกต์ในโฟลเดอร์ที่ workflow เป็นเจ้าของ (เก็บไว้ ไม่ลบ) และ path ของ 4.x ในเอกสารที่ PROJECT.md ชี้ไป (เช่น README.md)
- Stop ของ Codex ที่ `.agent-runtime` เป็น symlink จะ block ครั้งแรก แล้วปล่อย Stop ต่อเนื่องแบบ UNVERIFIED แทนการ block ไม่สิ้นสุด
- `lean test` รับชื่อ tier (`lean test e2e`) และ path จาก root ของ repo (`.lean/tests/hooks/test_gate.py`) นอกจาก `hooks/test_gate.py` และบอกชื่อไฟล์ที่ไม่มีแทน Python error
- marker ของ review-pending จะปล่อย control drift เฉพาะเมื่อ contract ที่ใช้จับคู่คือ contract ระดับ HIGH ของ session เอง Stop ที่รันเองด้วย `--contract` อื่นยังถูก block

**เมื่ออัปเกรด:** `python3 .lean/bin/lean update preview` ตรวจแผนแล้ว `update apply` gate controls ที่เปลี่ยน (`.lean/lean/gate.py`, `hooks.py`) ต้องมี HIGH review ที่ครอบคลุม หรือ `lean gate accept-controls` ไม่ต้องย้าย configuration หรือข้อมูล

</details>

## 5.0.0 — 2026-10-27

**Token highlight:** fixed-task inventory 11,146 → 9,962 (-10.6%), startup 2,213 → 2,209 (-0.2%), o200k_base ([measurement](../docs/benchmarks/2026-10-27/README.md)) · **Compared with:** 4.17.1

Rebuild the workflow around one `lean` command line. Every rule, hook and check from 4.17.0 that the core keeps carries over with its tests; the layout, commands and spawning defaults change, so this is a major release.

- **One command.** `python3 .lean/bin/lean` replaces every script in `.lean/scripts/`, the Claude hook scripts and the Codex adapter. Code lives in `.lean/lean/`, one module per command group (`guard`, `gate`, `evidence`, `hooks`, `records`, `progress`, `models`, `spawn`, `testsel`, `structure`, `update`). Provider hooks call `lean hook claude|codex <event>`. The bash gate runner is now Python; ShellCheck is no longer needed.
- **Progress bars.** `lean progress set <phase>` drives a solid/shade bar (`████████░░░░░░░░░░░░ 40%`) by lean-task phase, refined by counts inside a phase. One state file feeds the agent's replies, `lean status`, `lean watch`, `lean test`, `lean gate run`, `lean spawn run` (one bar per agent), the Claude status line and Codex's Stop message. Codex and agy have no custom in-window status line; they use `lean watch` in a second pane.
- **Tests by impact.** Tests sit in `.lean/tests/unit`, `hooks` and `e2e`; `.lean/tests/impact.json` maps paths to them. `lean test --changed` runs only what the change can affect, documentation-only changes run lint only, and an unmapped path runs everything. The gate runs the selection; CI runs `lean test --all` on every push and pull request.
- **Model list and spawning.** `.lean/models.json` maps sizes S/M/L/XL to models for Claude, Codex and agy; `lean models check --live` verifies them against the provider CLIs. By default at most `max_agents` (1) sized agent runs at a time, only when cheaper than finishing in the session. `/lean-agents` spawns one agent per parallel task; `/lean-agents <model> xN` runs up to N at once on that model. `lean spawn plan` computes waves with exclusive file ownership; `lean spawn run` starts headless `claude -p`, `codex exec` or `agy -p` processes in separate worktrees, removing metered API keys so they use the subscription login.
- **Activity log.** Phase changes, gate runs, test runs, spawned agents, contract bindings and review receipts are timed in `.agent-runtime/activity.jsonl`; `lean log` shows the timeline or a per-phase summary and `--export` keeps a copy in the repository.
- **agy support.** Antigravity CLI is a third provider for spawning, review and the gate (run explicitly; agy has no hooks).
- **Smaller core.** Eleven skills remain: init, task, scope, research, grill, agents, review, gate, effort, update and target. The optional skills audit, catalog, compress, pattern, playbook, prune and takeover are removed with their tools, along with the optional skill pack and queue cleanup (`clean-queue`). Archived queue history stays readable. Application targets (`lean target use|context|clear|gate`, records in `.lean/targets/<name>/`) carry over unchanged in behavior. The shared "skill level" text moved into `policy/SKILL-EFFORT.md`.
- **Update with migration.** `lean update preview|apply|rollback` replaces the takeover-based updater: an external pinned clone, a reviewed plan, snapshots, a journal and rollback, with 4.x migration of hooks, gate block, gate mode and skill links.
- **Quiet Stops while a review runs.** `lean gate review-pending --contract ... --session ...` marks an independent review as running; that session's Stops whose only refusal is the missing receipt for the same contract and shipping state are released UNVERIFIED (never passed) for up to two hours, instead of being refused again. Under a HIGH-depth contract, changed gate controls waiting for that review are released the same way, with checks NOT_RUN. Any change, another contract, a recorded receipt or any other refusal ends it. Only the command writes the marker.
- **Trusted spawn runs.** `lean spawn run --trust-agents` adds each provider's `trusted_args` from `models.json` (agy `--dangerously-skip-permissions`, Claude `--permission-mode bypassPermissions`), so headless agents can run their task's commands; it warns and is never the default.
- **Faster hooks and commands.** Measured against 4.17.1 on one machine with a trivial gate: a Stop takes 125 ms instead of 730 ms and starts 6 `git` processes instead of 11, SessionStart 128 ms instead of 627 ms, and plain commands are within 6 ms of 4.17.1's scripts (53–55 ms). The CLI keeps compiled bytecode in a private per-user cache (`~/.cache/lean-workflow/pycache`, or under `$XDG_CACHE_HOME`; used only when the path is absolute and every directory from the cache base down is the user's own and not writable by others, never in the checkout; delete it to clear it), the status line reads the gate's markers without loading the gate, and AGENTS.md is shorter with every rule kept. Data: [docs/benchmarks/2026-10-27](../docs/benchmarks/2026-10-27/README.md).
- `lean test` names failing test files in its summary line.
- A Claude Stop that finds the gate lock held by another run is blocked at most three times, then released UNVERIFIED, as in 4.17.1; it records no pass. The lock is an `flock` the kernel drops with its holder, so v5 needs no guardian process or `ps`. Checks inherit it, so unlike 4.17.1 a process a check leaves running in the background keeps the checkout locked until that process exits. A busy counter or refusal marker that cannot be written no longer blocks continued Stops without end.
- Gate mode moves from `.codex/quality-gate.json` to `.lean/gate.json` (`lean gate mode`). Gate runtime markers move from `.claude/.gate-cache`/`.gate-failed` to `.agent-runtime/`.

**Upgrade:** this release changes paths and commands; follow [migrating to v5](../docs/migrating-to-v5.md). A 4.x installation has no `lean` command, so run the preview from the pinned 5.0.0 release: `python3 <release>/.lean/bin/lean update preview --target <project>`, review the plan, then `update apply`. Approve the changed gate controls through a covering HIGH review or `lean gate accept-controls`. Project records, PROJECT facts, config and trackers are kept.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** ชุดไฟล์ fixed-task 11,146 → 9,962 (-10.6%), startup 2,213 → 2,209 (-0.2%), o200k_base ([ผลวัด](../docs/benchmarks/2026-10-27/README.md)) · **เทียบกับรุ่น:** 4.17.1

สร้าง workflow ใหม่รอบคำสั่งเดียว `lean` กฎ hook และการตรวจของ 4.17.0 ที่แกนหลักเก็บไว้ยกมาพร้อม test ทั้งหมด แต่โครงสร้างไฟล์ คำสั่ง และค่าเริ่มต้นของการ spawn เปลี่ยน จึงเป็น major release

- **คำสั่งเดียว** `python3 .lean/bin/lean` แทนทุก script ใน `.lean/scripts/`, hook script ของ Claude และ adapter ของ Codex โค้ดอยู่ใน `.lean/lean/` แยก module ตามกลุ่มคำสั่ง hook ของ provider เรียก `lean hook claude|codex <event>` gate runner เปลี่ยนจาก bash เป็น Python จึงไม่ต้องใช้ ShellCheck แล้ว
- **Progress bar** `lean progress set <phase>` แสดงแถบทึบ/จาง (`████████░░░░░░░░░░░░ 40%`) ตาม phase ของ lean-task และละเอียดขึ้นด้วยจำนวนงานใน phase ไฟล์ state เดียวแสดงได้ทุกที่: คำตอบของ agent, `lean status`, `lean watch`, `lean test`, `lean gate run`, `lean spawn run` (แถบละหนึ่ง agent), status line ของ Claude และข้อความ Stop ของ Codex ส่วน Codex และ agy ไม่มี status line ที่กำหนดเองได้ ให้ใช้ `lean watch` ในอีก pane
- **Test ตามผลกระทบ** test แบ่งเป็น `unit`, `hooks`, `e2e` และ `.lean/tests/impact.json` จับคู่ path กับ test `lean test --changed` รันเฉพาะที่งานกระทบ แก้แต่เอกสารรันแค่ lint ส่วน path ที่ไม่มีกฎรองรับจะรันทั้งหมด gate ใช้การเลือกนี้ ส่วน CI รัน `lean test --all` ทุก push และ pull request
- **Model list และการ spawn** `.lean/models.json` กำหนดขนาด S/M/L/XL เป็น model ของ Claude, Codex และ agy และ `lean models check --live` ตรวจกับ CLI ของ provider ค่าเริ่มต้น spawn ได้ไม่เกิน `max_agents` (1) ตัวต่อครั้งตามขนาดงาน และเฉพาะเมื่อคุ้มกว่าทำใน session `/lean-agents` แตกหนึ่ง agent ต่องานที่ขนานได้ และ `/lean-agents <model> xN` รันพร้อมกันได้สูงสุด N ตัวด้วย model นั้น `lean spawn plan` คำนวณ wave โดยไม่ให้ไฟล์ชนกัน และ `lean spawn run` เปิด `claude -p`, `codex exec` หรือ `agy -p` ใน worktree แยก โดยตัด API key แบบคิดเงินออกเพื่อใช้ login ของ subscription
- **Activity log** บันทึกเวลาของการเปลี่ยน phase, การรัน gate และ test, agent ที่ spawn, การผูก contract และ review receipt ลง `.agent-runtime/activity.jsonl` ดูได้ด้วย `lean log` (timeline) หรือ `lean log --summary` (เวลาต่อ phase) และ `--export` เก็บสำเนาลง repo
- **รองรับ agy** Antigravity CLI เป็น provider ที่สามสำหรับ spawn, review และ gate (รัน gate เองเพราะ agy ไม่มี hook)
- **แกนเล็กลง** เหลือ 11 skill: init, task, scope, research, grill, agents, review, gate, effort, update และ target ตัด skill เสริม audit, catalog, compress, pattern, playbook, prune, takeover พร้อมเครื่องมือ, optional skill pack และการล้าง queue (`clean-queue`) ประวัติ queue ที่ archive ไว้ยังอ่านได้ ส่วน application target (`lean target use|context|clear|gate` และ records ใน `.lean/targets/<name>/`) ยังทำงานเหมือนเดิม ข้อความ "skill level" ที่ซ้ำกันย้ายไปไว้ใน `policy/SKILL-EFFORT.md`
- **อัปเดตพร้อม migration** `lean update preview|apply|rollback` แทน updater ที่อิง takeover: clone แบบ pin ไว้นอก repo, แผนที่ review ได้, snapshot, journal และ rollback พร้อมย้าย hook, gate block, gate mode และ skill link ของ 4.x
- **Stop เงียบระหว่างรอ review** `lean gate review-pending --contract ... --session ...` บันทึกว่า independent review กำลังทำงาน Stop ของ session นั้นที่ถูกปฏิเสธเพียงเพราะยังไม่มี receipt ของ contract และ shipping state เดียวกัน จะถูกปล่อยแบบ UNVERIFIED (ไม่นับเป็นผ่าน) ได้นานสุดสองชั่วโมงแทนการปฏิเสธซ้ำ ภายใต้ contract ระดับ HIGH การเปลี่ยน gate controls ที่รอ review นั้นอยู่จะถูกปล่อยแบบเดียวกัน (checks NOT_RUN) การเปลี่ยนแปลงใดๆ, contract อื่น, receipt ที่บันทึกแล้ว หรือเหตุปฏิเสธอื่นจะยุติทันที และมีเพียงคำสั่งนี้ที่เขียน marker ได้
- **Spawn แบบ trusted** `lean spawn run --trust-agents` เติม `trusted_args` ของแต่ละ provider จาก `models.json` (agy `--dangerously-skip-permissions`, Claude `--permission-mode bypassPermissions`) เพื่อให้ agent แบบ headless รันคำสั่งของงานได้ มีคำเตือนและไม่ใช่ค่าเริ่มต้น
- **Hook และคำสั่งเร็วขึ้น** วัดเทียบกับ 4.17.1 บนเครื่องเดียวด้วย gate ว่าง: Stop ใช้ 125 ms แทน 730 ms และเรียก `git` 6 ครั้งแทน 11, SessionStart 128 ms แทน 627 ms และคำสั่งทั่วไปช้ากว่า script ของ 4.17.1 ไม่เกิน 6 ms (53–55 ms) CLI เก็บ bytecode ไว้ใน cache ส่วนตัวของผู้ใช้ (`~/.cache/lean-workflow/pycache` หรือใต้ `$XDG_CACHE_HOME` ใช้เฉพาะเมื่อ path เป็น absolute และทุก directory ตั้งแต่ฐานของ cache ลงไปเป็นของผู้ใช้และคนอื่นเขียนไม่ได้ ไม่เขียนลง checkout ลบทิ้งได้เพื่อล้าง cache) status line อ่าน marker ของ gate โดยไม่โหลด gate และ AGENTS.md สั้นลงโดยยังมีครบทุก rule ข้อมูล: [docs/benchmarks/2026-10-27](../docs/benchmarks/2026-10-27/README.md)
- `lean test` บอกชื่อไฟล์ test ที่ fail ในบรรทัดสรุป
- Stop ของ Claude ที่เจอ gate lock ถูก run อื่นถืออยู่ จะถูก block ไม่เกินสามครั้งแล้วปล่อยแบบ UNVERIFIED เหมือน 4.17.1 โดยไม่บันทึกว่าผ่าน lock เป็น `flock` ที่ kernel ปล่อยพร้อม process ที่ถือ จึงไม่ต้องมี guardian หรือ `ps` แต่ check ได้รับ lock ต่อไปด้วย ต่างจาก 4.17.1 process ที่ check ทิ้งไว้ทำงานเบื้องหลังจะถือ lock ไว้จนกว่า process นั้นจบ และ busy counter หรือ refusal marker ที่เขียนไม่ได้จะไม่ทำให้ Stop ต่อเนื่องถูก block ไม่สิ้นสุดอีก
- gate mode ย้ายจาก `.codex/quality-gate.json` ไป `.lean/gate.json` (`lean gate mode`) และ marker ของ gate ย้ายจาก `.claude/.gate-cache`/`.gate-failed` ไป `.agent-runtime/`

**เมื่ออัปเกรด:** รุ่นนี้เปลี่ยน path และคำสั่ง ให้ทำตาม [migrating to v5](../docs/migrating-to-v5.md) การติดตั้ง 4.x ยังไม่มีคำสั่ง `lean` จึงต้องรัน preview จาก release 5.0.0 ที่ pin ไว้: `python3 <release>/.lean/bin/lean update preview --target <project>` ตรวจแผนแล้วค่อย `update apply` อนุมัติ gate controls ที่เปลี่ยนผ่าน HIGH review ที่ครอบคลุม หรือ `lean gate accept-controls` โดย records, ข้อมูลใน PROJECT, config และ tracker ของโปรเจกต์ยังอยู่ครบ

</details>

## 4.17.1 — 2026-10-27

**Token highlight:** - · **Compared with:** -

No token or speed saving is claimed. Gate behaviour ported from the v5 draft; the tests named below are the evidence, and nothing else is claimed.

**Fixed**

- The gate lock holder keeps its descriptor private, runs the gate as a child and records an owner token that nested `--check` calls validate; a guardian process holds the lock until the gate has ended, and the gate announces its pid to the guardian before it starts, so a holder killed with SIGKILL cannot leave the gate running without the lock. A process a check leaves running in the background no longer keeps the checkout locked. The busy message and exit code 2 are unchanged. Tests: `test_lock_inherit.py`, `test_gate_lock.py`. Process start times and parents come from `/proc` on Linux and from `ps -o … -p` elsewhere; without either, the gate stops with "Quality Gate lock unavailable" (exit 2, NOT_RUN) instead of reporting a busy lock (`test_gate_lock.py`). The tree kill still depends on `ps`: without it, a holder killed with SIGKILL stops the gate shell but not the check it is running, which can outlive the lock and overlap a later gate. Gate runs were verified on macOS, Linux CI and a Linux image without `ps`; the kill guarantee only where `ps` exists.
- The Codex hook counts a busy gate lock like the Claude hook (three blocks, then a release marked UNVERIFIED). Its Stop path fails closed: a missing or failing `lean_core.py`, a failed import of `gate_mode`, `gate_evidence` or `contract_guard`, or any unexpected error gives a fixed block message instead of empty output, and a zero-status `SystemExit` counts as a failure. Tests: `test_codex_busy.py`, `test_codex_partial.py`.
- Refusal markers are kept per session: `.agent-runtime/gate-failed.<key>` and `.agent-runtime/gate-refusal.<key>` (and the Codex equivalents), `<key>` being the first 16 hex characters of the sha256 of the session id. Runs without a session id keep the previous file names, and a keyed seed or pass removes those once. A marker that is a directory or other non-regular file, an unusable `.agent-runtime`, and a malformed `session_id` are bounded by the cap of three instead of blocking without end. A session key that is not 16 lowercase hex characters is ignored wherever it would become a file name. `workflow.py` status reads the newest marker. Tests: `test_session_markers.py`, `test_busy_cap.py`, `test_gate_integrity.py`.
- `test_lock_inherit.py` accepts the pipe type lsof reports on Linux (`FIFO`) as well as macOS (`PIPE`); the Linux CI jobs failed on that assertion alone.
- CI clones full history, so the partial-upgrade tests that need the 4.17.0 commit run instead of skipping.
- `gate_evidence.py hook-field` answers a JSON array or scalar payload with "payload must be a JSON object" (exit 2) instead of a Python error text. Test: `test_hook_field.py` (6 non-object payloads fail on the previous code, pass now).

**Added**

- `lean_core.py`: `gate_refusal`, `session_key` and `valid_session_key`, the single refusal decision used by the Claude Stop hook, the shell runner and the Codex hook (`test_lean_core.py`). It is a protected gate control file.

**Known limits:** after a killed holder, the guardian's no-pid fallback signals orphans of the holder's process group, which could include an unrelated background process started from the same group. `workflow.py` status may show FAIL from another session's refusal marker until it is pruned. In Codex, an invalid gate policy or hook input is still reported and released, not blocked. `test_busy_cap.py` and `test_codex_busy.py` compare the unchanged paths with `HEAD`, so they guard later edits, not this release against 4.17.0. CI runs Linux on `ubuntu-24.04`, the last runner image with Python 3.9.

**Upgrade:** update `.lean/scripts/lean_core.py`, `gate_evidence.py`, `gate_lock.py`, `quality-gate.sh`, `.claude/hooks/quality-gate.sh` and `.codex/hooks/quality_gate.py` together, then approve the changed controls through the existing review procedure. A Codex hook updated without `lean_core.py` degrades (a fresh Stop blocks once, a continued Stop is released UNVERIFIED), checked by `test_partial_upgrade.py`. One in-flight refusal restarts at count 1. A project test fixture that copies the gate scripts must also copy `lean_core.py`, and a test that reads the refusal marker of a run with a session id must read `.agent-runtime/gate-failed.<key>` instead of `.claude/.gate-failed` (the legacy name still applies without a valid session id).

## 4.17.0 — 2026-10-25

**Token highlight:** - · **Compared with:** -

- Keep each session's original commit boundary across commits, resumes, prompt clearing and later gate passes. Committed High-risk changes still require a current independent HIGH-depth review in Claude and Codex.
- Apply every retained target's High-risk policy to its application changes, including after clearing or switching the active target and after committing application and parent gitlink changes. Handle new targets and unborn parent repositories; changed deinitialized High-risk targets require initialization before validation.
- Protect retained target gate blocks and trusted-control references, including inactive targets, and protect the submodule gate implementation. Check controls before executing target commands in shared, standalone and provider entrypoints. Reuse the root review receipt and reject stale coverage or unsafe retained policy links.
- Add regressions for the reproduced gate gaps and a reproducible offline context inventory. Startup and fixed-task input inventories remain 2,213 and 11,146 tokens with `o200k_base`; the five-file gate source inventory grows by 1,836 tokens (6.83%). These counts exclude runtime prompts, model output, retries and cache billing and do not establish actual usage or cost savings. See the [measurement artifact](../docs/benchmarks/2026-10-25/context-tokens.json) and [measurement script](../docs/benchmarks/2026-10-25/measure_context.py).

**Upgrade:** update the contract guard, shared gate runner, evidence helper, submodule helper and Codex adapter together. Keep project policy and runtime records. Inspect and approve newly protected controls through the existing approval/review procedure; an older accepted baseline may lack the new submodule control. Start a fresh session after upgrading to record its original commit boundary. Initialize a changed retained High-risk target before gating it. No configuration or data migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- เก็บ commit เริ่มต้นของ session ไว้ แม้ commit งาน, resume, ล้าง contract เมื่อมี prompt ใหม่ หรือผ่าน gate แล้ว งาน High-risk ที่ commit ไปยังต้องมี independent HIGH-depth review ที่ครอบคลุมสถานะปัจจุบัน ทั้ง Claude และ Codex
- ตรวจ High-risk policy ของทุก target ที่ยังเก็บ policy ไว้ แม้ล้างหรือสลับ target ปัจจุบัน และแม้ commit งานใน application กับ gitlink ของ parent แล้ว รองรับ target ใหม่และ parent ที่ยังไม่มี commit ส่วน target High-risk ที่เปลี่ยนและถูก deinitialize ต้อง initialize ก่อนตรวจ
- ป้องกัน gate block และ trusted-control references ของ target รวมถึง target ที่ไม่ได้เลือก และป้องกันตัว submodule gate ตรวจ controls ก่อนรันคำสั่งของ target ในทุก entrypoint ใช้ review receipt ของ root ร่วมกัน และปฏิเสธหลักฐานที่ล้าสมัยหรือ policy link ที่ไม่ปลอดภัย
- เพิ่ม regression ของช่องว่างที่ทำซ้ำได้ พร้อมสคริปต์นับ context แบบ offline ชุด startup และ fixed-task ยังเป็น 2,213 กับ 11,146 tokens เมื่อใช้ `o200k_base` ส่วน inventory โค้ด gate ห้าไฟล์เพิ่ม 1,836 tokens (6.83%) ตัวเลขนี้ไม่รวม runtime prompts, output, retries และ cache billing จึงยังสรุป usage หรือค่าใช้จ่ายจริงไม่ได้ ดู [ผลวัด](../docs/benchmarks/2026-10-25/context-tokens.json) และ [สคริปต์](../docs/benchmarks/2026-10-25/measure_context.py)

**เมื่ออัปเกรด:** อัปเดต contract guard, shared gate runner, evidence helper, submodule helper และ Codex adapter พร้อมกัน เก็บ policy และ runtime records ของโปรเจกต์ไว้ ตรวจ diff และอนุมัติ controls ที่เพิ่มการป้องกันตามขั้นตอนเดิม เพราะ baseline เก่าอาจยังไม่มี submodule control เริ่ม session ใหม่หลังอัปเกรดเพื่อบันทึก commit เริ่มต้น และ initialize target High-risk ที่เปลี่ยนก่อนรัน gate ไม่ต้องย้าย configuration หรือข้อมูล

</details>

## 4.16.0 — 2026-10-24

**Token highlight:** - · **Compared with:** -

Prepare project operations with optional playbooks and get earlier feedback from workflow checks. Deployment and rollback execution still require an explicit request; preparation and read-only readiness checks do not authorize execution.

- Print parallel test-job status as each job completes, including fast failures behind earlier slow jobs; retain all checks, detailed failure blocks and the final recap in submission order. Barrier regression and separate feedback-latency measurements are retained with the benchmark notes.
- Run the full CI regression suite with six shards per Python file while retaining the CPU-sized worker pool and all matrix checks. Local paired measurements and actual test-ID coverage are retained in `docs/benchmarks/2026-10-24/`; remote matrix timings remain unmeasured.
- Index active and archived tracker documents once per queue validation instead of rescanning them for every item; count and stat only IDs referenced by active or archived queue records to avoid unrelated history work. Preserve exact ID linkage, duplicate detection, validation order and fresh lookups on each call.
- Add optional `lean-playbook` for project deployment/backup/rollback preparation, read-only readiness checks and explicitly requested execution. Include reusable playbook/release record templates, provider-parity discovery tests and compatibility with the previous 17-skill registry. Nine core skills remain enabled by default; the optional pack now has nine skills. Projects with deployment targets are offered the skill during init without automatic activation or execution.
- Upgrade shared assets, canonical skills, templates, registry and discovery tooling together; preserve project operations documents and release records. Reload runtime skills after enabling the optional pack. No configuration or record migration is needed.

**Local measurements:** paired full-suite medians fell from 175.748 s to 97.346 s (44.6% less elapsed time), with the same 445 test IDs executed exactly once in each measured run. The final suite adds the completion-order regression for 446 tests. Sparse queue fixtures with 1 or 10 linked items and 10,000 tracker files took about 7–21% less time locally. A deliberately blocked-first fixture reported failure status in 0.113015 s instead of 1.622919 s; total duration stayed about 1.6 s. These results do not establish remote CI speed, overall agent performance or token savings. Methods, raw samples and limitations are retained in [the benchmark notes](../docs/benchmarks/2026-10-24/README.md).

**Upgrade:** update the shared assets, canonical skills, playbook/release templates, registry and discovery tooling together. Preserve project operations documents, release records and the existing optional-skill selection. Nine core skills remain enabled by default and the optional pack now has nine skills; reload runtime discovery after enabling it. No data, configuration or record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

เตรียมงานดูแลระบบด้วย playbook แบบเลือกเปิดใช้ และรับผลตรวจ workflow ได้เร็วขึ้น การ deploy หรือ rollback ยังต้องมีคำขอให้ลงมืออย่างชัดเจน การเตรียมเอกสารและตรวจความพร้อมแบบอ่านอย่างเดียวไม่ได้อนุญาตให้ดำเนินการจริง

- แสดงสถานะงานทดสอบขนานทันทีที่แต่ละงานเสร็จ รวมถึงงานที่ fail เร็วแต่ถูกส่งหลังงานช้า ยังคงรันทุก check และแสดงรายละเอียด failure กับสรุปท้ายตามลำดับส่งงาน เก็บ regression ที่ใช้ barrier และผลวัดเวลารอ feedback แยกไว้กับ benchmark
- รัน regression suite เต็มใน CI โดยแบ่งแต่ละไฟล์ Python เป็นหก shard ใช้ worker pool ตามจำนวน CPU และคงทุก matrix check ไว้ เก็บผลวัดแบบจับคู่ในเครื่องและ test ID ที่รันจริงใน `docs/benchmarks/2026-10-24/` โดยยังไม่ได้วัดเวลา remote matrix
- สร้างดัชนี tracker ปัจจุบันและที่เก็บในประวัติครั้งเดียวต่อการตรวจ queue แทนการสแกนซ้ำทุกรายการ นับและตรวจ stat เฉพาะ ID ที่ queue ปัจจุบันหรือประวัติอ้างถึง ยังคงการเชื่อม ID ที่ตรงกัน การตรวจซ้ำ ลำดับ validation และการค้นข้อมูลใหม่ในแต่ละครั้ง
- เพิ่ม optional `lean-playbook` สำหรับเตรียม deployment, backup และ rollback ของโปรเจกต์ ตรวจความพร้อมแบบอ่านอย่างเดียว และลงมือเมื่อมีคำขอชัดเจน มี template ของ playbook/release record, test ความเท่าเทียมของ discovery ทั้งสอง provider และรองรับ registry เดิมที่มี 17 skill ยังคงเปิดเก้า core skill เป็นค่าเริ่มต้น ส่วน optional pack มีเก้า skill โปรเจกต์ที่มีเป้าหมาย deployment จะได้รับคำแนะนำให้ใช้ระหว่าง init โดยไม่เปิดใช้หรือลงมือเอง
- อัปเกรด shared assets, canonical skills, templates, registry และ discovery tooling พร้อมกัน รักษาเอกสาร operations และ release records ของโปรเจกต์ไว้ โหลด skill ของ runtime ใหม่หลังเปิด optional pack ไม่ต้องย้าย configuration หรือ records

**ผลวัดในเครื่อง:** ค่ามัธยฐาน full suite แบบจับคู่ลดจาก 175.748 เป็น 97.346 วินาที (ใช้เวลาน้อยลง 44.6%) โดยแต่ละรอบรัน 445 test ID เดิมครั้งเดียวครบทุกตัว suite สุดท้ายเพิ่ม regression ของ completion-order รวมเป็น 446 test ส่วน fixture queue ที่มีรายการเชื่อมโยง 1 หรือ 10 รายการกับ tracker 10,000 ไฟล์ ใช้เวลาน้อยลงประมาณ 7–21% ในเครื่อง fixture ที่จงใจบล็อกงานแรกแสดงสถานะ failure ใน 0.113015 แทน 1.622919 วินาที แต่เวลารวมยังประมาณ 1.6 วินาที ผลเหล่านี้ไม่ได้ยืนยันความเร็ว remote CI, ประสิทธิภาพ agent โดยรวม หรือการประหยัด token ดูวิธีวัด ตัวอย่างดิบ และข้อจำกัดได้ใน [benchmark notes](../docs/benchmarks/2026-10-24/README.md)

**เมื่ออัปเกรด:** อัปเดต shared assets, canonical skills, template ของ playbook/release, registry และ discovery tooling พร้อมกัน รักษาเอกสาร operations, release records และการเลือกเปิด optional skill ของโปรเจกต์ไว้ เก้า core skill ยังเปิดเป็นค่าเริ่มต้น และ optional pack มีเก้า skill แล้ว โหลด discovery ของ runtime ใหม่หลังเปิดใช้ ไม่ต้องย้ายข้อมูล configuration หรือ records

</details>

## 4.15.0 — 2026-10-23

**Token highlight:** - · **Compared with:** -

- Show Quality Gate progress. A direct run of the shared runner prints each numbered check when it starts and with its elapsed time when it passes, a target gate numbers its checks, and `python3 .codex/hooks/quality_gate.py run` streams that output as it arrives. This adds two short lines per check to a direct run; pass the new `--quiet` flag to omit them. Claude and Codex Stops always run quietly, so a refusal shows the model only its failure and its fingerprint does not change with check times.
- Build the template smoke fixtures from the release asset registry (`.lean/assets.json`), `.gitignore`, Claude settings and the project provider slots, so host target records, runtime data, local notes and undeclared skill resources stay out of downstream fixtures.
- Make the 4.14.0 mid-turn rule work in Claude Code. A live run in Claude Code 2.1.309 showed that Claude runs `UserPromptSubmit` for a prompt typed mid-turn before it writes that prompt's queue record, so 4.14.0 never found one and still cleared the contract. The guard now keeps the contract while the transcript shows the turn still running: no `turn_duration`, person's prompt or interrupt since the binding. A Stop that blocks writes only `stop_hook_summary` and the turn goes on, so it no longer ends the turn. In a live nested session, `ping` typed during a 40-second tool call kept the declared contract, and the next prompt after the turn cleared it. Codex transcripts have no Claude entries, so every Codex prompt still clears the contract; a unit test and a live two-turn `codex exec` run (codex-cli 0.163.0) confirm it.

**Upgrade:** update `.lean/scripts/contract_guard.py`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/submodule.py`, `.codex/hooks/quality_gate.py`, `.lean/policy/CONTRACTS.md` and the tests together; the guard, the runner and the Codex adapter are protected gate controls. No configuration or record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- แสดงความคืบหน้าของ Quality Gate เมื่อรัน runner กลางโดยตรง จะพิมพ์หมายเลข check ตอนเริ่ม และพิมพ์เวลาที่ใช้ตอนผ่าน gate ของ target ก็ใส่หมายเลข check เช่นกัน และ `python3 .codex/hooks/quality_gate.py run` จะแสดงผลทันทีที่ได้ ไม่ต้องรอจนจบ การรันตรงจึงมีข้อความเพิ่ม check ละ 2 บรรทัดสั้นๆ ถ้าไม่ต้องการให้ใส่ flag ใหม่ `--quiet` ส่วน Stop ของ Claude และ Codex รันแบบเงียบเสมอ เมื่อ refuse model จึงเห็นเฉพาะ check ที่ fail และ fingerprint ของ refusal ไม่เปลี่ยนตามเวลาที่ check ใช้
- สร้าง smoke fixture ของ template จาก asset registry ของ release (`.lean/assets.json`), `.gitignore`, Claude settings และช่อง provider ของโปรเจกต์ ทำให้ records ของ target ฝั่ง host, ข้อมูล runtime, โน้ตส่วนตัว และไฟล์ของ skill ที่ไม่ได้ประกาศไว้ ไม่หลุดเข้า fixture ของโปรเจกต์ปลายทาง
- ทำให้กฎ mid-turn ของ 4.14.0 ใช้ได้จริงใน Claude Code จากการทดสอบจริงบน Claude Code 2.1.309 พบว่า Claude รัน `UserPromptSubmit` ของ prompt ที่พิมพ์ระหว่าง turn ก่อนจะเขียน record คิวของ prompt นั้น 4.14.0 จึงหา record ไม่เจอและยังล้าง contract อยู่ ตอนนี้ guard จะคง contract ไว้ตราบที่ transcript แสดงว่า turn ยังไม่จบ คือไม่มี `turn_duration`, prompt ใหม่จากคน หรือการ interrupt หลังผูก contract ส่วน Stop ที่ถูกบล็อกจะเขียนแค่ `stop_hook_summary` แล้ว turn ยังดำเนินต่อ จึงไม่นับเป็นการจบ turn อีก ในการทดสอบกับ session ซ้อนจริง พิมพ์ `ping` ระหว่างคำสั่งที่ใช้เวลา 40 วินาทีแล้ว contract ที่ declare ไว้ยังอยู่ และ prompt ถัดไปหลังจบ turn ล้าง contract ตามที่ควร ส่วน transcript ของ Codex ไม่มี entry แบบ Claude ทุก prompt ของ Codex จึงยังล้าง contract เหมือนเดิม ยืนยันด้วย unit test และการรัน `codex exec` 2 turn จริง (codex-cli 0.163.0)

**เมื่ออัปเกรด:** อัปเดต `.lean/scripts/contract_guard.py`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/submodule.py`, `.codex/hooks/quality_gate.py`, `.lean/policy/CONTRACTS.md` และ test ที่เกี่ยวข้องพร้อมกัน โดย guard, runner และ Codex adapter เป็น gate control ที่ถูกป้องกัน ไม่ต้องย้าย configuration หรือ records

</details>

## 4.14.0 — 2026-10-23

**Token highlight:** - · **Compared with:** -

- Keep the Task Contract when a Claude prompt arrives while the agent is still working. Such a prompt is queued in the transcript and delivered mid-turn, but the `UserPromptSubmit` hook cleared the contract, and the transcript binder then fell back to the turn's first contract line, dropping any contract declared since. During the 4.13.0 work this forced three extra `declare` calls and one control-drift gate refusal. `contract_guard.py` now keeps the contract when the transcript shows that prompt's queue record and no turn end, person's prompt or interrupt since the binding; any doubt still clears it, and Codex is unchanged.

**Upgrade:** update `AGENTS.md`, `.lean/policy/CONTRACTS.md`, `.lean/policy/QUALITY.md`, `.lean/scripts/contract_guard.py` and `.lean/tests/test_contract_guard.py` together; the guard is a protected gate control. No configuration or record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- คง Task Contract ไว้เมื่อมี prompt ของ Claude เข้ามาขณะ agent ยังทำงานอยู่ prompt แบบนี้ถูกบันทึกใน transcript เป็นคิวและส่งเข้ามากลาง turn แต่ hook `UserPromptSubmit` เดิมล้าง contract ทิ้ง แล้วตัวผูก contract จาก transcript ก็ย้อนกลับไปใช้ contract บรรทัดแรกของ turn ทำให้ contract ที่ declare ใหม่หลังจากนั้นหายไป ระหว่างทำ 4.13.0 เหตุนี้ทำให้ต้อง `declare` เพิ่ม 3 ครั้ง และ gate refuse เรื่อง control drift 1 ครั้ง ตอนนี้ `contract_guard.py` จะคง contract ไว้เมื่อ transcript มี record คิวของ prompt นั้น และไม่มีการจบ turn, prompt ใหม่จากคน หรือการ interrupt หลังจากผูก contract ถ้าไม่แน่ใจยังล้างเหมือนเดิม ส่วน Codex ไม่เปลี่ยน

**เมื่ออัปเกรด:** อัปเดต `AGENTS.md`, `.lean/policy/CONTRACTS.md`, `.lean/policy/QUALITY.md`, `.lean/scripts/contract_guard.py` และ `.lean/tests/test_contract_guard.py` พร้อมกัน โดย guard เป็น gate control ที่ถูกป้องกัน ไม่ต้องย้าย configuration หรือ records

</details>

## 4.13.0 — 2026-10-23

**Token highlight:** - · **Compared with:** -

**Gate highlight:** this repository's Quality Gate took about **71–79% less wall time** than 4.12.0 on one 8-core machine: a median of 40.3 s versus 195.1 s over three interleaved direct runs of each version under heavy background load, and versus 141.0 s for 4.12.0 earlier the same day under lighter load. A Stop that follows a passing `--cache-tree` run on the same shipping state now reuses that pass in about 0.5 s instead of running the gate again (about 50 s), for both providers. Timings, method and the downstream token baseline behind the wording changes are kept in `docs/history/measurements/2026-10-22-gate-speed.md` in the source repository.

- Run `.lean/tests/test-hooks.sh` as five concurrent parts, each in its own subshell and scratch directory. The same 110 cases still run once each and print in the same order. Failed case names are listed again after the totals, where a gate's 40-line output tail still shows them, and a part that stops early counts as a failure.
- Add `--shards N` to `.lean/tests/run_tests.py` to split each test file's tests across up to N processes, and run a named `*.sh` suite with bash in the same pool. After the failure output it repeats every failing test or case name, so a gate's output tail names them all. This repository's gate now runs `test-hooks.sh` and `test_gate_integrity.py` together with `--shards 6`, after its quicker checks.
- Remove instructions that cost Claude extra round trips: `CLAUDE.md` and `AGENTS.md` say the imported files are already loaded, and `AGENTS.md` limits `declare` in Claude to a turn whose first tool call writes, to replacing a bound contract and to recovering from a denied write; Codex still declares first. In the downstream baseline, 75 of 163 `declare` calls came later in a turn whose written contract line the guard could already bind.
- Reuse a passing gate run for both providers. A run made with `--cache-tree`, direct or Stop, records the shipping state, and a later `--cache-tree` run or either provider's Stop on that unchanged state reuses the pass instead of running the checks again. Contract, review-receipt and High-risk checks still run, a direct run's pass never excuses a missing contract line at Claude's Stop, and any refusal other than a contract refusal drops the record. `.codex/hooks.json` now passes `--cache-tree` to the Codex Stop as `.claude/settings.json` does for Claude, and `/lean-gate` adds it when the project's Stop commands use it. Runs without it, including `python3 .codex/hooks/quality_gate.py run`, always execute.

**Upgrade:** update `AGENTS.md`, `CLAUDE.md`, `.lean/CUSTOMIZING.md`, `.lean/policy/QUALITY.md`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/workflow.py`, `.lean/skills/lean-gate/SKILL.md`, `.lean/tests/test-hooks.sh`, `.lean/tests/run_tests.py`, `.lean/tests/test_run_tests.py`, `.lean/tests/test_gate_integrity.py`, `.codex/hooks.json` and `.codex/hooks/quality_gate.py` together; the runner, Codex adapter and hooks file are protected gate controls. Projects whose checks read ignored, installed or environment inputs should drop `--cache-tree` from `.codex/hooks.json` as well as from `.claude/settings.json`. Gates that call `.lean/tests/test-hooks.sh` get the concurrent parts without changes. To shard more of a gate, replace lines such as `python3 -m unittest discover -s .lean/tests -p 'test_gate_integrity.py'` with `python3 .lean/tests/run_tests.py --shards 6 test-hooks.sh test_gate_integrity.py`; that edits a protected gate control, so record its approval or HIGH review as usual. No configuration, record or queue migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

**ผลด้านเวลา gate:** Quality Gate ของ repository นี้ใช้เวลาน้อยลงประมาณ **71–79%** เทียบกับ 4.12.0 บนเครื่อง 8 core เครื่องเดียว: ค่ามัธยฐาน 40.3 วินาที เทียบกับ 195.1 วินาที จากการรันตรงแบบสลับกันรุ่นละสามรอบขณะเครื่องมีโหลดหนัก และเทียบกับ 141.0 วินาทีของ 4.12.0 ที่วัดก่อนหน้าในวันเดียวกันขณะโหลดเบากว่า Stop ที่ตามหลังการรันด้วย `--cache-tree` ที่ผ่านแล้วบน shipping state เดิม จะใช้ผลนั้นซ้ำในประมาณ 0.5 วินาที แทนการรัน gate ใหม่ (ประมาณ 50 วินาที) ทั้งสอง provider เวลาดิบ วิธีวัด และ baseline ด้าน token จากโปรเจกต์ downstream ที่ใช้ประกอบการแก้ข้อความ เก็บไว้ที่ `docs/history/measurements/2026-10-22-gate-speed.md` ใน source repository

- รัน `.lean/tests/test-hooks.sh` เป็นห้าส่วนพร้อมกัน แต่ละส่วนอยู่ใน subshell และ scratch directory ของตัวเอง ทั้ง 110 case ยังรันครั้งเดียวและพิมพ์ตามลำดับเดิม ชื่อ case ที่ล้มเหลวจะแสดงซ้ำหลังบรรทัดสรุป ซึ่งยังอยู่ใน 40 บรรทัดท้ายที่ gate แสดง ส่วนที่หยุดกลางทางนับเป็นความล้มเหลว
- เพิ่ม `--shards N` ใน `.lean/tests/run_tests.py` เพื่อแบ่ง test ของแต่ละไฟล์ไปรันได้สูงสุด N process และรัน suite `*.sh` ที่ระบุชื่อด้วย bash ใน pool เดียวกัน หลังผลที่ล้มเหลวจะพิมพ์ชื่อ test หรือ case ที่ล้มทั้งหมดซ้ำอีกรอบ ท้าย output ของ gate จึงแสดงครบ gate ของ repository นี้จึงรัน `test-hooks.sh` กับ `test_gate_integrity.py` พร้อมกันด้วย `--shards 6` หลังจากตรวจข้อที่เร็วกว่าเสร็จแล้ว
- ตัดคำสั่งที่ทำให้ Claude ต้องเรียก tool เพิ่มโดยไม่จำเป็น: `CLAUDE.md` และ `AGENTS.md` ระบุว่าไฟล์ที่ import โหลดอยู่แล้ว และ `AGENTS.md` ให้ Claude ใช้ `declare` เฉพาะใน turn ที่ tool call แรกเป็นการเขียน ตอนแทนที่ contract ที่ผูกไว้แล้ว และหลังโดนปฏิเสธการเขียน ส่วน Codex ยัง declare ก่อนเหมือนเดิม ใน baseline ของ downstream มี `declare` 75 จาก 163 ครั้งที่เกิดภายหลังใน turn ซึ่ง guard ผูก contract line ที่เขียนไว้ได้อยู่แล้ว
- ใช้ผล gate ที่ผ่านแล้วซ้ำได้ทั้งสอง provider: การรันด้วย `--cache-tree` ไม่ว่าจะรันตรงหรือผ่าน Stop จะบันทึก shipping state ไว้ และการรันด้วย `--cache-tree` หรือ Stop ของ provider ใดก็ได้ครั้งถัดไปบน state เดิมจะใช้ผลนั้นแทนการรัน check ใหม่ แต่ยังตรวจ contract, review receipt และ High-risk เหมือนเดิม pass จากการรันตรงไม่ทำให้ Stop ของ Claude ยอมรับงานที่ไม่มี contract line และการ refuse ทุกแบบยกเว้น contract refusal จะลบผลที่บันทึกไว้ `.codex/hooks.json` ส่ง `--cache-tree` ให้ Stop ของ Codex แบบเดียวกับที่ `.claude/settings.json` ทำกับ Claude และ `/lean-gate` จะใส่ flag นี้เมื่อ Stop ของโปรเจกต์ใช้อยู่ การรันที่ไม่ใส่ flag รวมถึง `python3 .codex/hooks/quality_gate.py run` ยังรันจริงทุกครั้ง

**เมื่ออัปเกรด:** อัปเดต `AGENTS.md`, `CLAUDE.md`, `.lean/CUSTOMIZING.md`, `.lean/policy/QUALITY.md`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/workflow.py`, `.lean/skills/lean-gate/SKILL.md`, `.lean/tests/test-hooks.sh`, `.lean/tests/run_tests.py`, `.lean/tests/test_run_tests.py`, `.lean/tests/test_gate_integrity.py`, `.codex/hooks.json` และ `.codex/hooks/quality_gate.py` พร้อมกัน โดย runner, Codex adapter และไฟล์ hooks เป็น gate control ที่ถูกป้องกัน โปรเจกต์ที่ check อ่านไฟล์ที่ถูก ignore, dependency ที่ติดตั้งไว้ หรือค่าจาก environment ควรเอา `--cache-tree` ออกจาก `.codex/hooks.json` และ `.claude/settings.json` gate ที่เรียก `.lean/tests/test-hooks.sh` จะได้การรันแบบขนานทันทีโดยไม่ต้องแก้ ถ้าต้องการแบ่ง shard เพิ่ม ให้แทนบรรทัดอย่าง `python3 -m unittest discover -s .lean/tests -p 'test_gate_integrity.py'` ด้วย `python3 .lean/tests/run_tests.py --shards 6 test-hooks.sh test_gate_integrity.py` ซึ่งเป็นการแก้ gate control ที่ถูกป้องกัน จึงต้องบันทึกการอนุมัติหรือ HIGH review ตามปกติ ไม่ต้องย้าย configuration, records หรือ queue

</details>

## 4.12.0 — 2026-10-22

**Token highlight:** - · **Compared with:** -

- Add `auto_fixloop` and `manual_fixloop` gate modes in `.lean/scripts/gate_mode.py` alongside `auto` and `manual`: `auto_fixloop` runs the shared Quality Gate automatically on Stop and auto-loops over actionable code, test and lint failures until the gate passes without asking between rounds; `manual_fixloop` skips automatic Stops (`NOT_RUN`), always requires user authorization before starting a full gate run, and then auto-loops until the gate passes—stopping only for genuine requirement/design questions or missing environment tools.
- Align Stop hook retry caps across both providers: Codex's `.codex/hooks/quality_gate.py` now enforces the same three-attempt continuation cap (`max_refusals = 3`) and immediate unchanged-refusal `UNVERIFIED` release as Claude's Stop adapter.
- Connect accepted project standards (`docs/standards/` or `record_root`) directly into context selection (`CONTEXT.md`), review (`REVIEW.md`, `lean-review`, `.lean/roles/reviewer.md`), `/lean-pattern` and `/lean-audit`, enforcing `mandatory` standards on lines/behavior introduced or modified by a diff while keeping `recommended` standards and untouched legacy code non-blocking unless explicitly promoted.

**Upgrade:** update `AGENTS.md`, `.lean/README.md`, `.lean/CUSTOMIZING.md`, `.lean/policy/CONTEXT.md`, `.lean/policy/QUALITY.md`, `.lean/policy/RECOVERY.md`, `.lean/policy/REVIEW.md`, `.lean/roles/reviewer.md`, `.lean/scripts/gate_mode.py`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/contract_guard.py`, `.claude/hooks/session-start.sh`, `.codex/hooks/quality_gate.py`, and the shared `lean-gate`, `lean-review`, `lean-pattern` and `lean-audit` skills together. Existing `.codex/quality-gate.json` files (`{"auto": true|false}`) remain valid without migration.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- เพิ่มโหมด Gate `auto_fixloop` และ `manual_fixloop` ใน `.lean/scripts/gate_mode.py` ควบคู่กับ `auto` และ `manual` เดิม: `auto_fixloop` รัน Quality Gate อัตโนมัติใน Stop hook และวนแก้ทุกปัญหาที่แก้ได้ (code/test/lint) จนผ่านโดยไม่หยุดถามระหว่างรอบ ส่วน `manual_fixloop` ข้ามการรันอัตโนมัติใน Stop hook (`NOT_RUN`) และต้องขออนุญาตผู้ใช้ก่อนเริ่มรัน full gate เสมอ แต่เมื่อเริ่มรันแล้วจะวนแก้ปัญหาและรันซ้ำจนผ่านโดยไม่ถามซ้ำ (หยุดถามเฉพาะเมื่อมีคำถามเชิง requirement/design จริงๆ หรือขาดเครื่องมือในสภาพแวดล้อม)
- ปรับเพดานการวนซ้ำใน Stop hook ของทั้งสอง provider ให้เท่ากัน: `.codex/hooks/quality_gate.py` ของ Codex รองรับการบล็อกเพื่อวนแก้สูงสุด 3 รอบ (`max_refusals = 3`) และปล่อยหลุด `UNVERIFIED` ทันทีเมื่อสถานะและสาเหตุซ้ำเดิมโดยไม่มีการแก้ไข เหมือนกับฝั่ง Claude
- เชื่อมโยงมาตรฐานของโปรเจกต์ที่อนุมัติแล้ว (`accepted` project standards) เข้ากับการเลือกบริบท (`CONTEXT.md`), การรีวิว (`REVIEW.md`, `lean-review`, `.lean/roles/reviewer.md`), `/lean-pattern` และ `/lean-audit` โดยบังคับใช้กฎระดับ `mandatory` เฉพาะจุดที่เพิ่มหรือแก้ไขใน diff ปัจจุบัน (clean-as-you-code) และคงกฎ `recommended` หรือโค้ดเก่าที่ไม่ได้แตะไว้ไม่ให้บล็อกงาน ยกเว้นระบุไว้ในขอบเขตงานอย่างชัดเจน

**เมื่ออัปเกรด:** อัปเดต `AGENTS.md`, `.lean/README.md`, `.lean/CUSTOMIZING.md`, `.lean/policy/CONTEXT.md`, `.lean/policy/QUALITY.md`, `.lean/policy/RECOVERY.md`, `.lean/policy/REVIEW.md`, `.lean/roles/reviewer.md`, `.lean/scripts/gate_mode.py`, `.lean/scripts/quality-gate.sh`, `.lean/scripts/contract_guard.py`, `.claude/hooks/session-start.sh`, `.codex/hooks/quality_gate.py` และสกิล `lean-gate`, `lean-review`, `lean-pattern`, `lean-audit` พร้อมกัน ไฟล์ `.codex/quality-gate.json` เดิม (`{"auto": true|false}`) ยังคงใช้งานได้ทันทีโดยไม่ต้องแปลงข้อมูล

</details>

## 4.11.0 — 2026-10-22

**Token highlight:** - · **Compared with:** -

- Expand `/lean-pattern` and `/lean-audit` with concrete guidance for stack-appropriate repository structure, module boundaries and dependency direction without prescribing a single universal folder tree.
- Add technical and per-locale linguistic i18n standards and audit checks: no hardcoded user-facing strings, locale key parity, interpolation/pluralization instead of string concatenation across variables, grammatical accuracy and natural phrasing per language rather than literal word-for-word translation, shared terminology/glossary consistency, and consistent tone/politeness level.
- Distinguish greenfield/early-stage setup from existing repositories: `/lean-init` and `/lean-pattern` guide new projects to define baselines early to avoid large rework, while `/lean-pattern` and `/lean-audit` inspect existing codebases first and route uncertain structural moves or terminology/copy changes through `/lean-grill` before remediation.

**Upgrade:** update `AGENTS.md`, `.lean/README.md`, `.lean/OPTIONAL.md`, `docs/skills.md`, and the shared `lean-init`, `lean-pattern` and `lean-audit` skills together. No configuration, task record or queue migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- ขยายความสามารถของ `/lean-pattern` และ `/lean-audit` ให้รองรับการกำหนดและตรวจสอบโครงสร้างโฟลเดอร์ตาม stack จริง ขอบเขตโมดูล (module boundaries) และทิศทางการ import (dependency direction) โดยไม่บังคับโครงสร้างโฟลเดอร์ตายตัวแบบเดียวทุกโปรเจกต์
- เพิ่มเกณฑ์มาตรฐานและการตรวจสอบด้าน i18n และคุณภาพภาษาในแต่ละภาษา: ห้ามฝังข้อความที่ผู้ใช้เห็นไว้ในโค้ด (hardcoded user-facing strings), ความครบถ้วนของ key ทุกภาษา, การใช้ interpolation/pluralization แทนการต่อ string ข้ามตัวแปร, ความถูกต้องตามหลักไวยากรณ์และสำนวนที่เป็นธรรมชาติของแต่ละภาษาแทนการแปลตรงตัวแบบคำต่อคำ, ความสม่ำเสมอของคลังคำศัพท์ (terminology/glossary), และระดับภาษา/ความสุภาพที่สอดคล้องกัน
- แยกแนวทางระหว่างโปรเจกต์เริ่มใหม่กับโปรเจกต์เดิมที่มีโค้ดอยู่แล้ว: `/lean-init` และ `/lean-pattern` ช่วยวางมาตรฐานตั้งแต่ช่วงเริ่มต้นเพื่อลดงานรื้อแก้ภายหลัง ส่วนโปรเจกต์เดิมจะใช้ `/lean-pattern` และ `/lean-audit` ตรวจสภาพจริงก่อนและส่งประเด็นที่อาจกระทบโครงสร้างหรือความหมายไปถามผ่าน `/lean-grill` ก่อนลงมือแก้ไข

**เมื่ออัปเกรด:** อัปเดต `AGENTS.md`, `.lean/README.md`, `.lean/OPTIONAL.md`, `docs/skills.md` และสกิล `lean-init`, `lean-pattern`, `lean-audit` พร้อมกัน ไม่ต้องย้ายข้อมูลตั้งค่า บันทึกงาน หรือคิว

</details>

## 4.10.0 — 2026-10-22

**Token highlight:** - · **Compared with:** -

- Shorten skill names to single-word `lean-<name>` commands for faster autocomplete: `lean-multi-agent` $\rightarrow$ `lean-agents`, `lean-skill-effort` $\rightarrow$ `lean-effort`, `lean-update-workflow` $\rightarrow$ `lean-update`, `lean-takeover-workflow` $\rightarrow$ `lean-takeover`, `lean-use-submodule` $\rightarrow$ `lean-target`, and `lean-model-update` $\rightarrow$ `lean-catalog`.
- Consolidate `lean-clean-queue` and `lean-clean-repo` into a single reworked `/lean-prune` skill (`queue [all|old] [--days N] [--dry-run|--apply]` and `repo [scope]`).
- Remove the unused `lean-quality-gate-mode` skill while keeping `gate_mode.py` and `QUALITY.md` intact. Keep nine core skills discovered by default and eight optional skills behind `skill_pack.py` so per-turn system-prompt overhead does not increase.
- Allow `takeover.py` and `shared_assets.py` to recognize, retire and roll back previous v4 skill slots and discovery links during upgrades, while `check_structure.py` rejects retired or dangling skill slots.

**Upgrade:** update the shared skills, `.lean/assets.json`, both discovery link trees (`.claude/skills/` and `.agents/skills/`), scripts, policies and guides together, and remove retired v4 skill directories and discovery symlinks. Existing `.lean/skill-effort.json` overrides that name old skill identifiers should be updated to the new names (`lean-agents`, `lean-effort`, `lean-prune`, `lean-catalog`, `lean-takeover`, `lean-target`, `lean-update`). No task record or queue migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- ย่อชื่อสกิลเป็นคำเดียวในรูปแบบ `lean-<name>` เพื่อเรียกใช้งานและพิมพ์ต่อท้ายได้ไวขึ้น: `lean-multi-agent` $\rightarrow$ `lean-agents`, `lean-skill-effort` $\rightarrow$ `lean-effort`, `lean-update-workflow` $\rightarrow$ `lean-update`, `lean-takeover-workflow` $\rightarrow$ `lean-takeover`, `lean-use-submodule` $\rightarrow$ `lean-target`, และ `lean-model-update` $\rightarrow$ `lean-catalog`
- ยุบรวม `lean-clean-queue` และ `lean-clean-repo` เข้าเป็นสกิล `/lean-prune` ตัวเดียว (`queue [all|old] [--days N] [--dry-run|--apply]` และ `repo [scope]`)
- ถอดสกิล `lean-quality-gate-mode` ที่ไม่ได้ใช้งานออก โดยคง `gate_mode.py` และ `QUALITY.md` ไว้ คงจำนวน 9 core skills ตามค่าเริ่มต้น และ 8 optional skills ผ่าน `skill_pack.py` เพื่อไม่เพิ่มภาระ system prompt token ต่อ turn
- รองรับการตรวจสอบ ลบ และ rollback ช่องสกิลรุ่น v4 เดิมใน `takeover.py` กับ `shared_assets.py` ระหว่างการอัปเกรด และให้ `check_structure.py` ปฏิเสธช่องสกิลที่เลิกใช้หรือลิงก์ค้าง

**เมื่ออัปเกรด:** อัปเดต shared skills, `.lean/assets.json`, discovery links ทั้งสองฝั่ง (`.claude/skills/` และ `.agents/skills/`), สคริปต์, นโยบาย และเอกสารพร้อมกัน พร้อมลบโฟลเดอร์สกิลและ symlinks ชื่อเดิมออก หากมี `.lean/skill-effort.json` ที่ตั้งค่าเฉพาะสกิลด้วยชื่อเดิม ให้เปลี่ยนเป็นชื่อใหม่ ไม่ต้องย้ายข้อมูลบันทึกงานหรือคิว

</details>

## 4.9.0 — 2026-10-20

**Token highlight:** - · **Compared with:** -

- Require explicit task-sized model and effort settings whenever the spawn tool supports them, including when they match the parent.
- Check runtime-specific context rules before dispatch. When Codex model or effort overrides require fresh context, use `fork_turns: "none"` with a self-contained brief. Full-history forks need a recorded context requirement and suitable settings; independent HIGH review always starts fresh.
- Record context mode and concrete requested settings separately from runtime-reported settings. Replace bare `inherited/inherited` records with known values and limitations; use `unavailable` for metadata the runtime does not expose.
- Keep model choices portable and task-sized. This release does not change main-session settings or set every subagent to an economical default.

**Upgrade:** update `AGENTS.md`, `MODELS.md` and `lean-multi-agent` together. Preserve project model mappings and check the current spawn tool's override capabilities. No configuration or record migration is needed; the new dispatch format applies to future assignments. No new token benchmark was run.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- ส่ง model และ effort ตามขนาดงานอย่างชัดเจนเมื่อเครื่องมือรองรับ แม้จะตรงกับค่าของ agent ต้นทาง
- ตรวจข้อจำกัดเรื่องบริบทของ runtime ก่อน dispatch หาก Codex ต้องเริ่มบริบทใหม่เพื่อเปลี่ยน model หรือ effort ให้ใช้ `fork_turns: "none"` พร้อม brief ที่มีข้อมูลครบ การ fork ประวัติทั้งหมดต้องมีเหตุผลและ settings ที่เหมาะกับงาน ส่วน independent HIGH review ต้องเริ่มบริบทใหม่เสมอ
- บันทึก context mode และค่าที่ร้องขอแยกจากค่าที่ runtime รายงาน แทน `inherited/inherited` ด้วยค่าที่ทราบและข้อจำกัด หาก runtime ไม่เปิดเผยข้อมูลให้ระบุ `unavailable`
- คงการเลือกโมเดลตามขนาดงานและความสามารถของ runtime รุ่นนี้ไม่เปลี่ยน settings ของ session หลักหรือกำหนดให้ agent ลูกทุกตัวใช้โมเดลประหยัด

**เมื่ออัปเกรด:** อัปเดต `AGENTS.md`, `MODELS.md` และ `lean-multi-agent` พร้อมกัน เก็บ model mappings ของโปรเจกต์และตรวจความสามารถในการ override ของเครื่องมือที่ใช้ ไม่ต้องย้าย configuration หรือ records รูปแบบ dispatch ใหม่ใช้กับงานที่ส่งหลังอัปเกรด และไม่มีการวัด token ชุดใหม่

</details>

## 4.8.1 — 2026-10-19

**Token highlight:** - · **Compared with:** -

- Rewrite all 27 earlier release entries around what changed, its impact and any required upgrade steps. Remove long implementation stories and unnecessary experiment details.
- Add a collapsed Thai translation to every release and the general upgrade guide.
- Give token comparisons clear baselines and workload context. Show increased usage honestly, mark missing comparisons with `-`, and link to the original reports.

**Upgrade:** update the documentation and baseline references together. No configuration, record or runtime migration is needed. This documentation patch adds no new token benchmark.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- ปรับประวัติทั้ง 27 รุ่นก่อนหน้าให้เน้นสิ่งที่เปลี่ยน ผลต่อผู้ใช้ และขั้นตอนอัปเกรดที่จำเป็น ตัดเรื่องราวการแก้ภายในกับรายละเอียดทดลองที่ไม่จำเป็นออก
- เพิ่มภาษาไทยแบบพับซ่อนในทุกรุ่นและคู่มืออัปเกรดโดยรวม
- ระบุรุ่นที่ใช้เทียบกับขอบเขตการวัด token ให้ชัด บอกผลที่ใช้เพิ่มตามจริง ใส่ `-` เมื่อไม่มีข้อมูลเทียบ และเชื่อมไปยังรายงานต้นฉบับ

**เมื่ออัปเกรด:** อัปเดตเอกสารและเลข baseline พร้อมกัน ไม่ต้องย้าย configuration, records หรือ runtime รุ่นนี้ปรับเอกสารและไม่มีการวัด token ชุดใหม่

</details>

## 4.8.0 — 2026-10-19

**Token highlight:** about **44% fewer than 4.4.0** and **52% fewer than 4.7.0** in the reported TCK303 replays: 20.0M tokens per run versus 35.4M and 41.8M. The budgeted setup had two unpaired runs; each baseline had four. This small sample does not isolate the causes of the saving.

Keep long delegated tasks manageable with smaller assignments and clearer handoffs.

- Give each worker a few files and about **50 turns**. A turn is one model request, even when it makes several tool calls. Split larger tasks before dispatch; keep tasks that already fit together.
- Keep required tests in the brief, including page- or integration-level tests for user-visible behavior. Split the work rather than drop tests to fit the budget.
- When the budget runs out, return changed files, check results and remaining steps. Send the next slice to a fresh worker. Resume a spent worker only to finish its handoff report or recover from a transient runtime error.
- The Controller checks the worker's changes before accepting them, treats missing reports as partial work, and resolves unfinished claims before redispatch. In `full` mode, it renews its own claim before dispatch and when the worker returns; a worker that may outlast the remaining lease gets its own item and claim. Expired claims need a new request ID.
- Structure checks and the README now cover these rules. Worker briefs also ask for focused reads, targeted edits and focused tests while working, followed by full assigned checks before completion.

**Upgrade:** update `lean-multi-agent`, `check_structure.py` and `test_structure.py` together. No record migration is needed. Custom Claude roles can use `maxTurns` and `autoCompactWindow` to back the brief's budget; keep the turn budget below the cap. Codex has no per-spawn turn cap, so its brief carries the budget. A hard cap can interrupt an edit, so always inspect partial work before accepting it.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** จากบันทึกการทดลอง TCK303 ใช้ประมาณ **44% น้อยกว่า 4.4.0** และ **52% น้อยกว่า 4.7.0** คำนวณจาก 20.0M tokens ต่อรอบ เทียบกับ 35.4M และ 41.8M ตามลำดับ ชุดกำหนดงบมีเพียงสองรอบและไม่ได้จับคู่เปรียบเทียบ ส่วน baseline มีอย่างละสี่รอบ จึงยังแยกสาเหตุของการประหยัดไม่ได้

แบ่งงานที่ส่งให้ worker ให้เล็กลง และส่งต่องานที่ยังไม่เสร็จให้ชัดเจนขึ้น

- มอบหมายครั้งละไม่กี่ไฟล์และประมาณ **50 turns** โดย 1 turn คือการเรียกโมเดล 1 ครั้ง แม้จะเรียกหลาย tools ในครั้งนั้น งานใหญ่ให้แบ่งก่อนส่ง ส่วนงานที่พอดีอยู่แล้วให้ทำต่อเนื่อง
- ระบุ tests ที่จำเป็นใน brief รวมถึง tests ระดับหน้าจอหรือ integration สำหรับพฤติกรรมที่ผู้ใช้เห็น หากเกินงบให้แบ่งงานเพื่อเก็บ tests ให้ครบ
- เมื่อใช้งบครบ ให้รายงานไฟล์ที่แก้ ผลตรวจ และขั้นตอนที่เหลือ แล้วใช้ worker ใหม่ทำส่วนต่อไป การ resume ตัวเดิมทำได้เฉพาะเพื่อจบรายงานส่งมอบหรือกู้คืนจากข้อผิดพลาดชั่วคราวของ runtime
- Controller ตรวจไฟล์ก่อนรับงาน ถือว่างานที่ไม่มีรายงานยังไม่ครบ และจัดการ claim ค้างก่อนส่งต่อ ในโหมด `full` ต้องต่ออายุ claim ของตัวเองก่อนส่งงานและเมื่อรับงานกลับ หาก worker อาจทำงานนานกว่า lease ที่เหลือ ให้มีรายการงานและ claim ของตัวเอง ส่วน claim ที่หมดอายุแล้วต้องขอใหม่ด้วย request ID ใหม่
- เพิ่ม structure checks และอัปเดต README รองรับกติกานี้ brief ยังให้ค้นหาก่อนอ่าน แก้เฉพาะจุด รัน tests ที่เกี่ยวข้องระหว่างทำ และรัน checks ที่รับผิดชอบครบก่อนส่งมอบงานที่เสร็จแล้ว

**เมื่ออัปเกรด:** อัปเดต `lean-multi-agent`, `check_structure.py` และ `test_structure.py` พร้อมกัน ไม่ต้องย้ายข้อมูลบันทึกงาน Claude role ที่กำหนดเองใช้ `maxTurns` และ `autoCompactWindow` ช่วยควบคุมงบได้ โดยตั้งงบ turns ต่ำกว่าเพดาน ส่วน Codex ยังไม่มีเพดานแยกต่อการ spawn จึงต้องระบุงบใน brief หาก hard cap ตัดระหว่างแก้ไฟล์ ต้องตรวจงานค้างก่อนรับเสมอ

</details>

## 4.7.0 — 2026-10-18

**Token highlight:** about **18% more than 4.4.0**, calculated from later TCK303 replay notes: 41.8M versus 35.4M tokens per run, with four runs per version. This workload did not show a token saving for 4.7.0.

- The contract guard recognizes more ways to write files, including scripts read from stdin, shell functions and archive commands. Ordinary read commands are less likely to be blocked by mistake.
- Clarify the limits of review evidence: local receipts help detect stale reviews but do not prove independence against someone who can write to the checkout.
- `workflow.py context` now names the source of its gate status. A direct or Codex run may show `NOT_RUN` or `STALE` because that summary reads Claude hook markers.
- Repair links in the archived tracker. Archiving still moves files without rewriting their links.

**Upgrade:** take the updated guard, evidence helper, gate runner, workflow CLI, contract policy and tests together. Protected controls need a trusted-ref match, a covering independent HIGH review or matching recorded approval. No record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** คำนวณจากบันทึก TCK303 ที่รายงานภายหลัง ใช้ประมาณ **18% มากกว่า 4.4.0** หรือ 41.8M เทียบกับ 35.4M tokens ต่อรอบ จากรุ่นละสี่รอบ งานชุดนี้จึงไม่ได้แสดงว่า 4.7.0 ประหยัด token

- contract guard รู้จักคำสั่งเขียนไฟล์ได้ครอบคลุมขึ้น เช่น shell ที่อ่านคำสั่งจาก stdin, shell functions และคำสั่ง archive พร้อมลดการบล็อกคำสั่งอ่านที่ไม่จำเป็น
- อธิบายข้อจำกัดของหลักฐานรีวิวให้ชัดขึ้น: receipt ช่วยตรวจว่าผลรีวิวยังตรงกับงาน แต่ไม่ใช่หลักฐานยืนยันความเป็นอิสระที่ป้องกันผู้มีสิทธิ์เขียน checkout ได้
- `workflow.py context` บอกที่มาของสถานะ gate แล้ว การรันตรงหรือผ่าน Codex อาจแสดง `NOT_RUN` หรือ `STALE` เพราะข้อมูลสรุปนี้อ่าน marker ของ Claude hook
- แก้ลิงก์ใน tracker ที่เก็บเข้าประวัติแล้ว การ archive ยังย้ายไฟล์โดยไม่แก้ลิงก์ให้เอง

**เมื่ออัปเกรด:** อัปเดต guard, evidence helper, gate runner, workflow CLI, contract policy และ tests พร้อมกัน การเปลี่ยน protected controls ต้องตรงกับ trusted ref มี independent HIGH review ที่ครอบคลุม หรือมีการบันทึกอนุมัติที่ตรงกับการเปลี่ยนแปลง ไม่ต้องย้ายข้อมูลบันทึกงาน

</details>

## 4.6.0 — 2026-10-18

**Token highlight:** - · **Compared with:** -

- A protected-control change can be accepted automatically when an independent HIGH review covers the entire change and its final state. Changes outside that coverage still need matching approval.
- Read-only inspection can run before the Task Contract is bound. Writes still need the contract first.
- A clear implementation request accepts the scope it names. Routine work continues; ambiguous requests, open material decisions, HIGH-risk work and spec-only requests still pause for clarification or approval as appropriate.
- Setup now documents trusted upstream refs so reviewed upgrades can be recognized without a repeated manual acceptance step.

**Upgrade:** update both providers' hooks/adapters and the shared guard, gate, policies and skills together. Preserve project additions and permissions. Use a trusted-ref match, a covering independent HIGH review or matching recorded approval for control changes. Projects that require approval for every scope draft should say so in their additions. No record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- ยอมรับการเปลี่ยน protected controls อัตโนมัติได้ เมื่อ independent HIGH review ครอบคลุมทั้งการเปลี่ยนแปลงและสถานะสุดท้าย ส่วนที่อยู่นอกผลรีวิวยังต้องมีการอนุมัติที่ตรงกัน
- อ่านและตรวจข้อมูลก่อนผูก Task Contract ได้ ส่วนการเขียนยังต้องมี contract ก่อน
- คำขอให้ลงมือทำที่ชัดเจนถือว่ายอมรับขอบเขตนั้นแล้ว งานตามขอบเขตจึงเดินต่อได้ ส่วนคำขอที่กำกวม มีเรื่องสำคัญยังไม่ตัดสินใจ เสี่ยง HIGH หรือขอเพียง spec ยังต้องหยุดเพื่อถามหรือขออนุมัติตามกรณี
- เพิ่มคำแนะนำเรื่อง trusted upstream refs เพื่อรับรู้การอัปเกรดที่ผ่านรีวิวแล้ว โดยไม่ต้องยืนยันการเปลี่ยน controls ซ้ำด้วยมือ

**เมื่ออัปเกรด:** อัปเดต hooks/adapters ของทั้งสอง providers พร้อม guard, gate, policies และ skills ที่ใช้ร่วมกัน เก็บ project additions และ permissions ไว้ การเปลี่ยน controls ต้องผ่าน trusted ref, independent HIGH review ที่ครอบคลุม หรือการบันทึกอนุมัติที่ตรงกัน หากโปรเจกต์ต้องการอนุมัติ scope ทุกครั้ง ให้ระบุไว้ใน additions ไม่ต้องย้ายข้อมูลบันทึกงาน

</details>

## 4.5.0 — 2026-10-18

**Token highlight:** the reported pre-release smoke comparison used **103k tokens per run**, about **24% fewer than 4.1.0** (136k) and **29% fewer than 4.3.0** (145k), across 16 runs. These reports do not isolate template edits from project-local settings. A separate guard-only trial used **0.8% more than 4.3.0** overall; it was a different experiment.

- Queue cleanup accepts `old --days N`. Queue path checks allow unrelated dependency links while protecting workflow state. `model_drift.py` checks local Codex catalog evidence without network access or writes.
- Review receipts can survive staging and committing the complete reviewed content. Partial commits or different content invalidate them. Routine tracker updates are excluded from the content fingerprint and still checked by the workflow CLI.
- Reduce contract and Stop interruptions: support the first-write declaration case, keep more safe reads available, and release repeated identical refusals as `UNVERIFIED` so the agent can report `BLOCKED`.
- Recognize protected controls that match reviewed upstream refs. Add `workflow.py context` and guarded archive support for completed trackers.
- Shorten shared instructions and batch independent reads. Extend developer evals to check actual outcomes and final review evidence, with tools for comparing recorded runs.

**Upgrade:** update shared guards, gates, policies, skills, CLI and tests together; preserve project settings and records. Old review receipts need to be recorded again by an independent reviewer. Register trusted upstream refs or use matching approval for control changes. No mode or record migration is needed.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** ผล smoke test ก่อนออก release ที่บันทึกไว้ใช้ **103k tokens ต่อรอบ** คิดเป็นประมาณ **24% น้อยกว่า 4.1.0** (136k) และ **29% น้อยกว่า 4.3.0** (145k) จาก 16 รอบ ผลรายงานนี้ยังแยกผลของ template ออกจาก settings เฉพาะโปรเจกต์ไม่ได้ ส่วนการทดลองเฉพาะ guard เป็นอีกชุดหนึ่ง และใช้ token รวม **0.8% มากกว่า 4.3.0**

- ล้างคิวเก่าด้วย `old --days N` ได้ การตรวจ path ยอมให้มี dependency links ที่ไม่เกี่ยวข้อง พร้อมปกป้อง state ของ workflow และเพิ่ม `model_drift.py` สำหรับตรวจ catalog ของ Codex ในเครื่องโดยไม่ใช้เครือข่ายหรือเขียนไฟล์
- receipt ยังใช้ได้หลัง stage และ commit เนื้อหาที่รีวิวครบแล้ว การ commit เพียงบางส่วนหรือเนื้อหาที่ต่างออกไปทำให้ receipt ใช้ไม่ได้ การอัปเดต tracker ตามปกติแยกออกจาก fingerprint แต่ยังผ่านการตรวจของ workflow CLI
- ลดจังหวะสะดุดจาก contract และ Stop: รองรับการ declare ก่อนคำสั่งแรกที่เขียนไฟล์ เปิดทางให้คำสั่งอ่านที่ปลอดภัยมากขึ้น และปล่อยการปฏิเสธซ้ำเดิมเป็น `UNVERIFIED` เพื่อรายงาน `BLOCKED` ได้
- รับรู้ controls ที่ตรงกับ upstream refs ที่ผ่านรีวิว เพิ่ม `workflow.py context` และการ archive tracker ที่เสร็จแล้วอย่างมีเงื่อนไขป้องกัน
- ย่อคำสั่งที่ใช้ร่วมกัน รวมการอ่านที่ทำแยกกันได้ และเพิ่มเครื่องมือ eval สำหรับตรวจผลจริง หลักฐานรีวิวสุดท้าย และเปรียบเทียบผลการรันที่บันทึกไว้

**เมื่ออัปเกรด:** อัปเดต guards, gates, policies, skills, CLI และ tests พร้อมกัน เก็บ settings และ records ของโปรเจกต์ไว้ receipt เก่าต้องให้ independent reviewer บันทึกใหม่ ตั้ง trusted upstream refs หรือใช้การอนุมัติที่ตรงกับการเปลี่ยน controls ไม่ต้องย้ายโหมดหรือข้อมูลบันทึกงาน

</details>

## 4.4.0 — 2026-10-17

**Token highlight:** about **15% more than 4.1.0** in the recorded Sonnet smoke test on the same four tasks. That comparison showed increased usage, not a saving.

- Enforce a Task Contract before writes in both Claude and Codex. A new user prompt clears it; read-only inspection stays available. Contracts also support a field-block format.
- Only the independent reviewer records its receipt. Codex reviewers start with a fresh context. An unchanged state already covered by a HIGH-depth PASS can satisfy the high-risk floor on later status turns; a new HIGH contract still needs its own receipt.
- Make Claude's headless Stop refusals reach the agent correctly, require a contract for changed work in Codex, and fix the direct gate runner on macOS Bash 3.2.
- Protect review receipts from direct edits and add a repair path for a broken contract guard. Reports must match changes that actually happened.
- Add opt-in behavior evals for both providers and a faster parallel Python test runner. Paid evals require explicit model and budget limits; CI uses local grader tests and dry runs.

**Upgrade:** update both providers' hook settings/adapters and shared guard/evidence/gate tooling together. Re-trust Codex hooks after the update and record matching approval for control changes. Merge local entrypoint changes, including the fresh-reviewer instruction.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** บันทึก Sonnet smoke test ที่ใช้งานสี่ข้อชุดเดียวกันพบว่าใช้ประมาณ **15% มากกว่า 4.1.0** ผลเปรียบเทียบนี้ใช้ token เพิ่มขึ้น

- บังคับให้มี Task Contract ก่อนเขียนทั้ง Claude และ Codex ข้อความใหม่จากผู้ใช้จะล้าง contract เดิม แต่ยังอ่านตรวจข้อมูลได้ และเขียน contract แบบแบ่ง fields ได้ด้วย
- ให้ independent reviewer เป็นผู้บันทึก receipt เท่านั้น reviewer ของ Codex ต้องเริ่มด้วย context ใหม่ หากเนื้อหาเดิมมี HIGH-depth PASS ครอบคลุมแล้ว ใช้รองรับการตอบสถานะภายหลังได้ แต่ contract HIGH ใหม่ยังต้องมี receipt ของตัวเอง
- แก้การส่งผลปฏิเสธจาก Stop ใน Claude แบบ headless บังคับ contract สำหรับงานที่เปลี่ยนใน Codex และแก้ gate runner เมื่อเรียกตรงบน macOS Bash 3.2
- ป้องกันการแก้ receipt โดยตรง เปิดทางซ่อม contract guard ที่เสีย และกำหนดให้รายงานตรงกับสิ่งที่เปลี่ยนจริง
- เพิ่ม behavior evals ของทั้งสอง providers และตัวรัน Python tests แบบขนาน การรัน eval ที่เสียเงินต้องระบุโมเดลกับเพดานงบ ส่วน CI ใช้ grader tests และ dry run ในเครื่อง

**เมื่ออัปเกรด:** อัปเดต hook settings/adapters ของทั้งสอง providers พร้อม guard, evidence และ gate tooling ต้อง trust Codex hooks ใหม่และบันทึกการอนุมัติที่ตรงกับการเปลี่ยน controls รวมคำสั่ง reviewer ที่ต้องเริ่ม context ใหม่เข้ากับ entrypoint ที่ปรับเอง

</details>

## 4.3.1 — 2026-10-16

Fix installed-template smoke tests in projects with custom provider skills. Project-owned skills are preserved and no longer counted as bundled Lean skills.

**Upgrade:** take the updated `test_template.py` if you carry a local workaround. Workflow behavior and records are unchanged.

<details>
<summary>ภาษาไทย</summary>

แก้ smoke tests ของ template ที่ติดตั้งในโปรเจกต์ซึ่งมี provider skills ของตัวเอง โดยเก็บ skills เหล่านั้นไว้ และไม่นับรวมเป็น Lean skills ที่มากับชุดติดตั้ง

**เมื่ออัปเกรด:** ใช้ `test_template.py` รุ่นใหม่แทน workaround ที่ทำไว้ได้ พฤติกรรม workflow และข้อมูลบันทึกงานไม่เปลี่ยน

</details>

## 4.3.0 — 2026-10-15

**Token highlight:** about **7% more than 4.1.0**, calculated from the rounded baseline averages in later smoke-test notes: 145k versus 136k tokens per run. This is a historical baseline comparison, not a dedicated 4.3.0 benchmark.

- Pass an appropriately sized model and effort on each subagent spawn that supports them, including reviewers. Inheriting session settings needs a recorded reason.
- Keep optional work in the current session when a new worker would cost more. Required delegation and independent review still apply.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** คำนวณจากค่าเฉลี่ย baseline แบบปัดเศษในบันทึก smoke test ภายหลัง ใช้ประมาณ **7% มากกว่า 4.1.0** หรือ 145k เทียบกับ 136k tokens ต่อรอบ เป็นการเทียบ baseline ย้อนหลัง ไม่ใช่ benchmark เฉพาะรุ่น 4.3.0

- ระบุโมเดลและ effort ที่เหมาะกับงานทุกครั้งที่ spawn subagent แล้ว runtime รองรับ รวมถึง reviewer หากใช้ค่าจาก session ต้องบันทึกเหตุผล
- งานที่ไม่จำเป็นต้องแยก ให้ทำใน session เดิมเมื่อการเปิด worker ใหม่แพงกว่า กติกา delegation และ independent review ที่จำเป็นยังคงเดิม

</details>

## 4.2.0 — 2026-10-14

**Token highlight:** - · **Compared with:** -

- Keep nine core skills visible by default and ten optional skills available through `skill_pack.py`. Add project standards, bounded audits, procedure intensity settings and pinned workflow updates.
- Share auto/manual gate settings across Claude and Codex. Codex's lifecycle adapter needs runtime trust; manual mode reports `NOT_RUN` and does not waive validation or review.
- Serialize gates per checkout. Rerun checks by default, allow explicit tree caching, and keep failed or undefined validation from becoming a pass. A released Stop remains `UNVERIFIED`.
- Bind HIGH-review receipts to the exact contract and shipping state. Protect gate controls and check high-risk paths even after their changes have been committed.
- Support economical reviewers for wording-only HIGH reviews when a checked rule map proves the meaning stayed the same. Use smaller document reads when dependencies are bounded, and prevent reuse of archived tracker IDs.

**Upgrade:** take the shared skills, registry/discovery links, policies, gate/evidence/lock helpers, both provider adapters and tests together. Preserve mode, execution, optional-pack choices and project preferences, including `.lean/skill-effort.json` and `.codex/quality-gate.json`. Configure real project checks if the old gate was empty. Review control changes and record matching approval; old caches are not validation evidence.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

- เปิดเก้า core skills ตามค่าเริ่มต้น และเปิดอีกสิบ optional skills ผ่าน `skill_pack.py` ได้ เพิ่มมาตรฐานโปรเจกต์ การ audit แบบมีขอบเขต การตั้งระดับความละเอียดของ procedure และการอัปเดต workflow โดยตรึงรุ่น
- ใช้ settings ของ gate แบบ auto/manual ร่วมกันใน Claude และ Codex โดย lifecycle adapter ของ Codex ต้องผ่าน runtime trust ส่วน manual แสดง `NOT_RUN` และยังต้องตรวจ validation กับ review ให้ครบ
- ให้ gate ทำงานทีละชุดต่อ checkout รัน checks ใหม่เป็นค่าเริ่มต้น เปิด tree cache ได้อย่างชัดเจน และไม่เปลี่ยนผลที่ล้มเหลวหรือยังไม่มีการตรวจให้เป็นผ่าน Stop ที่ถูกปล่อยยังเป็น `UNVERIFIED`
- ผูก HIGH-review receipt กับ contract และเนื้อหาที่ส่งจริง ปกป้อง gate controls และตรวจ high-risk paths แม้ commit การเปลี่ยนแปลงไปแล้ว
- ใช้ reviewer ที่ประหยัดกว่าสำหรับ HIGH review ที่แก้ถ้อยคำล้วนได้ เมื่อ rule map ที่ตรวจแล้วแสดงว่าความหมายเดิมครบ อ่านเอกสารเฉพาะส่วนเมื่อจำกัด dependencies ได้ และป้องกันการใช้ tracker ID ที่ archive แล้วซ้ำ

**เมื่ออัปเกรด:** อัปเดต shared skills, registry/discovery links, policies, gate/evidence/lock helpers, adapters ของทั้งสอง providers และ tests พร้อมกัน เก็บโหมด execution การเลือก optional pack และ preferences ของโปรเจกต์ไว้ รวมถึง `.lean/skill-effort.json` และ `.codex/quality-gate.json` หาก gate เดิมว่าง ต้องใส่ checks จริง ตรวจการเปลี่ยน controls และบันทึกอนุมัติที่ตรงกัน cache เก่าไม่ใช่หลักฐาน validation

</details>

## 4.1.1 — 2026-10-14

Rewrite the README, contribution guide and public guides in plain English. Clarify setup, modes, delegation and runtime limits without changing the workflow requirements.

**Upgrade:** update the guides and baseline references together, preserving project facts and preferences. No configuration or record migration is needed.

<details>
<summary>ภาษาไทย</summary>

ปรับ README คู่มือ contribution และคู่มือสาธารณะให้อ่านง่ายขึ้น อธิบาย setup โหมด delegation และข้อจำกัดของ runtime ให้ชัด โดยไม่เปลี่ยนข้อกำหนดของ workflow

**เมื่ออัปเกรด:** อัปเดตคู่มือและเลข baseline พร้อมกัน เก็บข้อมูลและ preferences ของโปรเจกต์ไว้ ไม่ต้องย้าย configuration หรือข้อมูลบันทึกงาน

</details>

## 4.1.0

**Token highlight:** - · **Compared with:** -

Add `/lean-clean-repo` to preview repository cleanup before making changes. Approved cleanup uses external snapshots and a recovery journal; it preserves uncertain files, existing work, credentials and records. Nothing is cleaned automatically, and applied changes still need validation and review.

**Upgrade:** take the skill, helper, registry, discovery links and tests together. Keep cleanup sessions outside the repository and stop other writers during apply or restore.

<details>
<summary>ภาษาไทย</summary>

**ผลด้าน token:** - · **เทียบกับรุ่น:** -

เพิ่ม `/lean-clean-repo` สำหรับเสนอรายการเก็บกวาด repository ก่อนลงมือ เมื่ออนุมัติแล้วจึงใช้ snapshot ภายนอกกับ journal สำหรับกู้คืน โดยเก็บไฟล์ที่ยังไม่แน่ใจ งานเดิม credentials และ records ไว้ ไม่มีการล้างอัตโนมัติ และงานที่ apply แล้วยังต้องผ่าน validation กับ review

**เมื่ออัปเกรด:** อัปเดต skill, helper, registry, discovery links และ tests พร้อมกัน เก็บ cleanup sessions ไว้นอก repository และหยุดตัวเขียนไฟล์อื่นระหว่าง apply หรือ restore

</details>

## 4.0.0

Claude and Codex now use one shared copy of the workflow.

- Skills live in `.lean/skills/`; each runtime discovers them through relative symlinks.
- Reviewer instructions live in `.lean/roles/reviewer.md`, and both providers use the shared gate runner.
- Rename `/clean-queue` to `/lean-clean-queue`. The underlying CLI command stays the same.

**Upgrade from 3.x:** move local skill customizations into the shared source before replacing runtime copies with links. Update skills, roles, runner, tooling, registry and both discovery trees together. Preserve unrelated skills and project data. Copy symlinks without dereferencing them, then reload runtime skills when needed. Legacy provider-skill distributions need a schema-2 registry before takeover planning.

<details>
<summary>ภาษาไทย</summary>

Claude และ Codex ใช้ workflow จาก source ชุดเดียวกันแล้ว

- skills อยู่ใน `.lean/skills/` และแต่ละ runtime ค้นพบผ่าน relative symlinks
- คำสั่ง reviewer อยู่ใน `.lean/roles/reviewer.md` และทั้งสอง providers ใช้ gate runner ร่วมกัน
- เปลี่ยนชื่อ `/clean-queue` เป็น `/lean-clean-queue` ส่วนคำสั่ง CLI ภายในยังเดิม

**อัปเกรดจาก 3.x:** รวมการปรับ skills ของโปรเจกต์เข้ากับ shared source ก่อนแทนสำเนาใน runtime ด้วย links อัปเดต skills, roles, runner, tooling, registry และ discovery trees ของทั้งสองฝั่งพร้อมกัน เก็บ skills อื่นกับข้อมูลโปรเจกต์ไว้ คัดลอก symlinks โดยรักษาตัว links แล้ว reload skills ตามที่จำเป็น ชุดติดตั้งเก่าที่มี provider skills ต้องใช้ schema-2 registry ก่อนวางแผน takeover

</details>

## 3.5.0

Add `/lean-use-submodule <remote url>` to keep application code in `targets/<name>` while Lean and its project records stay outside the application repository. Workflow and catalog commands select active target records by default; application checks run in the target.

**Upgrade:** update procedures/adapters, tooling, hooks, tests and the registry together. Give Lean's own workflow/catalog gate checks an explicit `--root .`. Preserve target registrations and records. The command does not remove workflow files already tracked inside an application.

<details>
<summary>ภาษาไทย</summary>

เพิ่ม `/lean-use-submodule <remote url>` เพื่อเก็บ application code ใน `targets/<name>` และเก็บ Lean กับ project records ไว้นอก application repository คำสั่ง workflow และ catalog เลือก records ของ target ที่ใช้อยู่เป็นค่าเริ่มต้น ส่วน checks ของ application รันใน target

**เมื่ออัปเกรด:** อัปเดต procedures/adapters, tooling, hooks, tests และ registry พร้อมกัน ใส่ `--root .` ให้ workflow/catalog checks ของ Lean เอง เก็บ target registrations และ records ไว้ คำสั่งนี้ไม่ลบ workflow files ที่เคยติดตามใน application อยู่แล้ว

</details>

## 3.4.0

Add `/lean-takeover-workflow` for moving an existing project's workflow into Lean. It audits the current setup, resolves migration decisions, previews a plan, and uses external snapshots for apply, resume and rollback. It also supports explicitly approved `casetodian-v1` queue/tracker conversions without losing original records.

**Upgrade:** update portable assets, registry, tooling, tests and adapters together. Preserve project additions, checks, configuration, records, custom skills and permissions. Takeover runs only when requested; applied migrations still need the target gate and an independent HIGH review.

<details>
<summary>ภาษาไทย</summary>

เพิ่ม `/lean-takeover-workflow` สำหรับย้าย workflow ของโปรเจกต์เดิมมาใช้ Lean โดยตรวจ setup เดิม สรุปเรื่องที่ต้องตัดสินใจ เสนอแผน และใช้ snapshots ภายนอกสำหรับ apply, resume และ rollback รองรับการแปลงคิวกับ tracker แบบ `casetodian-v1` ที่อนุมัติชัดเจน โดยเก็บ records ต้นฉบับไว้

**เมื่ออัปเกรด:** อัปเดต portable assets, registry, tooling, tests และ adapters พร้อมกัน เก็บ project additions, checks, configuration, records, custom skills และ permissions ไว้ takeover ทำเมื่อร้องขอเท่านั้น และหลัง apply ยังต้องผ่าน gate ของ target กับ independent HIGH review

</details>

## 3.3.0

Tighten existing checks so invalid records and unsafe paths cannot slip through.

- DONE trackers must have no open acceptance or task checkboxes, including those under subheadings.
- Reject multiline tracker titles/evidence and ambiguous agent IDs.
- Refuse symlinked workflow-state paths and detect changes in untracked files when checking gate caches.

**Upgrade:** review open checkboxes in DONE trackers and check workflow-state paths before running the stricter checks.

<details>
<summary>ภาษาไทย</summary>

เพิ่มความเข้มงวดให้ checks เดิม เพื่อไม่ให้ records ที่ไม่ถูกต้องหรือ paths ที่ไม่ปลอดภัยหลุดผ่าน

- tracker ที่เป็น DONE ต้องไม่มี acceptance หรือ task checkboxes ค้างอยู่ รวมถึงหัวข้อย่อย
- ไม่รับชื่อ tracker หรือ evidence หลายบรรทัด และ agent IDs ที่กำกวม
- ไม่ยอมเขียนผ่าน workflow-state paths ที่เป็น symlinks และตรวจการเปลี่ยนไฟล์ untracked ก่อนใช้ gate cache

**เมื่ออัปเกรด:** ตรวจ checkboxes ที่ยังเปิดใน DONE trackers และ paths ของ workflow state ก่อนรัน checks ที่เข้มงวดขึ้น

</details>

## 3.2.0

- Add user entrypoints for setup, tasks, model research, prose compression and queue cleanup, with shared Claude/Codex procedures.
- `/lean-compress` previews wording changes within an approved scope. `/lean-model-update codex|claude|all` previews project catalog updates; neither silently changes runtime settings or authorizes paid use.
- `/clean-queue old` archives DONE items older than 30 days; `all` archives every DONE item. Unfinished items and trackers stay in place, and archived dependencies remain valid.

**Upgrade:** update cleanup tooling and procedures before archiving so all workers can resolve history. Stop old workers and retain history in version control. Undated DONE items are skipped by `old` and can be archived by `all`. The command was renamed in 4.0.0.

<details>
<summary>ภาษาไทย</summary>

- เพิ่มคำสั่งสำหรับ setup งาน การค้นข้อมูลโมเดล การย่อข้อความ และการล้างคิว โดยใช้ procedures ร่วมกันใน Claude/Codex
- `/lean-compress` เสนอการแก้ถ้อยคำในขอบเขตที่อนุมัติ ส่วน `/lean-model-update codex|claude|all` เสนอการอัปเดต catalog ของโปรเจกต์ ทั้งสองไม่เปลี่ยน runtime settings หรืออนุมัติค่าใช้จ่ายเอง
- `/clean-queue old` เก็บ DONE items ที่เก่ากว่า 30 วันเข้าประวัติ ส่วน `all` เก็บ DONE items ทั้งหมด งานที่ยังไม่เสร็จและ trackers ยังคงอยู่ และ dependencies ที่อ้างประวัติยังใช้ได้

**เมื่ออัปเกรด:** อัปเดต cleanup tooling และ procedures ก่อน archive เพื่อให้ workers ทุกตัวอ่าน history ได้ หยุด workers รุ่นเก่าและเก็บ history ใน version control DONE items ที่ไม่มีวันที่จะถูกข้ามโดย `old` แต่ archive ด้วย `all` ได้ คำสั่งนี้เปลี่ยนชื่อในรุ่น 4.0.0

</details>

## 3.1.0

Add explicit mode downgrades without deleting work records. Preview with `downgrade <mode> --dry-run`; use `--apply` after resolving blockers.

- Active claims block every downgrade. Active trackers block a move to `standard`.
- `--keep-pending` explicitly acknowledges paused unfinished work. Existing records, IDs, evidence and execution settings stay intact.
- Configure no longer permits an implicit downgrade; upgrades validate retained records too.

<details>
<summary>ภาษาไทย</summary>

เพิ่มการลดระดับโหมดอย่างชัดเจนโดยไม่ลบบันทึกงาน ดูแผนด้วย `downgrade <mode> --dry-run` และใช้ `--apply` หลังจัดการสิ่งที่บล็อกแล้ว

- claims ที่ยังใช้งานบล็อกการลดทุกโหมด และ trackers ที่กำลังทำบล็อกการย้ายไป `standard`
- `--keep-pending` ใช้ยืนยันการพักงานที่ยังไม่เสร็จ โดยคง records, IDs, evidence และ execution settings ไว้
- configure ไม่ยอมลดโหมดโดยปริยายแล้ว และการอัปเกรดตรวจ records ที่เก็บไว้ด้วย

</details>

## 3.0.0

Make Lean a shared Claude/Codex workflow with project-controlled ownership.

- `AGENTS.md` becomes the canonical contract; `CLAUDE.md` imports it. Shared procedures cover scope, research, planning, delegation, review and gates.
- Separate `standard` / `tracker` / `full` record keeping from `direct` / `delegated` execution. New templates start unconfigured in `standard` / `direct`.
- Choose the least costly capable model and effort for each task, replacing the earlier strongest-reviewer rule. Required HIGH independent review remains mandatory; report `BLOCKED` if unavailable.
- Preserve project records and licenses, reject duplicate tracker IDs, accept FAILED trackers, and recheck dependencies before completing queue work.
- Support macOS, Linux and WSL with Bash, Git and Python 3.9+. Native Windows is unsupported.

### Migrating from 2.x or local extensions

Preserve entrypoint additions, PROJECT, config, permissions, records and local extensions before replacement. Move shared rules from CLAUDE into AGENTS, then make CLAUDE import it while keeping runtime-specific additions. Reconcile customized files instead of overwriting them.

Keep existing modes and work records. Missing execution settings default to `direct`; select `delegated` explicitly where required. Update shared procedures/adapters, policy, hooks, tooling, templates, tests and workflow CI together. Retain `.lean/LICENSE`, merge settings/gitignore and run the actual project's checks and required review.

<details>
<summary>ภาษาไทย</summary>

ปรับ Lean ให้เป็น workflow ร่วมของ Claude/Codex และให้โปรเจกต์กำหนดผู้รับผิดชอบเอง

- ใช้ `AGENTS.md` เป็น contract หลัก และให้ `CLAUDE.md` import รองรับ scope, research, planning, delegation, review และ gates ผ่าน procedures ร่วมกัน
- แยกการเก็บบันทึกแบบ `standard` / `tracker` / `full` ออกจาก execution แบบ `direct` / `delegated` โดย template ใหม่เริ่มแบบยังไม่ตั้งค่าใน `standard` / `direct`
- เลือกโมเดลและ effort ที่ประหยัดที่สุดแต่ทำงานได้ตามคุณภาพ แทนกติกาเดิมที่ใช้ reviewer เก่งที่สุดเสมอ HIGH independent review ที่จำเป็นยังข้ามไม่ได้ หากใช้ไม่ได้ให้รายงาน `BLOCKED`
- เก็บ records และ licenses ของโปรเจกต์ ปฏิเสธ tracker ID ซ้ำ รองรับ FAILED trackers และตรวจ dependencies ใหม่ก่อนจบงานคิว
- รองรับ macOS, Linux และ WSL ด้วย Bash, Git และ Python 3.9+ ไม่รองรับ native Windows

**ย้ายจาก 2.x หรือ workflow ที่ปรับเอง:** เก็บ entrypoint additions, PROJECT, config, permissions, records และ local extensions ก่อนแทนไฟล์ ย้าย shared rules จาก CLAUDE เข้า AGENTS แล้วให้ CLAUDE import โดยเก็บส่วนเฉพาะ runtime ไว้ รวมไฟล์ที่ปรับเองอย่างระมัดระวัง

เก็บโหมดกับบันทึกงานเดิม หากไม่มี execution setting จะใช้ `direct` โปรเจกต์ที่ต้อง delegate ต้องเลือก `delegated` ชัดเจน อัปเดต procedures/adapters, policy, hooks, tooling, templates, tests และ workflow CI พร้อมกัน เก็บ `.lean/LICENSE` รวม settings/gitignore และรัน checks จริงกับ review ที่จำเป็นของโปรเจกต์

</details>

## 2.4.0

The gate distinguishes a missing tool from a check that ran and failed. Both block completion, but the message now tells you whether to fix the environment or investigate a failure.

Gate commands must still propagate their own failures. A command that masks an error can appear successful to the runner.

<details>
<summary>ภาษาไทย</summary>

gate แยกได้ว่าเครื่องมือที่ต้องใช้หายไป หรือ check รันแล้วไม่ผ่าน ทั้งสองกรณียังบล็อกการจบงาน แต่ข้อความช่วยให้รู้ว่าควรแก้ environment หรือตรวจสาเหตุที่ check ล้มเหลว

คำสั่งใน gate ยังต้องส่งสถานะล้มเหลวออกมาเอง หากคำสั่งกลบ error ไว้ runner อาจเห็นว่าเป็นการรันสำเร็จ

</details>

## 2.3.0

Make the existing reviewer-model rule apply at dispatch instead of silently inheriting the session model. At this release, HIGH review explicitly requested the strongest available model and disclosed when the reviewer ran on a weaker one. Version 3.0.0 later replaced this with capability-based model selection.

<details>
<summary>ภาษาไทย</summary>

ทำให้กติกาเลือกโมเดล reviewer มีผลตอนส่งงานจริง แทนการใช้โมเดลจาก session โดยเงียบ ๆ ในรุ่นนี้ HIGH review ระบุโมเดลที่เก่งที่สุดที่ใช้ได้อย่างชัดเจน และรายงานเมื่อ reviewer ใช้โมเดลที่อ่อนกว่า ต่อมาใน 3.0.0 เปลี่ยนเป็นการเลือกตามความสามารถที่งานต้องใช้

</details>

## 2.2.0

Bound review cycles so repeated fixes cannot extend one task indefinitely.

- One cycle covers one Task Contract and its review-driven fixes.
- After the second `REWORK`, allow one final repair/review pass. Unresolved findings end as `BLOCKED`.
- `PASS` ends the cycle. Later changes need their own contract, and review must cover the actual shipping changes.

<details>
<summary>ภาษาไทย</summary>

จำกัดรอบรีวิว เพื่อไม่ให้การแก้ซ้ำยืดงานเดิมออกไปไม่สิ้นสุด

- หนึ่งรอบกระบวนการครอบคลุมหนึ่ง Task Contract กับการแก้ตามผลรีวิวของงานนั้น
- หลัง `REWORK` ครั้งที่สอง ให้แก้และรีวิวอีกได้หนึ่งรอบ หากยังมีประเด็นค้างให้จบด้วย `BLOCKED`
- `PASS` จบรอบนั้น การเปลี่ยนภายหลังต้องมี contract ของตัวเอง และผลรีวิวต้องครอบคลุมเนื้อหาที่ส่งจริง

</details>

## 2.1.0

Run the Quality Gate after committed changes too; a clean working tree alone no longer skips validation. SessionStart records a baseline, while failed checks remain refused across turns and sessions until resolved.

**Upgrade:** resolve existing failing project checks. The corrected gate may now block work that earlier versions skipped.

<details>
<summary>ภาษาไทย</summary>

gate ตรวจงานที่ commit แล้วด้วย การที่ working tree สะอาดเพียงอย่างเดียวไม่ทำให้ข้าม validation อีกต่อไป SessionStart บันทึก baseline ส่วน checks ที่ล้มเหลวยังคงถูกปฏิเสธข้าม turn และ session จนกว่าจะแก้แล้ว

**เมื่ออัปเกรด:** จัดการ project checks ที่ล้มเหลวอยู่ก่อน gate ที่แก้แล้วอาจบล็อกงานซึ่งรุ่นก่อนเคยข้ามการตรวจ

</details>

## 2.0.0

Move the workflow into its own namespace: `.agent/` becomes `.lean/`, and self-check scripts move from `.github/lean-workflow/` into `.lean/scripts/` and `.lean/tests/`. Project-owned `scripts/`, `tests/`, `docs/` and root `CHANGELOG.md` stay separate.

### Migrating from 1.x

1. Move `.agent` to `.lean` **before** copying the new release. Moving it after `.lean` exists can create an unwanted `.lean/.agent/` directory.
2. Move the structure script into `.lean/scripts/` and hook tests into `.lean/tests/`. Take the release's workflow-owned files together; compare local customizations before replacement.
3. Update project-owned references, including PROJECT's gate commands, README, hook/script paths and CI filters. Merge runtime settings rather than replacing permissions.
4. Check for leftover old paths and nested directories, then run structure checks and hook tests.

<details>
<summary>ภาษาไทย</summary>

ย้าย workflow เข้าสู่ namespace ของตัวเอง: `.agent/` เปลี่ยนเป็น `.lean/` และย้าย self-check scripts จาก `.github/lean-workflow/` เข้า `.lean/scripts/` กับ `.lean/tests/` ส่วน `scripts/`, `tests/`, `docs/` และ root `CHANGELOG.md` ของโปรเจกต์ยังแยกกัน

**ย้ายจาก 1.x:**

1. ย้าย `.agent` เป็น `.lean` **ก่อน** คัดลอกรุ่นใหม่ หากมี `.lean` อยู่ก่อน อาจกลายเป็นโฟลเดอร์ซ้อน `.lean/.agent/`
2. ย้าย structure script เข้า `.lean/scripts/` และ hook tests เข้า `.lean/tests/` ใช้ workflow-owned files ของรุ่นใหม่พร้อมกัน โดยเทียบส่วนที่ปรับเองก่อนแทนไฟล์
3. แก้ references ของโปรเจกต์ ทั้ง gate commands ใน PROJECT, README, hook/script paths และ CI filters รวม runtime settings โดยเก็บ permissions เดิม
4. ตรวจว่าไม่เหลือ paths เก่าหรือโฟลเดอร์ซ้อน แล้วรัน structure checks และ hook tests

</details>

## 1.4.0

- Require a one-line Task Contract before edits and regression tests that fail before a bug fix and pass afterward.
- Load workflow internals only when needed and keep the main task procedure shorter.
- Fix only gate failures caused by the task; report unrelated failures as `BLOCKED`. Gate commands must return a failure status when they fail.

<details>
<summary>ภาษาไทย</summary>

- กำหนด Task Contract หนึ่งบรรทัดก่อนแก้ไฟล์ และมี regression test ที่ล้มเหลวก่อนแก้ bug แล้วผ่านหลังแก้
- อ่าน workflow internals เท่าที่งานต้องใช้ และย่อ procedure หลักให้สั้นลง
- แก้เฉพาะ gate failures ที่เกิดจากงานนี้ ส่วนที่ไม่เกี่ยวข้องให้รายงาน `BLOCKED` คำสั่งใน gate ต้องคืนสถานะล้มเหลวเมื่อรันไม่ผ่าน

</details>

## 1.3.0

Add workflow self-checks and CI: verify referenced paths, hook behavior, settings, executable scripts and skill metadata alongside ShellCheck.

<details>
<summary>ภาษาไทย</summary>

เพิ่ม self-checks และ CI ของ workflow เพื่อตรวจ paths ที่อ้างถึง พฤติกรรม hooks, settings, สิทธิ์เรียก scripts และข้อมูลกำกับ skills ควบคู่กับ ShellCheck

</details>

## 1.2.0

Move shared policies into `.agent/policy/` so they can be upgraded together while preserving the project-owned `.agent/PROJECT.md`.

<details>
<summary>ภาษาไทย</summary>

ย้าย shared policies เข้า `.agent/policy/` เพื่ออัปเดตพร้อมกันได้ โดยเก็บ `.agent/PROJECT.md` ซึ่งเป็นข้อมูลของโปรเจกต์ไว้

</details>

## 1.1.0

Add Claude-native skills, an independent HIGH reviewer and onboarding hooks under `.claude/`, sharing the existing workflow rules. Default permissions allow read-only Git commands and deny reading `.env` files.

<details>
<summary>ภาษาไทย</summary>

เพิ่ม skills สำหรับ Claude, independent HIGH reviewer และ onboarding hooks ใน `.claude/` โดยใช้กติกา workflow เดิมร่วมกัน permissions เริ่มต้นอนุญาต Git แบบอ่านอย่างเดียว และไม่ให้อ่านไฟล์ `.env`

</details>

## 1.0.0

First baseline: Task Contracts, project-defined Quality Gates, risk-based tests and review, and context loaded as needed. `CLAUDE.md` is the canonical contract; `AGENTS.md` adapts it for other agents.

<details>
<summary>ภาษาไทย</summary>

baseline แรก: มี Task Contracts, Quality Gates ตาม checks ของโปรเจกต์ การทดสอบและรีวิวตามความเสี่ยง และการอ่าน context เท่าที่จำเป็น โดยใช้ `CLAUDE.md` เป็น contract หลัก และ `AGENTS.md` เป็นตัวปรับให้ agents อื่น

</details>

## Upgrading

Read migration notes for every major version you cross, then follow [CUSTOMIZING.md](CUSTOMIZING.md) for the current process.

1. Preserve project facts, checks, configuration, records, local extensions and entrypoint additions.
2. Update the workflow's shared files, skills, adapters, hooks, tooling, templates and tests together.
3. Merge settings, gitignore and CI while keeping project permissions, application checks and licenses, including `.lean/LICENSE`.
4. Reconcile ownership and overrides explicitly. Keep existing mode, execution and primary-agent choices unless you decide to change them.
5. Run the actual project gate and installed workflow tests, then complete the required review over the final changes.

<details>
<summary>ภาษาไทย — การอัปเกรด</summary>

อ่าน migration notes ของทุกรุ่น major ที่ต้องข้าม แล้วทำตาม [CUSTOMIZING.md](CUSTOMIZING.md) สำหรับขั้นตอนปัจจุบัน

1. เก็บข้อมูลโปรเจกต์ checks, configuration, records, local extensions และ entrypoint additions ไว้
2. อัปเดต shared files, skills, adapters, hooks, tooling, templates และ tests ของ workflow พร้อมกัน
3. รวม settings, gitignore และ CI โดยคง permissions, application checks และ licenses ของโปรเจกต์ รวมถึง `.lean/LICENSE`
4. สรุป ownership และ overrides ให้ชัด เก็บโหมด execution และ primary agent เดิม เว้นแต่จะตัดสินใจเปลี่ยน
5. รัน gate จริงของโปรเจกต์กับ workflow tests ที่ติดตั้งไว้ แล้วทำ review ที่จำเป็นให้ครอบคลุมการเปลี่ยนแปลงสุดท้าย

</details>
