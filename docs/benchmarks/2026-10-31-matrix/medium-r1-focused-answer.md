The inspected source removes five Gmail OAuth endpoints while retaining ordinary SMTP and other email API transports. All findings below are from source inspection; no tests were executed.

**Removed HTTP endpoints**

The route regression test enumerates these method/path combinations and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

The fixture supplies a fake authenticated ADMIN principal. See `application/apps/api/src/routes/gmail-removed.test.ts:4`, particularly lines 11–19.

Implementation inspection found no Gmail route registrations. Connector settings remain mounted under `/api/v1`, and unmatched requests have a JSON `NOT_FOUND` response with status 404: `application/apps/api/src/app.ts:347`, `application/apps/api/src/app.ts:401`, `application/apps/api/src/app.ts:431`. Ordinary SMTP configuration and test-email endpoints remain registered: `application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`.

**Exact stored-secret cleanup and preservation**

The migration contains this single statement:

```sql
DELETE FROM "connector_secrets" WHERE "field" IN ('gmail-settings', 'gmail-grant') OR "field" LIKE 'gmail-state:%';
```

See `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:2`.

It deletes entire secret rows whose field is exactly `gmail-settings` or `gmail-grant`, or begins with `gmail-state:`. `%` also permits an empty suffix. There is **no workspace or connector-type restriction**, so matching rows across all workspaces and connector types qualify. Nonmatching rows—including `smtpPassword` and `emailApiKey`—are preserved by this statement. It contains no modification to connector configuration or other tables.

The database-backed test inserts four matching Gmail fields plus `smtpPassword` and `emailApiKey`, all under connector type `AI`, executes the migration SQL, and expects only the latter two fields to remain: `application/prisma/gmail-secret-cleanup.test.ts:13`. Its fixture covers one workspace and two nonmatching field names, not every possible boundary case.

**Ordinary `smtp.gmail.com` behavior**

Transport selection defaults to SMTP unless stored `mailTransport` is explicitly `"API"`: `application/packages/server/src/modules/connectors/connector-settings.service.ts:194`. SMTP settings load the workspace’s `AI/smtpPassword` secret: `application/packages/server/src/modules/connectors/smtp-settings.usecases.ts:26`.

`sendSmtpMessage` selects HTTP delivery only through explicit `config.emailApi`. Otherwise, it checks SMTP configuration/password, resolves the host, opens a socket, negotiates TLS as configured, authenticates using PLAIN or LOGIN, and sends SMTP commands. There is no Gmail hostname or `GMAIL_API_ENABLED` branch: `application/packages/server/src/infrastructure/providers/smtp-client.ts:183`, `application/packages/server/src/infrastructure/providers/smtp-client.ts:217`.

The Gmail-specific test sets `GMAIL_API_ENABLED=1`, uses `smtp.gmail.com:587` with STARTTLS and a username, passes no password, and asserts `SMTP_PASSWORD_MISSING` with no fetch call: `application/packages/server/src/smtp-gmail-host.test.ts:4`. Thus the test exercises early rejection, not successful Gmail SMTP delivery.

These findings do not establish deployed endpoint responses, migration application, actual secret deletion, remote OAuth-token revocation, or Gmail delivery success. No database, provider, network, build, or gate was accessed.
