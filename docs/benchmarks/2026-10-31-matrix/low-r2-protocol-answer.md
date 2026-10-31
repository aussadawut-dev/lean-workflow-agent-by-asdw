██████████████░░░░░░ 71% review — Check source evidence and limitations

The endpoint is **`/api/v1/me/navigation-pins`**. The controller explicitly registers **GET, PUT, and DELETE**, mounted under `/api/v1`. All three use `scopedPrincipal.userId`, selecting the authenticated caller rather than a client-supplied member ID. See `application/apps/api/src/modules/users/navigation-pins.controller.ts:5` and `application/apps/api/src/app.ts:401`.

- **GET** returns `{ pins: null }` or `{ pins: [...] }`.
- **PUT** accepts `{ pins: [...] }`, replaces the entire saved list, and returns it in the supplied order.
- **DELETE** removes the saved preference and returns `{ pins: null }`; the implementation is idempotent.

These behaviors follow from the `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6` and `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`. Successful HTTP responses are asserted as **200** in `application/apps/api/src/routes/navigation-pins.test.ts:31` and `application/apps/api/src/routes/navigation-pins.test.ts:75`.

**`pins: null` means “not customized; role defaults apply.”** It is a response state, not a valid PUT value. **`pins: []` is an explicitly saved empty customization**, distinct from resetting to defaults. See `application/packages/contracts/src/navigation-pins.ts:14`, `application/packages/server/src/navigation-pins.test.ts:29`, and `application/packages/server/src/navigation-pins.test.ts:49`. Actual UI/default rendering was outside this investigation.

PUT validation requires:

- Exactly the required `pins` property, containing an array.
- **0–8** identifiers, with no duplicates.
- Identifiers drawn from **`kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, `knowledge`**.
- No extra properties, including `userId` or `workspaceId`.

These rules are explicit in `application/packages/contracts/src/navigation-pins.ts:3`. Contract tests cover empty lists, `knowledge`, eight accepted identifiers, rejection of all nine identifiers, duplicates, unknown identifiers, missing `pins`, and extra fields: `application/packages/contracts/src/navigation-pins.test.ts:5`.

Malformed JSON or schema-invalid PUT bodies return **400** with:
`{"error":{"code":"INVALID_BODY","message":"Request body is invalid"}}`.
Validation happens before the replacement call. `application/apps/api/src/modules/users/navigation-pins.controller.ts:10` and `application/apps/api/src/routes/navigation-pins.test.ts:48` establish this.

The use case independently rejects invalid lists as **`INVALID_PINS`, 400, “Pins are invalid”**. Replacement returns **`NOT_FOUND`, 404, “Member was not found”** when repository membership lookup fails. GET returns `null` for no matching preference; DELETE does not require a matching row. See `application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/modules/navigation-pins/navigation-pins.service.ts:1`, and `application/apps/api/src/routes/navigation-pins.test.ts:82`. Unexpected errors reach the shared `application/apps/api/src/app.ts:416`.

GET also filters obsolete stored IDs, removes duplicates, and caps results at eight, preserving encounter order; filtering has a `application/packages/server/src/navigation-pins.test.ts:59`.

**Evidence limits:** HTTP tests mock persistence and assert unauthenticated 401s, caller-ID selection, and successful PUTs for four roles (`application/apps/api/src/routes/navigation-pins.test.ts:8`). Shared auth and workspace entitlement middleware remain dependencies (`application/apps/api/src/app.ts:245`); this is not a complete authorization audit. Framework handling of other methods was not established. Tests were **read, not executed**; no build, install, full gate, database, network, or deployed behavior was exercised, and no product files were edited.
