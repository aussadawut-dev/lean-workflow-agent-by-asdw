The endpoint is `/api/v1/me/navigation-pins`, mounted under `/api/v1` in `application/apps/api/src/app.ts#L401`.

| Method | Behavior | Successful response |
|---|---|---|
| GET | Reads the caller’s saved pins | `200 {"pins": null}` or `200 {"pins": [...]}` |
| PUT | Replaces the entire ordered list using `{"pins":[...]}` | `200 {"pins":[...]}` |
| DELETE | Removes the saved preference; repeated resets are idempotent | `200 {"pins":null}` |

These three handlers are explicitly registered in `application/apps/api/src/modules/users/navigation-pins.controller.ts#L5`. There is no explicit POST/PATCH handler; implicit HEAD/OPTIONS behavior was not verified.

**Which member?** Every handler uses `scopedPrincipal.userId`, never a body-supplied member ID (`application/apps/api/src/modules/users/navigation-pins.controller.ts#L7`). The repository scopes reads/deletes to the current workspace and requires workspace membership before upsert (`application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts#L7`). Shared middleware requires scoped authentication without requiring project membership (`application/apps/api/src/app.ts#L245`); `/me/*` maps to `profile.read` for reads and `profile.manage` for mutations (`application/packages/contracts/src/access-routes.ts#L6`). PUT tests exercise VIEWER, AGENT, ADMIN, and PLATFORM_ADMIN, but that does not bypass shared policy or workspace writability checks (`application/apps/api/src/routes/navigation-pins.test.ts#L38`, `application/apps/api/src/app.ts#L270`).

**`null` versus `[]`.** `pins:null` means no customization, so role defaults apply; the HTTP response does not expand those defaults (`application/packages/contracts/src/navigation-pins.ts#L17`). DELETE removes the row and returns null. `pins:[]` is a saved, explicitly empty customization. PUT rejects null. Replacement preserves order and overwrites previous values (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L17`, `application/packages/server/src/navigation-pins.test.ts#L29`, `application/packages/server/src/navigation-pins.test.ts#L49`).

**Validation.** Allowed identifiers are exactly `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, and `knowledge`. Lists contain **0–8 unique identifiers**. PUT requires `pins`, rejects non-arrays/null, unknown identifiers, duplicates, and extra properties—including `userId` or `workspaceId`. The update object is strict; the response schema is not explicitly strict (`application/packages/contracts/src/navigation-pins.ts#L3`). GET also sanitizes existing stored values: drops unknown IDs, removes duplicates, and keeps at most eight valid entries in encountered order (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L6`).

**Errors and test evidence.**

- Malformed JSON or invalid PUT bodies return `400`, `{"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}`; HTTP tests assert rejection before replacement (`application/apps/api/src/modules/users/navigation-pins.controller.ts#L11`, `application/apps/api/src/routes/navigation-pins.test.ts#L48`).
- Internal replacement validation throws `INVALID_PINS`/400; missing workspace member yields `NOT_FOUND`/404, `"Member was not found"` (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts#L17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts#L1`, `application/apps/api/src/routes/navigation-pins.test.ts#L82`).
- Missing/foreign members do **not** necessarily produce 404 on GET/DELETE: absent reads return null; deletes are no-ops. Persistence tests encode cross-workspace isolation (`application/packages/server/src/navigation-pins.test.ts#L79`).
- Tests assert unauthenticated GET/PUT/DELETE return 401 without calling persistence (`application/apps/api/src/routes/navigation-pins.test.ts#L22`). Unexpected handler errors reach the shared JSON 500 fallback (`application/apps/api/src/app.ts#L416`).

This is source evidence only. I executed no tests, builds, installs, full gate, database or network operations. Test passage, deployed behavior, and framework-specific method handling remain unverified; navigation UI/default rendering was outside scope.
