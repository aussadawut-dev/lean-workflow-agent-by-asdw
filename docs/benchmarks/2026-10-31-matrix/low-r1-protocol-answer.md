The endpoint is **`/api/v1/me/navigation-pins`**. The app registers the controller on its versioned router (`application/apps/api/src/app.ts:360`, `application/apps/api/src/app.ts:401`).

| Method | Contract |
|---|---|
| **GET** | Returns `{ "pins": null }` or `{ "pins": [...] }` for the authenticated member. |
| **PUT** | Accepts `{ "pins": [...] }`, replaces the entire saved list, and returns it in the same shape. |
| **DELETE** | Removes the saved customization and returns `{ "pins": null }`. Reset is idempotent. |

These are the three explicitly registered methods; this investigation does not establish framework behavior for HEAD, OPTIONS, or unsupported methods. Each handler uses **`scopedPrincipal.userId`**, never a caller-supplied member ID (`application/apps/api/src/modules/users/navigation-pins.controller.ts:6`). Replacement and reset semantics follow the `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`.

**`null` and `[]` differ.** Response `pins: null` means the member has not customized pins, so role defaults apply (`application/packages/contracts/src/navigation-pins.ts:17`). `pins: []` is a saved, explicitly empty selection; persistence tests assert it survives a subsequent read (`application/packages/server/src/navigation-pins.test.ts:29`). PUT rejects `null`; use DELETE to restore the uncustomized state. The endpoint returns `null` rather than computing role defaults itself.

**PUT validation:**

- Allowed identifiers: `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`.
- Between **0 and 8** identifiers; each must be unique. Order is retained.
- `pins` is required and must be an array. Unknown identifiers, duplicates, and extra top-level properties—including `userId` and `workspaceId`—are rejected.

These rules come from the `application/packages/contracts/src/navigation-pins.ts:3`. Contract tests cover empty lists, eight-item acceptance, nine-item rejection, duplicates, unknown IDs, missing `pins`, and extra fields (`application/packages/contracts/src/navigation-pins.test.ts:5`).

**Errors and evidence.** Malformed JSON or schema-invalid PUT bodies return HTTP **400** with `{"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}`, before replacement (`application/apps/api/src/modules/users/navigation-pins.controller.ts:11`); HTTP tests assert rejection without writing (`application/apps/api/src/routes/navigation-pins.test.ts:48`). The use case independently rejects invalid lists with `INVALID_PINS`/400, and returns `NOT_FOUND`/404 when replacement cannot find the member in the current workspace (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:14`). Error messages are defined in the `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`; the HTTP 404 mapping is `application/apps/api/src/routes/navigation-pins.test.ts:82`.

HTTP tests assert unauthenticated requests receive 401, caller-ID selection, successful replacement for all four listed roles, and DELETE returning 200/null (`application/apps/api/src/routes/navigation-pins.test.ts:22`, `application/apps/api/src/routes/navigation-pins.test.ts:75`). GET also filters obsolete stored IDs, removes duplicates, and caps results at eight (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`); persistence tests cover filtering and idempotent reset (`application/packages/server/src/navigation-pins.test.ts:49`).

**Limits:** This was source inspection only. No tests, builds, installs, full gate, database, network, or provider calls were executed; no product files changed. HTTP tests mock the use cases. Shared authentication, permission, and entitlement middleware remains an access dependency (`application/apps/api/src/app.ts:244`); its complete behavior and deployed configuration were not audited.
