# Lean Workflow 5.5.0 — ผลจากการใช้งานจริงใน asdw-harness (dogfood report)

- วันที่รวบรวม: 2026-10-31
- รีโปที่ใช้งาน: asdw-harness, สาขา `feat/improve-ui`, HEAD `8d7c5cb`
- Lean ที่ติดตั้ง: `refs/tags/v5.5.0`, commit `dde70f6cb0de66c1a1bba5d65018e12398d59410`
- โหมด: `tracker` / `direct`, gate `manual_fixloop`
- Provider ที่ใช้ร่วมใน checkout เดียว: Claude Code และ Codex (agy ไม่มี hook)
- แหล่งหลักฐาน: `.agent-runtime/activity.jsonl` ของวันที่ 2026-10-30 (phase 79, contract 22, review 15, test 5, gate 2 เหตุการณ์), trackers `docs/tracking/TCK020`–`TCK041`, `git log`, การยิง payload สังเคราะห์เข้า `lean hook claude pre-tool|stop|session-start`
- ขอบเขต: รายการนี้คือสิ่งที่ควรแก้ที่ Lean upstream เท่านั้น การตั้งค่าของโปรเจกต์ asdw-harness อยู่ในภาคผนวก B และจะปรับที่รีโปนั้นหลังอัปเดต Lean รอบถัดไป
- สถานะ upstream ตอนตรวจซ้ำ: `develop` = `bca42e1` (5.6.0) ทุกข้อมีบรรทัด "สถานะที่ bca42e1" บอกว่ายังพบในโค้ดปัจจุบันหรือไม่ (ตรวจด้วย grep ตามบรรทัดที่อ้าง ไม่ได้รัน test ใน upstream)

สิ่งที่ตรวจแล้วทำงานถูกต้อง (ไม่ต้องแก้): `lean lint`, `mode check`, `models check`, `attribution` ผ่านทั้งหมด; hook `pre-tool` ใช้เวลา 37–40 ms ต่อครั้ง, `session-start` 0.28 s, `stop` ในโหมด manual 0.05 s; การผูก contract จาก transcript ทำงานได้เมื่อ tool call แรกของเทิร์นเป็นการอ่าน (session ที่เขียนรายงานนี้ผูกได้ที่ 2026-10-30T16:30:26Z, `source: transcript`)

---

## รายการที่ควรแก้ เรียงตามผลกระทบ

### 1. Contract lifecycle: cleared on every prompt, and the transcript read races the first write

**ปัญหา** contract ถูกล้างทุกครั้งที่ผู้ใช้พิมพ์ prompt ใหม่ (`guard.py` ฟังก์ชัน `prompt()` บรรทัด ~1061 ยกเว้นกรณี `still_working`) การเขียนครั้งแรกของเทิร์นถูกปฏิเสธถ้า Claude ยังไม่บันทึกข้อความตอบลง transcript ภายใน `TRANSCRIPT_WAIT = 1.0` วินาที (`guard.py:55`) จน AGENTS.md ต้องมีย่อหน้าอธิบายวิธีเลี่ยง ("in Claude run `declare` only when the turn's first tool call writes…")

**หลักฐาน** วันที่ 2026-10-30: contract 22 ครั้ง, ต่างกันจริง 19, ประกาศข้อความเดิมซ้ำ 3 ครั้ง (contract เดิมถูกล้างเพราะ prompt ใหม่ในงานเดิม); แหล่งที่มา `declared` 20 ครั้ง, `transcript` 2 ครั้ง นั่นคือทางหลักที่เอกสารแนะนำ (บรรทัดแรกของคำตอบ) ถูกใช้จริงไม่ถึง 1 ใน 10

**ทางแก้ที่เสนอ** (เลือกทางใดทางหนึ่ง)
- (ก) contract คงอยู่ทั้ง session จนกว่าจะประกาศใหม่หรือสั่ง `lean contract clear`; prompt ใหม่ของผู้ใช้แค่ติดธง "ต้องยืนยันว่ายังเป็นงานเดิม" ที่โชว์ใน status ไม่ล้างทิ้ง
- (ข) ให้ `lean contract declare` เป็นทางหลักทางเดียว แล้วตัดโค้ดอ่าน transcript (`transcript_contract`, `bind_transcript`, `still_working` รวมประมาณ 150 บรรทัดและ test) ออก เอกสารจะสั้นลงมาก
- (ค) ถ้ายังคง transcript ไว้: เพิ่มเวลารอ และข้อความปฏิเสธบอกให้ "ลองใหม่อีกครั้ง" แทนที่จะส่ง HELP ยาว 8 บรรทัดทุกครั้ง

**เกณฑ์ตรวจ** session ที่มี N prompt ในงานเดียวประกาศ contract ครั้งเดียว; การเขียนครั้งแรกหลังบรรทัด contract ไม่ถูกปฏิเสธใน Claude; test ใน `.lean/tests/hooks/test_guard.py`

**สถานะที่ bca42e1** ยังอยู่: `prompt()` ยังล้าง contract เมื่อไม่ `still_working` (`guard.py` ~1075)

### 2. Shell write heuristic is inconsistent

**ปัญหา** `shell_writes` ตัดสินจากรายการคำ ไม่ใช่ผลที่เกิดจริง

**หลักฐาน** ยิง payload PreToolUse โดยไม่มี contract:
- `pnpm build` ถูกบล็อก เพราะ `build` อยู่ใน `INSTALL_WORDS` (`guard.py:575`)
- `pnpm test` และ `pnpm bench:local` ผ่าน แม้เขียนไฟล์จริง (cache, `bench-results/`)
- `mkdir -p <scratchpad ของ Claude>/x` ถูกบล็อก เพราะข้อยกเว้น `external_scratch_or_memory` (`guard.py:373`) ใช้กับ Edit/Write/MultiEdit เท่านั้น ไม่ครอบ Bash ที่เป้าหมายอยู่ใต้ `/private/tmp`
- `sed -i`, `git commit` ถูกบล็อก (ถูกต้อง)

**ทางแก้ที่เสนอ** ให้ package script (`pnpm <script>`, `npm run <script>`) เป็นการอ่าน ยกเว้นคำ install/publish; เอา `build` ออกจาก `INSTALL_WORDS` หรือให้ PROJECT.md ประกาศ allowlist ของ script ที่รันได้ก่อนมี contract; ข้อยกเว้น scratch ใช้กับ Bash ด้วยเมื่อทุก path เป้าหมายอยู่ใต้ scratch root

**เกณฑ์ตรวจ** ตารางคำสั่งกับผลที่คาดไว้เป็น test case ใน `test_guard.py`

**สถานะที่ bca42e1** ยังอยู่: `INSTALL_WORDS` มี `build` (`guard.py:576`); `external_scratch_or_memory` ยังจำกัดเฉพาะ Edit/Write/MultiEdit (`guard.py:374`)

### 3. Review receipts do not travel and keep no history

**ปัญหา** receipt อยู่ใน `.agent-runtime/review.json` ไฟล์เดียว, git-ignored, ใบใหม่ทับใบเก่า

**หลักฐาน**
- TCK021: "The receipt file holds only the latest receipt, so the TCK022 receipt recorded afterwards on the same unchanged state replaces this one"
- TCK031, TCK032: "Review receipts recorded in the cloud container do not exist on the Mac. Before `lean gate run … --require-review`, run an independent review on the Mac of the delta since its last PASS" → ต้อง review ซ้ำทุกครั้งที่ย้ายเครื่องหรือ worktree
- REVIEW.md: การเปลี่ยนเนื้อหาใด ๆ หลัง review ทำให้ receipt ใช้ไม่ได้ จึงเกิดรอบ review ซ้ำสำหรับการแก้เล็ก ๆ

**ทางแก้ที่เสนอ** เก็บหลายใบ key ด้วย (contract, state) ในที่ที่ commit ได้ เช่น `docs/tracking/receipts/<state>.json` หรือ git notes `refs/notes/lean-review`; `check-review` ค้นหาใบที่ตรง state ปัจจุบัน ไม่ใช่ใบล่าสุด; คงกติกา "เฉพาะ reviewer บันทึก" ไว้

**เกณฑ์ตรวจ** receipt ที่บันทึกบนเครื่อง A ใช้ตรวจบนเครื่อง B ได้หลัง fetch; สอง contract ใน batch เดียวมี receipt ครบทั้งคู่

**สถานะที่ bca42e1** ยังอยู่: `evidence.py:553, 753` อ่านและเขียน `.agent-runtime/review.json` ไฟล์เดียว

### 4. Dispatch records require model/effort that runtimes never report

**ปัญหา** `lean-agents/SKILL.md` และ AGENTS.md บังคับบันทึก requested และ reported model/effort ("never bare inherited/inherited") แต่ไม่มี runtime ไหนคืนค่าให้ agent

**หลักฐาน** ทุก dispatch record ของวันนั้นจบด้วย "reported model/effort=unavailable" (TCK031, TCK032, TCK033, TCK037, TCK039, TCK040); สตริง reviewer ใน activity.jsonl เช่น "Independent Codex reviewer …; requested gpt-6.1-sol/high; runtime reported model/effort unavailable"

**ทางแก้ที่เสนอ** ให้ `lean spawn run` อ่านจาก output ของ CLI เอง (Claude `--output-format json` มีฟิลด์การใช้งานต่อโมเดล, Codex `exec --json` มี header ของ session) แล้วบันทึกลง activity.jsonl; ถ้าไม่มีให้ละฟิลด์ และ policy ยอมรับ "ไม่มีรายงานจาก runtime" โดย agent ไม่ต้องพิมพ์ประโยคนี้เอง

**เกณฑ์ตรวจ** dispatch record ถูกสร้างโดย `lean spawn run` ไม่ใช่พิมพ์โดย agent

**สถานะที่ bca42e1** ยังอยู่ (เป็นข้อกำหนดใน policy และ skill)

### 5. `lean update` reports false conflicts when the source URL form changes

**ปัญหา** `update.py:258` เทียบ `recorded.get("source") == source` เป็นสตริง ถ้า URL ต่างรูป (ssh กับ https) จะได้ `previous = None` และทุกไฟล์ที่ upstream เปลี่ยนถูกตีเป็น `conflict` แม้ไม่ได้แก้ในเครื่อง

**หลักฐาน**
- pin เดิม (`git show 8b0d723:.lean/upstream.json`): `"source": "git@github.com:aussadawut-dev/lean-workflow-agent-by-asdw.git"`
- pin ใหม่หลังอัปเดต: `"source": "https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git"`
- TCK039: "Nineteen conflicts matched v5.3.1 exactly; only test_models.py had a project customization"
- ค่าใช้จ่ายที่ตามมา: contract HIGH เพิ่ม 1 ใบ, workflow test เพิ่ม 2 รอบ (143 s, 178 s), review REWORK 1 รอบ

**ทางแก้ที่เสนอ** normalize ตัวตนของ source เป็น host + path (ตัด `.git`, ถือ ssh/https เป็นรีโปเดียวกัน) หรือ checkout commit ที่บันทึกไว้จาก source ปัจจุบันได้เลย; ถ้าหา base ไม่ได้จริง ให้ preview ติดป้าย "no base (unverified)" และบอกสาเหตุ แทนคำว่า "conflict"

**เกณฑ์ตรวจ** e2e test ใน `.lean/tests/e2e/test_update.py`: pin แบบ ssh แล้วอัปเดตด้วย https ไฟล์ที่ไม่ได้แก้ต้องเป็น "unmodified locally"

**สถานะที่ bca42e1** ยังอยู่: `update.py:258` เทียบสตริงเหมือนเดิม

### 6. The impact map does not cover the pin file, and nothing checks coverage

**ปัญหา** `.lean/tests/impact.json` ไม่มี `.lean/upstream.json` ทำให้ทุกครั้งที่ขยับ pin `lean test --changed` พิมพ์ "no impact rule covers: .lean/upstream.json" แล้วรันชุดเต็ม

**หลักฐาน** เหตุการณ์ `test` ใน activity.jsonl: 233.3 s (selection: no impact rule covers: .lean/upstream.json), 143.4 s (… .lean/lean/intake.py, .lean/upstream.json), 178.3 s, 121.5 s (… .lean/upstream.json) นอกจาก 253.9 s ของ `--all` ตอน restore

**ทางแก้ที่เสนอ** ใส่ `.lean/upstream.json` ใน `lint_only`; ให้ `lean lint` ล้มเมื่อ asset ใดใน `assets.json` ไม่มี scope หรือ rule ใน impact.json เพื่อกันไม่ให้เกิดซ้ำกับไฟล์ใหม่ในรุ่นถัดไป

**เกณฑ์ตรวจ** หลังขยับ pin `lean test --changed` เลือก 0 ไฟล์; lint มี test สำหรับ asset ที่ไม่ถูกครอบ

**สถานะที่ bca42e1** ยังอยู่: `.lean/tests/impact.json` ยังไม่มี `.lean/upstream.json`

### 7. `lean update` leaves version text in PROJECT.md stale

**ปัญหา** PROJECT.md ของโปรเจกต์ยังเขียน "Lean 5.3.1 uses tracker/direct" และ "commit d6a7af66…" ขณะที่ `upstream.json` เป็น 5.5.0 `dde70f6`; `lean mode check` ไม่ตรวจเรื่องนี้

**ทางแก้ที่เสนอ** template ของ PROJECT.md ไม่ฝังเลขรุ่น (ชี้ไป `upstream.json` แทน) หรือให้ update เขียนทับบรรทัดที่มี marker เช่น `<!-- lean:version -->`; `lint` เตือนเมื่อไม่ตรง

**เกณฑ์ตรวจ** หลังอัปเดตไม่มีสตริงรุ่นเก่าค้างใน PROJECT.md

**สถานะที่ bca42e1** แก้บางส่วนใน 5.6.0: preview เตือนเมื่อ Purpose มีข้อความ "Lean Workflow Baseline X.Y.Z" (`update.py:24` regex `BASELINE`, ใช้ที่ ~336-340) แต่ regex ไม่จับรูป "Lean 5.3.1 uses tracker/direct" ที่ asdw-harness เขียนไว้ จึงไม่เตือนในกรณีนี้ และยังไม่มีการแก้อัตโนมัติ

### 8. Gate automation is binary: everything at every Stop, or nothing

**ปัญหา** `gate.json` มีแค่ `auto`/`manual` (+`fixloop`) โหมด auto รันทั้งบล็อก PROJECT.md ทุก Stop; โหมด manual ไม่รันอะไรเลยและงานค้าง NOT_RUN จนกว่าผู้ใช้จะอนุมัติ

**หลักฐาน**
- บล็อก gate ของโปรเจกต์: lint, mode check, models check, attribution, `lean test --changed`, `pnpm typecheck`, `pnpm test`, `pnpm build` (Stop hook ตั้ง timeout 600 s ใน `.claude/settings.json`) จึงต้องเลือก manual ตั้งแต่คอมมิต 6b1f76e
- tracker ที่บันทึก "Full gate NOT_RUN, needs user authorization": TCK031, TCK032, TCK035, TCK036, TCK037 (ค้าง BLOCKED), TCK039, TCK040, TCK041
- วันที่ 2026-10-30: gate รันจริง 2 ครั้ง (147.5 s และ 33.7 s) เทียบกับ review 15 และ contract 22
- `gate scope` และ `gate preflight` ของ 5.5.0 ยังไม่ปิดช่องนี้

**ทางแก้ที่เสนอ** แยกชั้นใน PROJECT.md: `gate:stop` (เร็ว รันอัตโนมัติทุก Stop: lint, mode check, typecheck, `test --changed` หรือ focused tests) และ `gate:full` (test เต็ม, build) รันเมื่ออนุมัติหรือหนึ่งครั้งต่อ batch; `lean status` รายงานสองชั้นแยกกัน

**เกณฑ์ตรวจ** Stop ในโหมด auto จบภายในชั้นเร็ว; tracker แสดง "stop PASS / full NOT_RUN" แทน NOT_RUN ทั้งหมด

**สถานะที่ bca42e1** ยังอยู่: `gate.py` รู้จักแค่บล็อก `gate:start`/`gate:end` เดียว; 5.6.0 เพิ่ม `gate-result.json` กับสถานะ RUNNING/PASS/STALE/FAIL/NOT_RUN ซึ่งช่วยให้เห็นผล แต่ไม่ได้แยกชั้นการรัน

### 9. PreToolUse hook has no matcher and fails closed on infrastructure errors

**ปัญหา** `.claude/settings.json` ตั้ง PreToolUse โดยไม่มี `matcher` และใช้ `… || exit 2` จึง spawn Python ทุก tool call รวม Read/Grep/MCP และถ้า `python3` หายหรือ `$CLAUDE_PROJECT_DIR` ว่าง ทุก tool ถูกปฏิเสธรวมการอ่าน ทั้งที่ `guard.pre_tool` ปล่อย READ_ONLY และ tool ที่ไม่รู้จักอยู่แล้ว

**หลักฐาน** วัดได้ 37–40 ms ต่อ call (payload Read, Edit, Bash); ไม่กระทบตอนนี้ แต่เป็นจุดล้มทั้งระบบจุดเดียว

**ทางแก้ที่เสนอ** `"matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash"` (และเทียบเท่าใน `.codex/hooks.json`) ให้การอ่านไม่ spawn Python และความล้มเหลวของ infra บล็อกเฉพาะการเขียน ซึ่งตรงกับหลัก "reads run first"; คง `|| exit 2` ไว้สำหรับตัวเขียน ข้อแลกเปลี่ยน: การป้องกันเขียน `review.json` ผ่าน MCP file tool แปลก ๆ หายไป ยอมรับได้ตามคำอธิบาย "not a security boundary"

**เกณฑ์ตรวจ** `lean lint` ตรวจ template ของ settings; test ว่ามี matcher

**สถานะที่ bca42e1** ยังอยู่: `.claude/settings.json` ของ upstream ไม่มี matcher และยังใช้ `|| exit 2`

### 10. Runtime folder is shared and generically named

**ปัญหา** `.agent-runtime/` เก็บ state ของ Lean (`contract-sessions.json`, `progress/`, `review.json`, `gate-*`, `activity.jsonl`) ปนกับไฟล์ของแอปและ scratch ของ agent ภายใต้ชื่อโฟลเดอร์กลาง ๆ ที่ใครก็ใช้ได้ (หมายเหตุ: ข้อสังเกตแรกของผู้รวบรวมว่า `status --line` ไม่อ่าน `session_id` จาก stdin นั้นผิด; `cli.py:349 status_line_session()` อ่านแล้วตั้งแต่ 5.3.1)

**หลักฐาน**
- สคริปต์ของแอป `scripts/live-*.ts` เขียนรายงานลง `.agent-runtime/mvp|agents|usage|commands|controls`
- checkout หลักมี scratch ของ agent ใน `.agent-runtime/` (adapters-before.ts, cli-spike/, codex-install-reference.sh 42 KB) และ marker ค้าง `codex-gate-failed`, `codex-gate-refusal` จาก 2026-10-28
- session ของ Claude และ Codex ใช้ `contract-sessions.json` และ `progress.json` ร่วมกันใน checkout เดียว; session ที่ยังไม่มี progress ของตัวเองเห็นงานของอีก session พร้อมป้าย "session 01a18ca4: 100% done — Commit push…" ซึ่งถูกต้องตามออกแบบ แต่ชวนสับสนเมื่อหลาย provider ใช้ checkout เดียว

**ทางแก้ที่เสนอ** ย้าย state ไป `.agent-runtime/lean/` หรือ `.lean-runtime/` พร้อม migration ใน update; กวาด marker และ session file ที่เก่ากว่า N วันทุกชนิด (ตอนนี้ prune เฉพาะ `progress/`)

**เกณฑ์ตรวจ** ไม่มีไฟล์ของ Lean ที่ root ของ `.agent-runtime/`; marker ของ Codex ที่เก่าถูกกวาด

**สถานะที่ bca42e1** ยังอยู่ (ส่วน status line ไม่ใช่ปัญหาแล้ว)

### 11. Footprint and self-tests shipped into consumer repositories

**ปัญหา** ชุดที่ติดตั้งในรีโปผู้ใช้ใหญ่เท่ากับแอปที่มันดูแล และ gate ของรีโปผู้ใช้รัน self-test ของ Lean

**หลักฐาน**
- `.lean/` 1.6 MB, 156 ไฟล์; Python 7,721 บรรทัด + tests 10,372 บรรทัด เทียบแอป src 8,156 + tests 9,459 บรรทัด
- `.lean/CHANGELOG.md` 149,602 bytes (สองภาษา), `.lean/evals/` ชุดโจทย์ประเมินโมเดล
- workflow test ที่รันในรีโปผู้ใช้วันที่ 2026-10-30 รวม 930 s (253.9 + 233.3 + 143.4 + 178.3 + 121.5)
- เอกสารกติกาที่ agent ต้องอ่าน (policy, skills, README, CUSTOMIZING, AGENTS, CLAUDE) รวม 928 บรรทัด ประมาณ 114 KB

**ทางแก้ที่เสนอ** `assets.json` แยกกลุ่ม `core` (bin, lean, policy, roles, skills, templates, README, CUSTOMIZING, LICENSE) กับ `dev` (tests, evals, CHANGELOG) ให้ `lean update --with dev` เป็น opt-in; self-test ของ Lean รันใน CI ของ upstream ส่วนรีโปผู้ใช้เหลือ `lean lint`, `mode check` และ smoke สั้น ๆ; ลดเวลา e2e ที่ spawn subprocess มาก

**เกณฑ์ตรวจ** import ค่าเริ่มต้นเล็กกว่า 500 KB; gate ของรีโปผู้ใช้หลังขยับ pin ใช้เวลาต่ำกว่า 30 s

**สถานะที่ bca42e1** ยังอยู่: `.lean/` ใน upstream 2.6 MB, `.lean/CHANGELOG.md` 152,694 bytes

### 12. Tracker `Status:` line is too strict

**ปัญหา** `records.py` ใช้ `^Status: [A-Z_]+$` (บรรทัด ~270, 312, 456, 766) โน้ตต่อท้ายทำให้ `lean mode check` ล้มทั้ง gate

**หลักฐาน** TCK031: "`lean mode check` first failed on `Status:` lines carrying notes (TCK029-031); fixed in e591a46 (notes moved to `Status note:`)"

**ทางแก้ที่เสนอ** ยอมรับ `Status: VALUE` ที่มีโน้ตตามหลัง (เช่น ` — note` หรือ `(note)`) หรืออย่างน้อย error ระบุไฟล์:บรรทัด และบอก convention `Status note:`; ใส่ตัวอย่างใน template

**เกณฑ์ตรวจ** unit test ทั้งสองรูป

**สถานะที่ bca42e1** ยังอยู่: regex `^Status: [A-Z_]+$` ใน `records.py`

### 13. `lean gate mode <mode>` writes `.lean/gate.json` silently

**ปัญหา** ไฟล์ถูกเขียนโดยไม่มีบันทึกใน activity.jsonl และไม่มีคำเตือนให้ commit session ถัดมาจึงเจอไฟล์ untracked ที่ไม่รู้ที่มา

**หลักฐาน** TCK020: "An untracked `.lean/gate.json` (`{"auto": false, "fixloop": true}`, author unknown, not this task) sets `manual_fixloop`"; TCK021: "`.lean/gate.json` … appeared at 01:08; not written by this session"

**ทางแก้ที่เสนอ** `gate mode <mode>` บันทึกเหตุการณ์ (session, ค่าก่อน/หลัง) และพิมพ์ "commit `.lean/gate.json`"; SessionStart แจ้งเมื่อ gate.json ยัง untracked

**เกณฑ์ตรวจ** activity.jsonl มีเหตุการณ์; test ของ notice

**สถานะที่ bca42e1** ยังอยู่: `gate.py` บันทึก activity เฉพาะผล gate run (~702-706) ไม่บันทึกตอน `gate mode <mode>`

### 14. Review depth by area is all-or-nothing HIGH

**ปัญหา** CONTRACTS.md: path ที่อยู่ใน High-risk areas ของ PROJECT.md บังคับ `risk=HIGH` และ gate ต้องการ HIGH receipt ไม่มีระดับกลางให้เลือกต่อพื้นที่

**หลักฐาน** ในรีโปนี้รายการครอบ `src/main/`, `src/preload/`, `src/host/`, `src/shared/validation.ts`, `resources/`, `.claude/settings.json`, `.lean/…` (รายการกว้างเป็นเรื่องของโปรเจกต์ ดูภาคผนวก B) ผลคือ contract HIGH 11 จาก 22 ใบในวันเดียว, review อิสระเกือบทุกงาน, REWORK 7 รอบ

**ทางแก้ที่เสนอ** ให้แต่ละพื้นที่ใน PROJECT.md ระบุ depth (`HIGH` หรือ `MEDIUM`) และเงื่อนไขได้ (เช่น การแก้เฉพาะ test ไม่ยกระดับ); gate บังคับตาม depth ของพื้นที่ที่โดนจริง; `lean-init` เตือนเมื่อ glob ความเสี่ยงสูงครอบเกินสัดส่วนที่กำหนดของ tree

**เกณฑ์ตรวจ** การแก้ในพื้นที่ MEDIUM ต้องการ MEDIUM receipt ไม่ใช่ HIGH

**สถานะที่ bca42e1** ยังอยู่ (policy) หมายเหตุ: `.lean/PROJECT.md` ของ upstream เองระบุ High-risk areas แคบและบอกเหตุผลต่อบรรทัด เป็นตัวอย่างที่ดีให้ `lean-init` ใช้สอน downstream

### 15. Tracker overhead for short tasks

**ปัญหา** โหมด tracker ต้องมี tracker ต่อ "non-trivial task" ทุกใบ รวมงาน LOW สั้น ๆ และ template ต้องการ dispatch record ต่อรอบ review

**หลักฐาน** `docs/tracking/` มี TCK 38 ไฟล์ รวม 258 KB; วันที่ 2026-10-30 tracker เพิ่ม 2,155 บรรทัด เทียบโค้ด +9,956/−918 (ประมาณ 22% ของ diff); TCK040 มี "Expanded contract:" หลายรอบในไฟล์เดียว

**ทางแก้ที่เสนอ** บังคับ tracker เมื่อ risk ≥ MEDIUM หรืองานข้าม session เท่านั้น งาน LOW บันทึกใน activity.jsonl และ commit message; template แบบย่อ; dispatch record สร้างโดย `lean spawn` (ข้อ 4)

**เกณฑ์ตรวจ** งาน LOW ผ่าน `mode check` ได้โดยไม่มี tracker ในโหมด tracker (ตั้งค่าได้)

**สถานะที่ bca42e1** ยังอยู่ (policy); 5.6.0 เพิ่มการปิด tracker ด้วยหลักฐาน (`tracker status --status DONE --contract … --evidence …`) ซึ่งเพิ่มความเข้มอีกชั้น ควรชั่งกับข้อนี้

### 16. Minor

- (ข้อ 16 ไม่ได้ตรวจซ้ำที่ bca42e1)
- `hooks.claude_stop` ในโหมด manual พิมพ์ย่อหน้า policy ลง stderr พร้อม exit 0 ทุก Stop; ตามเอกสาร hooks ของ Claude Code stderr ที่ exit 0 ไม่ถูกแสดงต่อโมเดลหรือผู้ใช้ ควรเงียบหรือส่งเป็น `systemMessage`
- `lean contract current` บังคับ `--session` ทั้งที่ `progress` หา session จาก env ได้แล้ว ควรใช้วิธีเดียวกัน
- `lean evidence --help` ตอบ "unrecognized arguments: --help"
- CLI ไม่มีคำสั่งดู contract และ tracker ที่ active แบบรวม (`contract show`, `tracker list` ไม่มี ต้องเดาชื่อ)

---

## ภาคผนวก A — สิ่งที่ตรวจพบแต่ไม่ใช่ปัญหาของ Lean (ไม่ต้องแก้ที่ upstream)

- คอมมิต cdccdee (2026-10-29) ถอด Lean ทั้งชุดด้วยเหตุผล "hooks denied writes until a Lean contract was bound" และติด trailer `Co-Authored-By` ที่กติกาโปรเจกต์ห้าม เป็นความผิดพลาดของ session นั้น การ restore ใน TCK033 ถูกต้องแล้ว (ข้อ 1 ลดแรงจูงใจแบบนี้ได้)
- คอมมิต a092d51 รวมการ restore Lean 208 ไฟล์เข้ากับคอมมิตฟีเจอร์ UI เป็นวินัยการใช้
- ชื่อ bench arm `lean`, `lean2`, `lean3` ใน asdw-harness เป็นของเหลือจากการทดลองนำแนวคิดไปใช้กับโมเดลเล็ก ไม่เกี่ยวกับ Lean upstream
- การตีความว่า review ตื้นจากเวลา REWORK → PASS 84–199 s ถูกตัดออก เพราะ timestamp คือเวลาบันทึก receipt ไม่ใช่เวลาตรวจ
- hook ของ Codex ต้อง trust ก่อน และ agy ไม่มี hook เป็นข้อจำกัดของ provider ไม่ใช่ของ Lean (เอกสารระบุไว้แล้ว)

## ภาคผนวก B — การตั้งค่าฝั่ง asdw-harness ที่จะกลับไปปรับหลังอัปเดต Lean

- ตัด High-risk areas ใน `.lean/PROJECT.md` ให้เหลือขอบเขตจริง (approvals, IPC boundary, การลบ worktree และไฟล์) และใช้ depth ต่อพื้นที่เมื่อข้อ 14 มี
- ใช้ gate แบบแยกชั้นเมื่อข้อ 8 มี; จนกว่าจะถึงตอนนั้น พิจารณาเอา `pnpm build` ออกจาก gate ประจำ
- ทบทวนโหมด tracker สำหรับงานสั้น (ข้อ 15)
- ย้าย output ของ `scripts/live-*.ts` ออกจาก `.agent-runtime/` ไปโฟลเดอร์ของแอปเอง
- เปลี่ยนชื่อ bench arm `lean*` และเลิกทิ้ง scratch ใน `.agent-runtime/`
- อัปเดตข้อความรุ่นใน PROJECT.md (จนกว่าข้อ 7 จะทำให้อัตโนมัติ)

## ภาคผนวก C — วิธีวัด

- เวลา hook: `echo '<payload>' | python3 .lean/bin/lean hook claude pre-tool` ด้วย payload ที่มี `session_id`, `transcript_path` (ไฟล์ไม่มีอยู่), `tool_name`, `tool_input` จับเวลาด้วย `time`; รายการที่ทดสอบ: Read, Edit, Bash `pnpm build`, Bash `pnpm test`, Bash `sed -i`, Bash `mkdir -p <scratchpad>/x`, Bash `git commit -m x`
- จำนวนเหตุการณ์: นับจาก `.agent-runtime/activity.jsonl` ของ checkout `feat/improve-ui` เฉพาะวันที่ 2026-10-30
- ขนาด: `du -sh .lean`, `find .lean -type f | wc -l`, `cat .lean/lean/*.py | wc -l`, `find .lean/tests -name '*.py' | xargs cat | wc -l`
- diff ของวัน: `git log --since=2026-10-30T00:00 --numstat --format= -- docs/tracking` และ `-- src tests`
- ตรวจซ้ำกับ upstream: grep ตามบรรทัดที่อ้างใน checkout `develop` = `bca42e1` ของ lean-workflow-agent-by-asdw (อ่านอย่างเดียว ไม่ได้รัน test ที่นั่น)
