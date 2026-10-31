The endpoint is `/api/v1/me/navigation-pins`, with three registered methods:

| Method | Behavior | Successful response |
|---|---|---|
| `GET` | Reads the caller’s saved pins | `{"pins":null}` or `{"pins":[...]}` |
| `PUT` | Replaces the entire list, preserving submitted order | `{"pins":[...]}` |
| `DELETE` | Removes the saved preference, restoring the uncustomized state | `{"pins":null}` |

All handlers pass `c.get("scopedPrincipal").userId` to the use case; there is no member selector in the route. Responses are parsed through `NavigationPinsSchema`. See `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`. HTTP tests use the full URL, assert the `"trusted-member"` argument, and exercise PUT for VIEWER, AGENT, ADMIN, and PLATFORM_ADMIN (`application/apps/api/src/routes/navigation-pins.test.ts:31`, `application/apps/api/src/routes/navigation-pins.test.ts:75`).

**`null` versus `[]`.** `pins:null` means the member has not customized pins, so role defaults apply; GET returns this when no preference row exists. `pins:[]` is a valid, explicitly saved empty customization. PUT cannot accept `null`; DELETE removes the row and returns `null`. See `application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, and `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`. Persistence tests assert empty-list round trips, overwrite behavior, and idempotent reset (`application/packages/server/src/navigation-pins.test.ts:29`). The actual UI application of role defaults was not inspected.

**PUT validation.** The JSON body must be a strict object containing the required `pins` array:

- Allowed identifiers: `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`.
- Zero through eight entries; duplicates are rejected.
- Unknown identifiers, non-array values, `null`, missing `pins`, and extra properties—including `userId` or `workspaceId`—are rejected.

These rules come from `application/packages/contracts/src/navigation-pins.ts:3`. Schema tests independently cover eight accepted entries, all nine unique identifiers exceeding the limit, duplicates, unknown IDs, missing fields, and extra fields (`application/packages/contracts/src/navigation-pins.test.ts:5`). The HTTP oversized fixture also contains a duplicate, so that fixture alone does not isolate count validation (`application/apps/api/src/routes/navigation-pins.test.ts:48`).

GET tolerates stale stored data: it drops invalid identifiers, removes duplicates, and caps output at eight while preserving retained order (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`). A persistence test asserts stale-value filtering and deduplication (`application/packages/server/src/navigation-pins.test.ts:59`).

**Errors and evidence.** Malformed JSON or schema-invalid PUT bodies return HTTP 400 with `{"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}` before replacement (`application/apps/api/src/modules/users/navigation-pins.controller.ts:10`). The use case additionally rejects invalid lists as `INVALID_PINS`/400 and failed member lookup as `NOT_FOUND`/404; the latter message is `"Member was not found"` (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:17`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`). HTTP tests assert unauthenticated 401 without persistence calls and the missing-member 404 envelope (`application/apps/api/src/routes/navigation-pins.test.ts:22`, `application/apps/api/src/routes/navigation-pins.test.ts:82`). Unrecognized exceptions reach the shared error handler (`application/apps/api/src/app.ts:416`).

This was source inspection only. No tests, build, install, full gate, database, network, or providers were executed. HTTP tests mock the pin use cases; shared authentication/authorization and deployed behavior were not independently verified.
