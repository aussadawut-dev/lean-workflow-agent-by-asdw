The inspected source removes the Gmail OAuth/API connector while retaining ordinary SMTP use of `smtp.gmail.com`.

**Removed HTTP endpoints**

The removal test enumerates these five method/path pairs and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

The fixture supplies a fake authenticated ADMIN; these are source-level test expectations, not observed responses. `application/apps/api/src/routes/gmail-removed.test.ts#L4`

Implementation inspection found no Gmail registration in the app or connector controller. Ordinary SMTP configuration and test-email handlers remain at `PATCH /settings/connectors/SMTP/config` and `POST /settings/connectors/SMTP/test-email`. The app provides a generic 404 fallback. `application/apps/api/src/modules/connectors/connector-settings.controller.ts#L189`, `application/apps/api/src/app.ts#L431`

**Exact stored-secret cleanup and preservation**

The migration contains one statement:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus deletion depends **only on `field`**: there is no workspace, connector-type, age, or ciphertext condition. The prefix pattern includes `gmail-state:` with an empty suffix. Nonmatching secret rows—including `smtpPassword` and `emailApiKey`—are outside this deletion predicate. The migration contains no update/delete of connector configuration or other tables. `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql#L1`

The relevant test creates six fields under one workspace and connector type `AI`, executes the migration SQL, and expects only `emailApiKey` and `smtpPassword` to remain. This expresses database-backed regression coverage, but I did **not** execute it; it does not explicitly exercise multiple workspaces/types or pattern edge cases. `application/prisma/gmail-secret-cleanup.test.ts#L13`

**Ordinary `smtp.gmail.com`, including `GMAIL_API_ENABLED=1`**

The sender has no Gmail-host or flag-specific branch. Without `config.emailApi`, it validates SMTP configuration, rejects a configured username without a password as `SMTP_PASSWORD_MISSING`, then applies outbound policy and opens an SMTP connection. STARTTLS and password-based `AUTH PLAIN`/`AUTH LOGIN` follow the ordinary SMTP implementation. `application/packages/server/src/infrastructure/providers/smtp-client.ts#L183`

The focused test sets `GMAIL_API_ENABLED=1`, configures `smtp.gmail.com:587` with STARTTLS and a username, supplies a null password, and expects that error with **no `fetch` call**. It covers early rejection, not successful Gmail SMTP delivery. `application/packages/server/src/smtp-gmail-host.test.ts#L4`

Explicit `config.emailApi` still selects the separate email-API transport; hostname and the Gmail flag do not select it. Stored transport selection likewise uses `mailTransport === "API"` and otherwise defaults to SMTP. `application/packages/server/src/infrastructure/providers/smtp-client.ts#L185`, `application/packages/server/src/modules/connectors/connector-settings.service.ts#L194`

**Uncertainty:** These conclusions describe inspected source and test assertions. No tests, migration, database, provider calls, build, or gate were run. Migration deployment, actual cleanup, live HTTP responses, and Gmail delivery remain unverified.
