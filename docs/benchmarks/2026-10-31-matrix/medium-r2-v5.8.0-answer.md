The inspected source removes the Gmail OAuth/API connector while retaining ordinary SMTP, including `smtp.gmail.com`.

**Removed HTTP endpoints**

The removal test enumerates five method/path pairs and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

Evidence: `application/apps/api/src/routes/gmail-removed.test.ts:5`. These assertions use a fake authenticated ADMIN. The application mounts connector routes at `/api/v1` and supplies a JSON `NOT_FOUND` fallback: `application/apps/api/src/app.ts:347`, `application/apps/api/src/app.ts:401`. Ordinary SMTP configuration and test-email handlers remain: `application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`.

**Exact stored-secret cleanup**

The migration contains:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus it deletes whole secret rows whose field exactly matches either named value or starts with `gmail-state:`; `%` also permits an empty suffix. There is **no workspace or connector-type restriction**. Other field values—including `smtpPassword` and `emailApiKey`—do not match and are preserved by this statement. It contains no connector-configuration update or provider-token revocation operation. `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:1`

The database-backed test inserts the two exact Gmail fields, two state fields, `smtpPassword`, and `emailApiKey`, all under connector type `AI`; after applying the SQL, it expects only the latter two. Coverage is one workspace and those six values, not every predicate boundary or connector type. `application/prisma/gmail-secret-cleanup.test.ts:13`

**Ordinary `smtp.gmail.com` behavior**

`sendSmtpMessage` chooses HTTP email delivery only when `config.emailApi` is explicitly present. Otherwise it validates SMTP configuration, rejects a configured username without a password with `SMTP_PASSWORD_MISSING`, resolves the host, establishes SMTP/TLS, and authenticates using PLAIN or LOGIN. There is no Gmail-host or `GMAIL_API_ENABLED` branch in this implementation. `application/packages/server/src/infrastructure/providers/smtp-client.ts:183`

The dedicated test sets `GMAIL_API_ENABLED=1`, supplies `smtp.gmail.com:587` with STARTTLS and a username but no password, and asserts that error plus zero `fetch` calls. It covers early rejection, **not a successful Gmail SMTP session**. `application/packages/server/src/smtp-gmail-host.test.ts:4`

These are source conclusions and unexecuted test assertions. I ran no tests, migration, build, or gate and accessed no database or providers. Deployment status, actual cleanup, live endpoint responses, and successful Gmail delivery remain unverified.
