The endpoint is **`/api/v1/me/navigation-pins`**. The controller registers three methods; `/api/v1` comes from the application mount. `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`, `application/apps/api/src/app.ts:401`.

| Method | Behavior | Successful response |
|---|---|---|
| GET | Reads the caller’s pins | 200 `{ "pins": null }` or an array |
| PUT | Replaces the entire ordered list | 200 `{ "pins": [...] }` |
| DELETE | Removes the saved preference; reset is idempotent | 200 `{ "pins": null }` |

Implementation: `application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`. These are the explicitly registered methods; framework behavior for HEAD/OPTIONS was not investigated.

**Which member:** every handler uses `scopedPrincipal.userId`, never a client-supplied member ID. Repository reads/deletes filter through the user’s current workspace; replacement first checks membership in that workspace. `application/apps/api/src/modules/users/navigation-pins.controller.ts:7`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`. Shared authorization maps GET to `profile.read` and mutations to `profile.manage`; additional subject-policy and workspace-writability checks apply. Consequently, the test covering all four roles is not an unconditional authorization guarantee. `application/packages/contracts/src/access-routes.ts:1`, `application/apps/api/src/app.ts:270`.

**`null` versus `[]`:**

- `pins: null` means “not customized; role defaults apply.” GET produces this when no preference row is found. DELETE removes the row and returns null; it does not return the resolved default list.
- `pins: []` is an explicitly saved empty customization.
- PUT **rejects** `{ "pins": null }`; use DELETE to reset.

`application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:29`. Actual UI application of role defaults was outside scope.

**Allowed input:** PUT requires exactly `{ "pins": [...] }`. Allowed identifiers are `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, and `knowledge`. Arrays may contain **0–8 unique identifiers**, in the supplied order. Duplicates, unknown identifiers, non-array values, missing `pins`, and extra top-level properties—including `userId` or `workspaceId`—are rejected. The response schema permits null and is not declared strict. `application/packages/contracts/src/navigation-pins.ts:3`.

GET sanitizes existing stored arrays: it drops unknown identifiers and duplicates, retains order, and caps the result at eight. This read path does not write the cleaned list back. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`.

**Errors and test evidence:**

- Invalid/malformed PUT bodies return **400** `{error:{code:"INVALID_BODY",message:"Request body is invalid"}}`; HTTP tests assert rejection without calling replacement. `application/apps/api/src/modules/users/navigation-pins.controller.ts:11`, `application/apps/api/src/routes/navigation-pins.test.ts:48`.
- Missing-workspace-member replacement returns **404 `NOT_FOUND`**, message `"Member was not found"`; direct use-case validation instead raises **400 `INVALID_PINS`**. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`, `application/apps/api/src/routes/navigation-pins.test.ts:82`.
- HTTP tests assert **401** without authentication for all three methods. `application/apps/api/src/routes/navigation-pins.test.ts:22`. Shared middleware can also reject requests; unexpected errors have a generic 500 fallback. `application/apps/api/src/app.ts:416`.
- Contract tests cover boundaries; database-backed tests assert persistence, sanitization, reset, and member/workspace isolation. `application/packages/contracts/src/navigation-pins.test.ts:5`, `application/packages/server/src/navigation-pins.test.ts:23`.

This is source evidence only. **No tests, build, install, full gate, database, network, or provider operations were executed.** HTTP tests mock the pins service; their assertions do not establish deployed behavior or current test success.
