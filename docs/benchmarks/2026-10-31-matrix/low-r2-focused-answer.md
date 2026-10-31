The endpoint is **`/api/v1/me/navigation-pins`**. The controller explicitly registers **GET, PUT, and DELETE**, mounted under `/api/v1`. Other methods are not explicitly defined here; framework behavior such as implicit HEAD handling was not verified. `application/apps/api/src/modules/users/navigation-pins.controller.ts#L5`, `application/apps/api/src/app.ts#L401`.

- **GET** reads the caller’s preference.
- **PUT** replaces the entire ordered list with `{ "pins": [...] }`.
- **DELETE** removes the saved preference and returns `{ "pins": null }`.

Successful responses contain `{ pins: ... }`; HTTP tests expect **200** for each operation. `application/apps/api/src/routes/navigation-pins.test.ts#L31`.

Every operation uses **`scopedPrincipal.userId`**, not a body-supplied member ID. Authentication resolves that principal, rejects mismatched workspaces, and establishes workspace context. The repository additionally scopes reads/deletes by workspace and checks membership before upsert. `application/apps/api/src/modules/users/navigation-pins.controller.ts#L7`, `application/packages/mcp-runtime/src/auth.ts#L78`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts#L7`. HTTP tests assert the trusted member is used and reject attempts to target another member. `application/apps/api/src/routes/navigation-pins.test.ts#L68`.

**`null` and `[]` have different meanings.** `pins:null` means no customization, so role defaults apply; DELETE restores that state. `pins:[]` is a saved customization containing zero pins. PUT does **not** accept `null`. Persistence tests assert empty-list retention and idempotent reset with row removal. `application/packages/contracts/src/navigation-pins.ts#L14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L17`, `application/packages/server/src/navigation-pins.test.ts#L29`.

**Input rules:** `pins` is required and must be an array of **0–8 unique identifiers**, preserving submitted order. Allowed identifiers are exactly:

`kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`.

Unknown IDs, duplicates, and **any extra top-level properties** are rejected by the strict update schema—including `userId` and `workspaceId`. `application/packages/contracts/src/navigation-pins.ts#L3`. Contract tests cover eight accepted entries, nine distinct entries rejected, duplicates, unknown/core IDs, missing pins, and extra fields. `application/packages/contracts/src/navigation-pins.test.ts#L5`.

GET defensively filters stored unknown IDs, removes duplicates, and caps the result at eight, retaining first-occurrence order. A stored list that filters to nothing produces `[]`, not `null`. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L6`. A persistence test asserts filtering/deduplication. `application/packages/server/src/navigation-pins.test.ts#L59`.

**Errors and evidence:**

- Malformed JSON or invalid PUT bodies → **400**, `{error:{code:"INVALID_BODY",message:"Request body is invalid"}}`; HTTP tests assert rejected bodies never call replacement. `application/apps/api/src/modules/users/navigation-pins.controller.ts#L10`, `application/apps/api/src/routes/navigation-pins.test.ts#L48`.
- Missing member on replacement → **404 `NOT_FOUND`**, `"Member was not found"`. Internal replacement validation uses **400 `INVALID_PINS`**. GET with no matching preference returns null; DELETE remains idempotent. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L6`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts#L1`, `application/apps/api/src/routes/navigation-pins.test.ts#L82`.
- Missing authentication → **401**, tested for all three methods. PUT succeeds for all four roles in tests, but shared profile permissions and workspace-write restrictions still apply. Unexpected errors become **500 `INTERNAL_ERROR`**. `application/apps/api/src/routes/navigation-pins.test.ts#L22`, `application/packages/contracts/src/access-routes.ts#L6`, `application/apps/api/src/app.ts#L270`, `application/apps/api/src/app.ts#L416`.

This is source/test inspection only: **no tests, builds, installs, full gate, database, network, or providers were executed/accessed**. HTTP tests mock persistence; their assertions are not evidence of a passing run or deployed behavior.
