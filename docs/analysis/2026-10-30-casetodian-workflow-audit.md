# ผลตรวจ handoff Casetodian เทียบ Lean 5.4.1

วันที่ 2026-10-30 · เจ้าของงาน: Codex session `01a18c6b-25af-7341-8b8c-d92ef26f8787` · Workset: [TCK018](../tracking/TCK018.md)

รายงานนี้เป็น snapshot ก่อนแก้ไขที่ HEAD `e17f7f9`; งาน implementation หลังผู้ใช้สั่งเริ่มติดตามแยกใน [TCK019](../tracking/TCK019.md) ให้ใช้สถานะและหลักฐานใน workset นั้นประเมินผลการแก้ปัจจุบัน

## สิ่งที่ Project Owner ต้องทราบ

ตรวจใหม่แล้วพบช่องว่าง upstream ที่ยังอยู่ 2 เรื่อง: queue ป้องกัน scope ซ้ำด้วยข้อความตรงกันเท่านั้น และ target tracker ยังทำให้ review receipt stale เมื่ออัปเดต closure ส่วนการตรวจ receipt หลัง checks เป็นพฤติกรรมที่ตั้งใจรักษาลำดับ deterministic validation ก่อน review แต่ทำให้รู้ปัญหาช้า จึงควรพัฒนา preflight แยกต่างหาก

Casetodian ยังมีช่องว่าง config ที่ full gate ไม่เรียก browser suite และเอกสารยังอ้าง test-health tracker ที่ปิดแล้ว ทั้งสองเป็นงานของเจ้าของ integration ไม่ใช่ข้อบกพร่องของตัวรัน Lean โดยอัตโนมัติ อีกเรื่องเป็นการ stage records ไม่ครบในอดีต มี commit ตามเก็บแล้ว แต่ยังไม่มีหลักฐานพอจะโยงว่าเป็น Lean code bug

รอบนี้ส่งมอบการวิเคราะห์และข้อเสนอเท่านั้น ไม่แก้ implementation, config, rules หรือ records ของ Casetodian และไม่ commit/push/merge/tag/release/deploy การอนุมัติ release ของ TCK017 ไม่ขยายมาถึงงานนี้

| ID | ระดับ / ประเภท | ผลตรวจปัจจุบัน | ลำดับเสนอ |
|---|---|---|---|
| CW-01 | HIGH / upstream ownership gap | ยืนยันซ้ำทั้งฟังก์ชันและ public queue CLI | 1: กำหนด semantics แล้วแก้การชน scope |
| CW-02 | HIGH / upstream review lifecycle gap | target `TCK*.md` ยังอยู่ใน review fingerprint; `INTAKE.md` ได้รับข้อยกเว้นแล้วใน 5.4.1 | 2: ออกแบบข้อยกเว้น closure ที่มีขอบเขต |
| CW-03 | MEDIUM / upstream efficiency + process | checks รันก่อนปฏิเสธ receipt; fail closed ตามกฎปัจจุบัน | 3: preflight หลัง validation/review ก่อน final gate |
| CW-04 | HIGH / project integration | config ต้นทางที่อ่านรอบนี้ไม่มี browser suite command | ทำคู่ขนานกับ 1 โดยเจ้าของ Casetodian |
| CW-05 | MEDIUM / project docs/process | กฎยังบอก TCK421 เปิดอยู่ แต่ tracker เป็น DONE | รวมกับ CW-04 |
| CW-06 | MEDIUM / publication process | commit ตามเก็บยืนยันว่ามี closure records และ app pointer แยกตามหลัง | ก่อน publication ครั้งถัดไป |

ระดับ HIGH ของ CW-01/02 บอกผลกระทบที่อาจเกิดกับ ownership/evidence ไม่ได้หมายความว่าพบไฟล์เสียหายหรือมีการปล่อยงานที่ไม่ได้ review แล้ว

## ขอบเขตและที่มาของหลักฐาน

- Lean ที่ตรวจ: version **5.4.1**, HEAD `e17f7f958337ce8b1392131ba5e601cdf64699a9`, branch `improve-requirement-flow`; ตอนเริ่ม git clean, tracker/direct, auto_fixloop และไม่มี active queue claims
- อ่าน AGENTS, README, PROJECT/config และ TCK016/017 ก่อนเขียน พบ release เดิม DONE; B2/B3 ยังเป็น follow-up ไม่มี accepted implementation scope สำหรับประเด็นชุดนี้
- Orca แสดง 2 sessions ใน checkout: session release เดิม done และ session รับ handoff นี้ working เป็น snapshot ไม่ใช่ checkout lock จึงใช้ไฟล์ใหม่เฉพาะ TCK018/รายงานนี้
- Handoff จากผู้ใช้เป็นหลักฐานประวัติ Lean **5.3.1** ณ 2026-10-30 ส่วนผลทดลองด้านล่างมาจากโค้ด **5.4.1** ที่ HEAD ข้างต้น
- อ่าน source Casetodian เฉพาะ PROJECT gate blocks, test/config/rules/queue scope และ commit stat แบบ read-only ไม่เปิด secrets ไม่รัน application หรือ browser/full gate ต้นทาง ไม่เปลี่ยนไฟล์ต้นทาง
- `workflow_root` ต้นทาง: `/Users/x10/orca/workspaces/casetodian-workspace/chore-improve-tasks-not-done`; application: `targets/casetodian-next-v2`; target records: `.lean/targets/casetodian-next-v2`

## CW-01: scope ownership ยังตรวจเฉพาะข้อความตรงกัน

โค้ดปัจจุบัน: `.lean/lean/records.py:571` (`validate_claims`) ใช้ `scopes.intersection(item["scopes"])`; บรรทัด 672/689 ในเส้นทาง `claim` และ `claim-next` ใช้ occupied set เดียวกัน ไม่มี normalization หรือ ancestor comparison ส่วน schema รับรายการ string และ template ใช้ `area:example` จึงมีทั้ง opaque labels และ path-like scopes โดยยังไม่มี grammar แยกสองชนิด

ทดลองเรียกฟังก์ชันจริงโดยไม่เขียน repo และเรียก public CLI ใน TemporaryDirectory ด้วย fixture `WorkflowModeTests` เดิม (configure full, สร้างสอง READY items, claim ด้วย agent คนละชื่อและ request ID คนละค่า):

| scopes ของสองรายการ | validate_claims | claim รายการที่สอง | claim-next หลังรายการแรกมี lease |
|---|---|---|---|
| `src/` กับ `src/` | REFUSED | exit 2 | exit 2 |
| `src/` กับ `src/a.ts` | ALLOWED | exit 0 | exit 0 |
| `src` กับ `src/` | ALLOWED | exit 0 | exit 0 |
| `src/a.ts` กับ `src/a.ts` | REFUSED | ไม่ทดลองเพิ่ม | ไม่ทดลองเพิ่ม |
| `src/` กับ `src-other/a.ts` | ALLOWED | ไม่ทดลองเพิ่ม | ไม่ทดลองเพิ่ม |
| `area:api` กับ `area:api` | REFUSED | ไม่ทดลองเพิ่ม | ไม่ทดลองเพิ่ม |
| `area:api` กับ `area:web` | ALLOWED | ไม่ทดลองเพิ่ม | ไม่ทดลองเพิ่ม |

อ่าน queue ต้นทางพบ scope ลงท้าย `/` 44 ค่า (นับค่าทั้งหมด ไม่ใช่ unique) เช่น `targets/casetodian-next-v2/apps/web/src/app/navigation/` จึงไม่ใช่รูปแบบสมมติล้วน ผู้ใช้สองรายอาจเข้าใจว่าถือพื้นที่คนละ claim แต่มีไฟล์ซ้อนอยู่ภายใน ไม่มีหลักฐาน file corruption จากการตรวจนี้ และไม่ได้จำลอง concurrent writers

ข้อเสนอ: กำหนดชนิด/grammar ก่อน แล้วใช้ overlap predicate เดียวใน validation และ selection โดยรักษา opaque labels; สำหรับ path scopes เปรียบเทียบส่วนประกอบ path เพื่อให้ directory ชน descendants แต่ `src` ไม่ชน `src-other` ต้องตัดสินใจอย่างชัดเจนเรื่อง `src`/`src/`, `./`, `..`, absolute paths, wildcard, case และ symlink ห้ามใช้ raw string-prefix หรือ normalize labels ทุกชนิดอย่างเงียบ ๆ

Acceptance ของชุดแก้: fail-before/pass-after ผ่าน public `claim` และ `claim-next` พร้อมตรวจ lease ที่โหลดกลับมา, same file, ancestor ทั้งสองทิศทาง, slash aliases, siblings และ opaque labels; ทดสอบ retry/idempotency, expiry/release และ retained records ไม่ถดถอย เพิ่มการทดสอบ concurrent claim เมื่อได้ path semantics ที่ยอมรับแล้ว

## CW-02: target tracker ทำให้ review receipt stale หลัง closure

โค้ดปัจจุบัน `.lean/lean/evidence.py:61` ยกเว้น Markdown โดยตรงใต้ `docs/tracking/` และเพิ่ม target `INTAKE.md` แบบ exact layout เท่านั้น จากนั้น `review_state` ใช้ `entries(root, tracker_record)` ที่บรรทัด 77

เรียก predicate จริง และสร้าง Git sandbox เปล่า (ไม่ commit) ใช้ `review_state`/`state` จริงก่อนและหลังแก้เนื้อหาไฟล์เดียว:

| path | ถูกยกเว้นจาก review | review fingerprint เปลี่ยน | gate fingerprint เปลี่ยน |
|---|---|---|---|
| `docs/tracking/TCK430.md` | True | False | True |
| `.lean/targets/casetodian-next-v2/docs/tracking/TCK430.md` | False | True | True |
| `.lean/targets/casetodian-next-v2/docs/tracking/INTAKE.md` | True | False | True |
| `.lean/targets/casetodian-next-v2/docs/requirements.md` | False | True | True |

เป็นผลจาก filesystem/Git จริง ไม่ได้ mock entries/controls และไม่ได้สร้างหรือปลอม review receipt จึงยืนยันได้ตรงระดับ fingerprint; ประวัติ TCK423 ที่ receipt stale หลังอัปเดต handoff มาจากรายงานผู้ใช้ ไม่ได้ replay receipt ต้นทาง

5.4.1 แก้เฉพาะ target intake ledger แล้ว (เกี่ยวกับ TCK016 B1) แต่ยังไม่ทำให้ target tracker closure มี semantics เดียวกับ workspace tracker ขณะเดียวกัน gate fingerprint รวม work records ตามเดิม การแก้ CW-02 จึงไม่ควรเปลี่ยนข้อกำหนดว่าต้องตรวจ gate ให้ตรง shipping state

ข้อเสนอที่ต้องตัดสินใจก่อน implementation: ยกเว้นเฉพาะ tracker ใน `.lean/targets/<name>/docs/tracking/` ที่ระบุชนิดชัดเจน และคงตรวจ scope/acceptance/metadata ที่มีผลต่อข้อกำหนด เช่น canonical semantic projection หรือแยก mutable closure evidence จาก reviewed requirements ต้องเทียบกับนโยบาย workspace เดิมด้วย ห้ามยกเว้น target docs ทั้งโฟลเดอร์; path-only exclusion เพียงอย่างเดียวไม่รับรองว่า acceptance ไม่ถูกแก้หลัง review

Acceptance ของชุดแก้: closure/evidence-only update ไม่ทำให้ semantic receipt stale ทั้ง workspace/target; การแก้ requirement, acceptance, meaningful metadata, app code หรือ gate controls ต้องยัง invalidate หรือถูกบล็อกตามกติกาที่ตกลง; malformed/symlink/nested/unrelated docs ไม่ได้ข้อยกเว้นเกินขอบเขต; deterministic mode/record checks และ gate fingerprint ยังครอบ records โดยไม่ลด validation เพื่อปิดงาน

## CW-03: receipt readiness รู้ผลหลัง checks

โค้ดปัจจุบัน `.lean/lean/gate.py:422` เรียก target checks ก่อนเตรียม receipt validation; non-cache path รัน workspace subprocess checks ก่อน `receipt_gap()` บรรทัด 544 ส่วน cache-hit ตรวจ receipt ก่อน reuse ที่บรรทัด 503; `.lean/lean/target.py:314–332` รัน commands ก่อน `high_risk_changes`/`check_shipped` แต่ทั้งสอง entry มี controls-drift precheck ก่อน commands อยู่แล้ว

การทดลองใน Git TemporaryDirectory: สร้าง PROJECT gate มีคำสั่ง Python touch marker หนึ่งคำสั่ง เรียก CLI จริง `gate run --require-review --contract 'Contract: risk=HIGH quality=HIGH acceptance=probe'` โดยไม่มี receipt ได้ **exit 2**, marker **มีอยู่** และ stderr แจ้ง `review.json` ไม่พบหลัง check 1 passed ยืนยัน missing-receipt path; ไม่ได้จำลองทุกเงื่อนไข stale/contract/depth ใหม่

นี่เป็น late refusal / efficiency gap ไม่ใช่ safety bypass ปัจจุบัน `.lean/tests/hooks/test_target_gate.py::TargetGateTests.test_target_high_risk_floor_applies_to_all_gate_entries_and_stale_reviews` ตั้งใจ assert ว่า deterministic checks รันก่อน review enforcement การย้าย refusal ให้มาก่อนทุกอย่างจะเปลี่ยนกติกาที่มีอยู่ ต้องออกแบบ preflight แยกจาก validation และ final verification

ประวัติผู้ใช้: TCK423 เคย LOW receipt ไม่พอ HIGH floor; TCK424 exact contract ต่างเครื่องหมายท้ายประโยค; TCK430 run2 checks ผ่านแต่ receipt เก่าก่อนแก้ test จากนั้น refresh review และ run3 ผ่าน ทั้งหมดเป็นประวัติ ไม่ใช่ผลรันรอบนี้ และ PASS นั้นไม่ครอบการแก้ภายหลังโดยอัตโนมัติ

ข้อเสนอ B2: รักษาลำดับ focused deterministic validation → semantic review → readiness preflight → final gate โดย preflight อ่านอย่างเดียว แจ้ง missing/stale/contract/depth/shipping mismatch รวม target ก่อนเริ่มงานแพง และ final gate ต้องตรวจซ้ำเพราะ checks อาจเปลี่ยนไฟล์ ระหว่างนี้ใช้ `evidence check-review --contract '<exact>'` สำหรับ HIGH receipt และ `batch readiness --id <batch>` เมื่อมี ledger; สองคำสั่งนี้ไม่ทดแทน full gate หรือ acceptance evidence

Acceptance: preflight ไม่รัน subprocess checks/ไม่สร้าง PASS; แจ้ง mismatch แต่ละชนิดชัดเจน; content drift ระหว่าง preflight/checks ยังถูก final gate ปฏิเสธ; cache/control/session/target floor ไม่อ่อนลง ห้ามลด quality floor หรือทำ contract fuzzy-match เพื่อประหยัดรอบ

## CW-04/05: browser coverage contract และ test-health pointer ของโครงการ

อ่าน config ต้นทางรอบนี้พบ target gate 5 commands:

```sh
node scripts/check-comment-history.mjs
node --test tests/workspace-paths.mjs
pnpm lint
OPENROUTER_LIVE_TEST=0 pnpm test
pnpm build
```

`package.json` ระบุ test=`vitest run`; target vitest config มี `tests/**` ใน exclude และ workspace browser files อยู่คนละ root คือ `tests/browser/*.test.mjs` (พบ 75 ไฟล์ ไม่ได้รัน) workspace gate 9 checks คือ lint, modes 2 roots, models, changed Lean tests, scoped Python tests, migration, design inventory และ scoped app-contract Vitest ซึ่ง config include เพียง `tests/application/*.test.ts` ไม่พบ browser command ใน gate blocks เหล่านี้; อ่าน entry check-comment-history/workspace-paths แล้วไม่พบการ dispatch browser suite

แต่ target records `docs/runtime/agent-project-rules.md:23` บอก “The full Quality Gate covers the rest” หลังสั่ง focused browser tests จึงเป็น coverage contract gap ไม่ควรรายงานว่า browser ทุกตัวผ่านเมื่อมีเพียง configured gate PASS ตัวรัน Lean ทำตาม PROJECT commands; เจ้าของ integration ต้องตกลงว่าจะใช้ full serial suite, change-aware browser selection ที่มี coverage manifest หรือแก้ข้อความให้ตรง coverage ที่รับประกันและระบุขั้น browser verification เพิ่มเติม การแก้ wording อย่างเดียวไม่ยืนยันว่าตรงความต้องการเดิมของผู้ใช้

บรรทัดเดียวกันยังชี้ “open test-health tracker (TCK421)” แต่ `TCK421.md` เป็น `Status: DONE` ยืนยัน current stale pointer เสนอทะเบียน test-health ถาวรที่มี active owner, current failures, baseline/commit/environment/last-run และลิงก์ tracker ประวัติ หรือระบุชัดว่าไม่มี active tracker พร้อมชี้ archive

Acceptance ของ integration: ทุก browser file ถูก map ไป command หรือ approved exclusion; command สามารถถูก gate เรียกจริงแบบ serial/concurrency=1 ตามกฎโครงการ, failure ทำให้ gate ไม่ PASS และบันทึก environment กับ coverage โดยไม่อาศัยข้อความอ้างลอย ๆ; health pointer ใช้ได้ไม่ว่าจะมี/ไม่มี open tracker การเลือก coverage เป็น material decision ของ Project Owner

ไม่มี browser run ใหม่ในรอบนี้ ไม่สรุปว่า 75 ไฟล์ผ่าน/ล้มเหลวหรือยัง flaky ระยะเวลา 42–89 นาทีและ refetch/render/load timeouts เป็นประวัติที่ผู้ใช้รายงานว่าหลายตัวแก้แล้ว ต้องวัดใหม่ก่อนวินิจฉัย

## CW-06: publication completeness

อ่าน `git show --stat 72a6f9a` ใน workspace ต้นทางแบบ read-only พบ subject `docs(tracking): add the TCK428 closure records missed by bf76480` และ delta ครอบ queue Q9838–Q9842, tracking README/TCK423/TCK427/TCK428 และ app pointer ยืนยันว่ามี follow-up closure commit จริง แต่ commit metadata ไม่พิสูจน์สาเหตุว่า agent ลืม stage, tooling ไม่ช่วย หรือ Lean มีบั๊ก

Lean ปัจจุบัน `evidence.shipping_gap` ตรวจ staged-vs-working-tree และ partial shipping ของ reviewed content อยู่แล้ว แต่ยกเว้น tracker ตาม `tracker_record`; receipt จึงไม่ใช่ manifest ว่าผู้ใช้ตั้งใจ publish records ครบทุกไฟล์ ข้อเสนอ: ก่อน publication สร้าง intended manifest ครอบ app commit/pointer, queue และ closure records แล้ว read back index/commit เทียบ manifest พร้อมแสดง omitted/extra paths หลัง commit ตรวจ tree/reference ตาม scope ที่อนุมัติ ห้าม auto-stage ทั้ง checkout เพราะอาจมีงาน session อื่น

Acceptance: จำลอง record หรือ pointer ตกหล่นแล้วตรวจพบก่อน publish, exact intended set ผ่าน และ unrelated dirty files ไม่ถูก stage; รวมกับ publication procedure เมื่อได้รับอนุญาตในงานใหม่ รอบนี้ไม่ได้รัน publication trial ไม่แก้ commit เดิมและไม่เผยแพร่

## Requirement mapping และชุดงานที่เสนอ

ยังไม่มี optional intake ledger entries/batches ใน worktree นี้ จึงบันทึก requirement map แบบเอกสารภายใต้ TCK018 โดยไม่สร้าง primary batch หรือเปิดงาน queued ให้ active เอง

| Requirement ที่บันทึก | เชื่อมงานเดิม | งาน/owner ที่เสนอ | ขอบเขตการอนุมัติ |
|---|---|---|---|
| R-H01: ownership ต้องกันพื้นที่ path ซ้อนตาม semantics ที่ตกลง | TCK016 AC-02 (ownership intent); queue เป็นส่วนขยายใหม่ | Lean / CW-01 | วิเคราะห์ยืนยันแล้ว; implementation ใหม่รอ scope |
| R-H02: closure ของ target ต้องไม่บังคับ review ซ้ำโดยไม่จำเป็น และยังรักษา requirement integrity | TCK016 B2 + B3; แยกจาก target INTAKE fix ใน B1 | Lean / CW-02 | ยังไม่อนุมัติ exclusion design |
| R-H03: รู้ receipt readiness ก่อน final gate แพง โดยไม่ลด evidence floor | TCK016 B2 | Lean / CW-03 | ข้อเสนอใหม่ใน B2 ที่ยัง queued |
| R-H04: coverage ที่กฎรับปากต้องตรง configured commands | TCK016 B3 (integration/evidence) | Casetodian integration owner / CW-04 | ไม่แก้กฎ/โค้ดต้นทางจาก handoff |
| R-H05: test-health มี current owner และ pointer ที่ไม่หมดอายุตาม tracker | TCK016 B3 | Casetodian process/docs owner / CW-05 | ไม่ตัดสินว่า tests ยัง flaky |
| R-H06: publication ต้องตรง intended shipping manifest | TCK016 B2 closure boundary + process follow-up | ผู้มีอำนาจ publish / CW-06 | ไม่มี publication authorization ในงานนี้ |

ลำดับแนะนำ: ปิด semantics CW-01 แล้วทำ regression/fix ชุดเล็กก่อน; เจ้าของ Casetodian ตัดสินใจ CW-04/05 คู่ขนานได้โดยแยก checkout/ownership; จากนั้นตัดสินขอบเขต CW-02 ก่อนทำ CW-03 เพื่อไม่ optimize รอบที่เกิดจาก closure mismatch อยู่; เพิ่ม CW-06 เป็นเกณฑ์ก่อน publication ครั้งถัดไป ไม่รวม release หรือ migration downstream ในชุดแก้โดยปริยาย

หากอนุมัติ implementation แต่ละชุด ต้องเปิด contract ตาม high-risk areas, tracker/queue ownership ตาม mode, fail-before/pass-after, deterministic validation, independent HIGH review สำหรับ gate/evidence/control/policy และ final shared gate ไม่ใช้ PASS ของรายงานนี้รับรองโค้ดที่ยังไม่ได้แก้

## ข้อที่ไม่ควรนับเป็น current defect

- READY item ที่มี active lease เป็น lifecycle ที่ validate_claims กำหนดไว้ ไม่ใช่ข้อขัดแย้งกับ tracker VALIDATING ต้องดู lease/owner/dependencies ประกอบ
- TCK430/Q9844 และข้อความ Next step เคลื่อนไหวระหว่าง session ต้นทาง ไม่ใช้ snapshot เก่ามาฟ้องว่า current status ผิด; รอบนี้ไม่ได้ audit completion/publication ปัจจุบันของงานนั้น
- `gate status` ของ session หนึ่งเป็น NOT_RUN ไม่ลบล้าง PASS ของอีก session ต้องระบุ session, contract, fingerprint, commands และเวลา ซึ่ง PASS ไม่ครอบ edit ภายหลัง
- guard `-h`, memory/gate-cache bypass และ progress ข้าม session มีประวัติแก้ใน TCK015 / 5.3.1 ไม่จัดเป็น open defects โดยไม่มี reproduction ใหม่ รอบนี้ไม่ได้ retest bypass เหล่านั้น

## การตรวจรับและข้อจำกัด

การทดลอง queue ใช้ฟังก์ชัน/CLI จริงและ TemporaryDirectory; fingerprint ใช้ Git sandbox จริง; gate missing-receipt ใช้คำสั่งจริงหนึ่ง check ไม่มี mocks ไม่มี network และไม่มี temp commits ผลละเอียดบันทึกด้านบน การทดลองเหล่านี้ยืนยันพฤติกรรมเดิม ไม่ใช่ regression tests ของการแก้ที่ยังไม่ได้ทำ

ผล deterministic validation, review และ shared gate ของ **ชุดเอกสารนี้** บันทึกใน Evidence ของ TCK018 เพื่อให้ closure record อัปเดตได้โดยไม่ปะปนกับข้อค้นพบ ไม่อ้างว่า report gate ครอบ browser หรือ full gate Casetodian และไม่อ้างว่าประวัติ receipt ทั้งหมดถูก replay แล้ว
