Source indicates the Gmail OAuth/API connector is removed, while ordinary SMTP remains available. All paths below are relative to `application/`.

The removal test enumerates five HTTP method/path pairs:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

The test constructs an app with a fake authenticated workspace administrator and expects **404** for each request (`application/apps/api/src/routes/gmail-removed.test.ts#L5`). Implementation inspection found no corresponding Gmail route registration; the app registers connector routes and supplies a JSON `NOT_FOUND` fallback (`application/apps/api/src/app.ts#L347`, `application/apps/api/src/app.ts#L431`). Ordinary `PATCH …/SMTP/config` and `POST …/SMTP/test-email` handlers remain (`application/apps/api/src/modules/connectors/connector-settings.controller.ts#L189`).

The stored-secret cleanup is exactly:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

This is a **field-only predicate**, with no workspace or connector-type restriction. It deletes exact `gmail-settings` and `gmail-grant` fields plus every field beginning `gmail-state:`; SQL `%` also permits an empty suffix. Other field names are preserved, including `smtpPassword` and `emailApiKey`. This migration contains no connector-row deletion or configuration rewrite (`application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql#L1`).

The cleanup test inserts those two exact Gmail fields, two state fields, `smtpPassword`, and `emailApiKey`, all under connector type `AI`; it applies the migration SQL and expects only the latter two fields to remain (`application/prisma/gmail-secret-cleanup.test.ts#L13`). That test covers one workspace and those six examples; the broader cross-workspace/type conclusion follows from the SQL itself.

For ordinary `smtp.gmail.com` configuration, **`GMAIL_API_ENABLED=1` does not select Gmail API delivery**. Stored transport defaults to SMTP unless `mailTransport` is exactly `"API"` (`application/packages/server/src/modules/connectors/connector-settings.service.ts#L194`). SMTP settings retrieve `smtpPassword` and return configuration without `emailApi`; explicit API transport separately retrieves `emailApiKey` (`application/packages/server/src/modules/connectors/smtp-settings.usecases.ts#L16`).

At send time, only `config.emailApi` selects HTTP API delivery. Otherwise, the implementation validates SMTP configuration, rejects a username without a password, resolves the host, opens a socket, negotiates TLS as configured, and authenticates using SMTP `AUTH PLAIN` or `AUTH LOGIN` (`application/packages/server/src/infrastructure/providers/smtp-client.ts#L183`).

The Gmail-host test sets `GMAIL_API_ENABLED=1`, uses `smtp.gmail.com:587` with STARTTLS and a username, passes no password, and expects `SMTP_PASSWORD_MISSING` with no `fetch` call (`application/packages/server/src/smtp-gmail-host.test.ts#L4`). Separate tests specify SMTP mode without `emailApi` despite a stored API key, and a successful fake-server STARTTLS/password exchange (`application/packages/server/src/email-api-connector.test.ts#L110`, `application/packages/server/src/smtp-connector.test.ts#L673`).

These are source conclusions and inspected test expectations. I executed no tests, migration, build, gate, database access, or provider calls. Actual migration application, deployed routing, and successful Gmail SMTP delivery remain unverified.
