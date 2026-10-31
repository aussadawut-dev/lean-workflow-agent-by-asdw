The endpoint is `/api/v1/me/navigation-pins`. Its explicitly registered methods are **GET, PUT, and DELETE**; the registrar mounts under `/api/v1`. (`application/apps/api/src/modules/users/navigation-pins.controller.ts:5`, `application/apps/api/src/app.ts:401`)

| Method | Behavior | Successful JSON |
|---|---|---|
| GET | Reads the caller’s saved pins | `{"pins":null}` or `{"pins":[…]}` |
| PUT | Replaces the complete list, preserving submitted order | `{"pins":[…]}` |
| DELETE | Removes the saved preference, restoring the uncustomized state | `{"pins":null}` |

The controller parses every successful response through `NavigationPinsSchema`. HTTP tests assert status **200** for all three operations. (`application/apps/api/src/modules/users/navigation-pins.controller.ts:6`, `application/apps/api/src/routes/navigation-pins.test.ts:31`, `application/apps/api/src/routes/navigation-pins.test.ts:75`)

**Which member:** every handler passes `c.get("scopedPrincipal").userId` to its server function. PUT accepts no member/workspace selector: extra properties such as `userId` or `workspaceId` invalidate the body. Tests assert use of `"trusted-member"`, reject another member’s ID, and exercise PUT for `VIEWER`, `AGENT`, `ADMIN`, and `PLATFORM_ADMIN`. This establishes handler behavior, relying on shared middleware to resolve the principal. (`application/apps/api/src/modules/users/navigation-pins.controller.ts:7`, `application/apps/api/src/routes/navigation-pins.test.ts:38`)

**`null` versus `[]`:** `pins:null` means the member has not customized pins, so role defaults apply; the response does not expand those defaults. `pins:[]` is a saved, explicitly empty customization. PUT rejects `null`; DELETE resets to `null` by removing the preference. Persistence tests assert empty-list round trips and idempotent reset. (`application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/navigation-pins.test.ts:29`)

**PUT body rules:** the body must be a strict object containing required `pins`, an array of **0–8 unique identifiers**. Allowed identifiers are exactly `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, and `knowledge`. Unknown IDs, duplicates, excess count, missing `pins`, nonarrays, and extra properties are rejected. Contract tests separately exercise eight valid entries and all nine allowed IDs, avoiding the HTTP test’s over-limit example also containing a duplicate. (`application/packages/contracts/src/navigation-pins.ts:3`, `application/packages/contracts/src/navigation-pins.test.ts:5`)

GET defensively filters stored unknown identifiers, removes duplicates, and caps the returned list at eight in first-seen order; this code does not rewrite storage. A persistence test asserts cleanup of retired IDs and duplicates. (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:59`)

**Errors and evidence:**

- Malformed JSON or invalid PUT body returns **400**, `{"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}`, before replacement. Tests assert rejection without calling replacement. (`application/apps/api/src/modules/users/navigation-pins.controller.ts:11`, `application/apps/api/src/routes/navigation-pins.test.ts:48`)
- Server validation can raise **400 `INVALID_PINS`**, “Pins are invalid”; replacement raises **404 `NOT_FOUND`**, “Member was not found,” when repository upsert reports no member. The controller maps these domain errors; an HTTP test covers the 404 body. (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`, `application/apps/api/src/routes/navigation-pins.test.ts:82`)
- HTTP tests assert unauthenticated GET/PUT/DELETE return **401** before server calls. Unexpected errors fall through to shared handling, including generic **500 `INTERNAL_ERROR`**. (`application/apps/api/src/routes/navigation-pins.test.ts:22`, `application/apps/api/src/app.ts:416`)

This was source inspection only. No tests, builds, installs, gate, database, or network operations were executed. HTTP tests mock server functions; persistence tests were only read. Shared authorization, deployed behavior, and unsupported-method responses were not independently verified.
