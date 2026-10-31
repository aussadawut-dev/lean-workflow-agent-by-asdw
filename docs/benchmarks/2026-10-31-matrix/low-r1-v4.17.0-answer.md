The endpoint is **`/api/v1/me/navigation-pins`**. Three methods are explicitly registered; successful responses are JSON with status 200:

| Method | Behavior |
|---|---|
| GET | Reads the caller’s saved pins. |
| PUT | Replaces the entire ordered list with `{ "pins": [...] }`. |
| DELETE | Removes the customization and returns `{ "pins": null }`; repeated resets are idempotent. |

See `application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/apps/api/src/app.ts:360`, `application/apps/api/src/app.ts:401`, and `application/apps/api/src/routes/navigation-pins.test.ts:31`. POST/PATCH are not registered here; framework-level HEAD/OPTIONS behavior was not verified.

**Which member:** all three handlers pass `scopedPrincipal.userId`, never a body-supplied member ID. Persistence additionally scopes reads/deletes to the current workspace and checks workspace membership before replacement. `application/apps/api/src/modules/users/navigation-pins.controller.ts:7`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`. Shared permissions classify GET as `profile.read` and mutations as `profile.manage`; HTTP test source exercises PUT for VIEWER, AGENT, ADMIN and PLATFORM_ADMIN. `application/packages/contracts/src/access-routes.ts:3`, `application/apps/api/src/routes/navigation-pins.test.ts:38`.

**`null` versus `[]`:**

- Response `pins: null` means no customization; role defaults apply. GET produces this when no preference row is found; DELETE removes that row.
- `pins: []` is an explicitly saved empty customization, retained as an empty list.
- PUT rejects `pins: null`; reset through DELETE.

Evidence: `application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:29`. Actual UI default selection/rendering was outside scope.

**Validation:** allowed identifiers are exactly `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`. Lists contain **0–8 unique identifiers**, preserving order. Nine identifiers exist, but all nine cannot be saved together. PUT requires a `pins` array and rejects extra top-level properties, including `userId` and `workspaceId`. `application/packages/contracts/src/navigation-pins.ts:3`. The response schema allows nullable pins and is not declared strict. GET also sanitizes stored lists: it drops unknown values and duplicates and retains at most eight valid entries, without writing that cleanup back. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`.

**Errors and test evidence:**

- Malformed JSON or invalid PUT shape returns **400**, `{error:{code:"INVALID_BODY",message:"Request body is invalid"}}`, before replacement. `application/apps/api/src/modules/users/navigation-pins.controller.ts:11`; `application/apps/api/src/routes/navigation-pins.test.ts:48`.
- Missing/wrong-workspace member on replacement produces **404 NOT_FOUND**, `"Member was not found"`. Direct use-case invalid input produces **400 INVALID_PINS**. `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`, `application/apps/api/src/routes/navigation-pins.test.ts:82`.
- Unauthenticated requests are asserted to return **401** without calling persistence. Shared authorization/entitlement middleware can also reject requests; unhandled errors map to **500 INTERNAL_ERROR**. `application/apps/api/src/routes/navigation-pins.test.ts:22`, `application/apps/api/src/app.ts:270`, `application/apps/api/src/app.ts:416`.

Contract tests cover limits, identifiers, duplicates, extras and null responses (`application/packages/contracts/src/navigation-pins.test.ts:5`); database-backed test source covers cleanup and member/workspace isolation (`application/packages/server/src/navigation-pins.test.ts:59`).

**Limitations:** source inspection only. No tests, builds, installs, full gate, database, network or provider operations were executed; test assertions above are unexecuted evidence, not passing results.
