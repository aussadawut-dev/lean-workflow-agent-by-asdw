The endpoint is `/api/v1/me/navigation-pins`: the controller registers these operations under the `/api/v1` mount (`application/apps/api/src/app.ts:401`, `application/apps/api/src/modules/users/navigation-pins.controller.ts:5`).

| Method | Contract |
|---|---|
| GET | Reads the caller’s pins; returns `200` with `{pins: null}` or `{pins: [...]}`. |
| PUT | Requires `{pins: [...]}`; replaces the entire list, preserving order; returns `200` with that list. |
| DELETE | Removes the saved preference; returns `200` with `{pins: null}`. Reset is idempotent. |

These are the explicitly registered methods. The persistence tests assert replacement, ordering, empty-list storage, and repeated reset (`application/packages/server/src/navigation-pins.test.ts:29`). Framework handling of other methods was not verified.

Every operation uses `scopedPrincipal.userId`, never a member identifier supplied by the client. Repository reads/deletes also filter by the current workspace; writes first verify that the member belongs to it (`application/apps/api/src/modules/users/navigation-pins.controller.ts:7`, `application/packages/server/src/modules/navigation-pins/prisma-navigation-pins.repository.ts:7`). Shared authorization requires `profile.read` for GET and `profile.manage` for mutations; subject permissions can further restrict access (`application/packages/contracts/src/access-routes.ts:1`, `application/packages/server/src/modules/access/access.service.ts:23`).

`pins:null` means **uncustomized; role defaults apply**, rather than a concrete default list returned by this API. `pins:[]` is a saved customization containing zero pins. PUT rejects `null`; DELETE restores the uncustomized state (`application/packages/contracts/src/navigation-pins.ts:14`).

Allowed identifiers are exactly `kanban`, `workload`, `calendar`, `talk`, `meet`, `appointments`, `skills`, `settings`, and `knowledge`. Lists permit **0–8 unique identifiers**. PUT requires `pins` and rejects extra properties, including `userId` or `workspaceId`. Contract tests independently check eight accepted identifiers versus all nine, duplicates, unknown identifiers, missing pins, and extra fields (`application/packages/contracts/src/navigation-pins.ts:3`, `application/packages/contracts/src/navigation-pins.test.ts:5`).

Errors use `{error:{code,message}}`:

- Invalid PUT bodies, including malformed JSON, return `400 INVALID_BODY`, `"Request body is invalid"`, before replacement. HTTP tests assert these cases and no replacement call (`application/apps/api/src/routes/navigation-pins.test.ts:48`).
- Replacement of a missing/out-of-workspace member produces `404 NOT_FOUND`, `"Member was not found"`; direct use-case validation produces `400 INVALID_PINS`. GET without a matching preference returns null; DELETE remains successful (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`).
- Shared middleware can reject authentication/authorization or workspace entitlement; unexpected errors map to `500 INTERNAL_ERROR` (`application/packages/mcp-runtime/src/auth.ts:65`, `application/apps/api/src/app.ts:270`, `application/apps/api/src/app.ts:416`).

GET additionally filters obsolete stored identifiers, removes duplicates, and caps the returned list at eight; this sanitization does not write back. Tests cover obsolete identifiers and duplicates (`application/packages/server/src/modules/navigation-pins/usecases/navigation-pins.ts:6`, `application/packages/server/src/navigation-pins.test.ts:59`).

Evidence is source inspection only. HTTP tests mock the pins service and authentication dependencies; persistence tests require a database. No tests, builds, installs, full gate, network/provider/database calls, or deployed checks were executed. Runtime behavior and test pass status therefore remain unverified.
