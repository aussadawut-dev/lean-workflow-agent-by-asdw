The endpoint is `/api/v1/me/navigation-pins`. Its explicit application methods are **GET, PUT, and DELETE**, mounted under `/api/v1`; POST/PATCH handlers are absent. Framework-generated HEAD/OPTIONS behavior was not verified. `application/apps/api/src/app.ts:401`, `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`.

- **GET** returns `200 {"pins":null}` or `200 {"pins":[...]}`.
- **PUT** accepts `{"pins":[...]}`, replaces the entire saved list while preserving order, and returns it with 200.
- **DELETE** removes the saved preference and returns `200 {"pins":null}`; reset is idempotent.

All three pass `scopedPrincipal.userId` to persistence, so they read/change the authenticated local member, not a member supplied in the request. Repository operations also constrain the member to the current workspace. `application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`.

**`null` and `[]` have different meanings.** `pins:null` means no customization exists and role defaults apply; the API returns that marker rather than computing defaults. `pins:[]` is a saved customization containing zero pins. PUT rejects `null`; DELETE restores the uncustomized state by deleting the preference row. `application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:29`.

**PUT validation:** `pins` is required and must be an array of **0–8 unique identifiers**, chosen exactly from:

`kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`.

Unknown identifiers and duplicates are rejected. The request object is strict: extra properties, including `userId` and `workspaceId`, are rejected. The response schema allows a nullable list but lacks the request schema’s `.strict()`. `application/packages/contracts/src/navigation-pins.ts:3`.

**Errors and access:** malformed JSON or any invalid PUT body produces `400 {"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}` before replacement. The server use case independently validates pins and can raise `400 INVALID_PINS` / `"Pins are invalid"`. Replacement raises `404 NOT_FOUND` / `"Member was not found"` when the member is absent from the current workspace. GET instead returns null for a missing preference; DELETE succeeds even when no matching preference exists. Domain errors retain their status and `{error:{code,message}}` shape. `application/apps/api/src/modules/users/navigation-pins.controller.ts:8`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`.

Shared middleware requires authentication, applies `profile.read` to GET and `profile.manage` to mutations, and checks workspace writability for PUT/DELETE. Thus the four roles exercised by tests do not imply unconditional authorization. Unhandled errors receive a generic JSON 500. `application/packages/contracts/src/access-routes.ts:6`, `application/apps/api/src/app.ts:270`, `application/apps/api/src/app.ts:416`.

**Test evidence inspected, not executed:**

- HTTP tests mock persistence and assert unauthenticated 401s, caller targeting, four-role PUT success, empty lists, invalid-body rejection without writes, reset, and mapped 404s. `application/apps/api/src/routes/navigation-pins.test.ts:22`.
- Schema tests cover identifiers, eight-item limits, duplicates, extra fields, and null responses. `application/packages/contracts/src/navigation-pins.test.ts:5`.
- Database-backed test source covers replacement/order, empty lists, idempotent reset, member/workspace isolation, and filtering obsolete/duplicate stored values. `application/packages/server/src/navigation-pins.test.ts:29`.

No tests, builds, installs, gate, database or network operations were executed. These are source-based findings, not runtime or deployed-behavior verification.
