The source removes Gmail OAuth/API routes while retaining ordinary SMTP, including `smtp.gmail.com`.

**Removed HTTP endpoints**

The regression test enumerates these five method/path pairs and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

Evidence: `application/apps/api/src/routes/gmail-removed.test.ts:11`. The app registers connector settings at `app.ts:347`; the inspected controller has no Gmail handlers, retains SMTP configuration/test-email handlers at lines 189–228, and the app supplies a general 404 fallback at `application/apps/api/src/app.ts:431`.

The test uses stubbed authentication/resolution (lines 4–9). It does **not** establish that every unauthenticated or middleware-rejected request returns 404.

**Exact stored-secret cleanup and preservation**

The migration contains:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus, it deletes exact `gmail-settings` and `gmail-grant` fields, plus fields beginning `gmail-state:`; `%` also permits an empty suffix. There is **no workspace or connector-type restriction**, so matching rows are selected across both. Nonmatching secret fields are preserved; this statement does not alter other tables. `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:1`

The database test seeds `gmail-settings`, `gmail-grant`, two `gmail-state:` entries, `smtpPassword`, and `emailApiKey`, all under connector type **AI**. After executing the migration SQL, it expects exactly `emailApiKey` and `smtpPassword` to remain. This supports field-based cleanup independent of SMTP connector type, but the fixture covers only one workspace and those six field values. `application/prisma/gmail-secret-cleanup.test.ts:14`

**Ordinary `smtp.gmail.com` behavior**

`sendSmtpMessage` contains no Gmail-host or `GMAIL_API_ENABLED` switch. Without explicit `config.emailApi`, it validates SMTP configuration, requires a password when a username is supplied, resolves the host, opens SMTP/TLS sockets, and authenticates through SMTP. An explicit `emailApi` configuration remains a separate dispatch branch. `application/packages/server/src/infrastructure/providers/smtp-client.ts:183`

The focused test configures `smtp.gmail.com:587` with STARTTLS, sets `GMAIL_API_ENABLED=1`, supplies a null password, and expects `SMTP_PASSWORD_MISSING` with **no `fetch` call**. It checks this early rejection, not successful Gmail delivery or the complete authenticated SMTP session. `application/packages/server/src/smtp-gmail-host.test.ts:4`

These are source conclusions and test assertions. I executed no tests or migration and accessed no database or provider; deployment status, actual cleanup, and live delivery remain unverified.
