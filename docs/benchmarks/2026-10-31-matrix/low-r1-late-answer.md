██████████████░░░░░░ 71% review — Check source evidence and limitations

The endpoint is **`/api/v1/me/navigation-pins`**. Its controller explicitly registers **GET, PUT, DELETE**; the app mounts it under `/api/v1`. No POST or PATCH handler is registered here; behavior for other methods was not exercised. `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`, `application/apps/api/src/app.ts:401`.

- **GET** reads the caller’s pins.
- **PUT** accepts `{ "pins": [...] }` and replaces the entire ordered list.
- **DELETE** removes the customization and returns `{ "pins": null }`; it does not parse a request body.

All three select the member using **`c.get("scopedPrincipal").userId`**, rather than a client-supplied member ID. HTTP tests assert this selection for each operation, successful 200 responses, and PUT access for VIEWER, AGENT, ADMIN and PLATFORM_ADMIN. `application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/apps/api/src/routes/navigation-pins.test.ts:31`, `application/apps/api/src/routes/navigation-pins.test.ts:75`.

**`null` versus `[]`:** Response `pins:null` means no customization, so role defaults apply; the API returns the sentinel rather than calculating those defaults. `pins:[]` is a saved, explicitly empty list. PUT rejects `null`; DELETE restores `null`. Persistence tests assert ordered replacement, saving `[]`, and idempotent reset that removes the preference row. `application/packages/contracts/src/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:29`.

**Allowed PUT body:**

- Required `pins` array containing **0–8 unique identifiers**, in the submitted order.
- Exact identifiers: `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`.
- Unknown identifiers, duplicates, missing `pins`, wrong types, and **any extra top-level properties** are rejected. Thus `userId` and `workspaceId` cannot redirect the operation.

These rules come from the enum, maximum, uniqueness refinement and strict request object. Contract tests cover empty lists, `knowledge`, eight accepted entries, nine rejected entries, unknown IDs, duplicates and extra fields. `application/packages/contracts/src/navigation-pins.ts:3`, `application/packages/contracts/src/navigation-pins.test.ts:5`.

**Errors and evidence:** Malformed JSON or invalid PUT data yields **400** with `{ "error": { "code": "INVALID_BODY", "message": "Request body is invalid" } }`; HTTP tests assert rejection without calling replacement. Unauthenticated GET/PUT/DELETE are expected to return **401** before persistence. `application/apps/api/src/modules/users/navigation-pins.controller.ts:10`, `application/apps/api/src/routes/navigation-pins.test.ts:22`, `application/apps/api/src/routes/navigation-pins.test.ts:48`.

The server independently validates replacements (`INVALID_PINS`, 400). A member absent from the current workspace produces `NOT_FOUND`, 404, “Member was not found”; the HTTP mapping has a mocked test. GET without a matching preference returns `null`, and reset tolerates no matching row. Reads also filter obsolete stored IDs, deduplicate and cap at eight. `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`, `application/apps/api/src/routes/navigation-pins.test.ts:82`.

**Limitations:** This was source inspection only. No tests, builds, installs, database calls or full gate ran. HTTP tests mock persistence and inject authentication resolution. Shared auth, permissions and entitlement middleware remain applicable and were not exhaustively audited; their wiring does not establish deployed safety. `application/apps/api/src/routes/navigation-pins.test.ts:3`, `application/apps/api/src/app.ts:244`.
