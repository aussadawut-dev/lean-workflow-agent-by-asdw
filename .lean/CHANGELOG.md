# Changelog

Versions follow `MAJOR.MINOR.PATCH`: MAJOR changes existing workflow rules or required paths, MINOR adds rules, files or enforcement, and PATCH clarifies wording.

Older entries describe the workflow at the time. For current installation and upgrade instructions, see [CUSTOMIZING.md](CUSTOMIZING.md).

Token highlights come from the [historical smoke-test notes](https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw/blob/v4.8.0/.lean/CHANGELOG.md#450--2026-10-18) and [TCK303 replay notes](https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw/blob/v4.8.0/.lean/CHANGELOG.md#480--2026-10-19). Approximate percentages are calculated from the reported totals, not new benchmarks. Compare results within the same workload; they are not guaranteed savings. The original smoke-test runs were not retained. `-` means no version comparison was recorded.

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
