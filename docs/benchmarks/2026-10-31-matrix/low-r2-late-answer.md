The endpoint is **`/api/v1/me/navigation-pins`**. Its explicitly registered methods are GET, PUT, and DELETE (`application/apps/api/src/app.ts:401`; `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`).

| Method | Behavior | Successful response |
|---|---|---|
| GET | Reads the caller’s saved pins | `200 {"pins": null}` or `200 {"pins": [...]}` |
| PUT | Replaces the complete list, preserving supplied order | `200 {"pins": [...]}` |
| DELETE | Removes the saved customization; repeated resets are idempotent | `200 {"pins": null}` |

These behaviors follow from the `application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, and persistence test assertions for ordering, replacement, empty lists, and reset (`application/packages/server/src/navigation-pins.test.ts:29`). This establishes the explicit registrations, not framework-generated HEAD/OPTIONS behavior.

**Which member:** Every handler passes `c.get("scopedPrincipal").userId`; none accepts a target member ID. The repository additionally scopes reads/removals to the current workspace and checks membership before upserting (`application/apps/api/src/modules/users/navigation-pins.controller.ts:7`; `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`). HTTP tests assert caller selection and reject a body containing another `userId` (`application/apps/api/src/routes/navigation-pins.test.ts:68`).

**`null` versus `[]`:**

- `pins: null` means no customization exists, so role defaults apply. GET returns this when no preference row exists; DELETE restores it.
- `pins: []` is an explicitly saved empty customization.
- PUT rejects `pins: null`; resetting uses DELETE.

See `application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, and `application/apps/api/src/routes/navigation-pins.test.ts:48`. The API returns the null sentinel; these sources do not demonstrate how a UI renders defaults.

**Validation:** PUT requires exactly `{ "pins": [...] }`. Allowed identifiers are `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, and `knowledge`. Lists contain **0–8 unique identifiers**. Missing `pins`, wrong types, unknown IDs, duplicates, and any extra properties—including `userId` or `workspaceId`—are rejected. The response permits null but otherwise uses the same list constraints; its object schema does not declare `.strict()` (`application/packages/contracts/src/navigation-pins.ts:3`). Contract tests separately cover eight accepted entries, all nine rejected, empty lists, duplicates, and extra fields (`application/packages/contracts/src/navigation-pins.test.ts:5`).

GET also sanitizes stored lists: it drops invalid identifiers and duplicates and retains at most eight valid entries in stored order (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`; `application/packages/server/src/navigation-pins.test.ts:59`).

**Errors and evidence:** Malformed JSON or invalid PUT data returns `400 {"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}` before replacement. Domain errors preserve their status/code/message: missing-member PUT produces `404 NOT_FOUND`; direct use-case validation produces `400 INVALID_PINS` (`application/apps/api/src/modules/users/navigation-pins.controller.ts:10`; `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`; `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`). HTTP tests assert unauthenticated requests receive 401, successful PUT for four roles, invalid requests make no writes, and the 404 body (`application/apps/api/src/routes/navigation-pins.test.ts:22`). Shared workspace entitlement middleware can also reject requests; unrecognized exceptions map to generic 500 responses (`application/apps/api/src/app.ts:270`, `application/apps/api/src/app.ts:416`).

**Limitations:** This was source inspection only. No tests, builds, installs, database operations, or full gate were executed. HTTP tests mock persistence and inject authentication (`application/apps/api/src/routes/navigation-pins.test.ts:3`); their assertions do not establish deployed authentication or database behavior. Shared authorization/entitlement internals were not exhaustively audited.
