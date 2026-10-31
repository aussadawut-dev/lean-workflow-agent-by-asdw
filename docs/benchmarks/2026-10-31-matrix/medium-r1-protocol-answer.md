The inspected source removes the Gmail OAuth/API connector while retaining ordinary SMTP support.

**Removed HTTP endpoints.** The removal test enumerates five method/path pairs and expects HTTP 404 for each, using a supplied authenticated ADMIN context:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

See `application/apps/api/src/routes/gmail-removed.test.ts:4>`. The app’s registration block contains no Gmail registrar, and unmatched requests have a JSON 404 fallback (`application/apps/api/src/app.ts:337`). Ordinary SMTP configuration and test-email handlers remain (`application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`). The test’s 404 expectation does not establish every response under different authentication or middleware conditions.

**Stored-secret cleanup.** The exact migration statement is:

```sql
DELETE FROM "connector_secrets" WHERE "field" IN ('gmail-settings', 'gmail-grant') OR "field" LIKE 'gmail-state:%';
```

It deletes entire matching rows, across all workspaces and connector types: there is no additional restriction. The prefix pattern includes `gmail-state:` with an empty suffix. Nonmatching rows—including `smtpPassword` and `emailApiKey`—are preserved by this statement; it does not delete every field beginning with `gmail`, or modify connector configuration. See `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:1`.

The companion test creates four matching fields plus `smtpPassword` and `emailApiKey`, all under connector type `AI`, executes the SQL, and expects exactly those latter two fields to remain (`application/prisma/gmail-secret-cleanup.test.ts:13`).

**`smtp.gmail.com` with `GMAIL_API_ENABLED=1`.** Ordinary SMTP configuration receives no Gmail-specific diversion. `sendSmtpMessage` selects HTTP/API delivery only through explicit `config.emailApi`; otherwise it validates SMTP settings, requires a password when a username is supplied, resolves the SMTP host, and uses socket-based SMTP with TLS/STARTTLS and password authentication (`application/packages/server/src/infrastructure/providers/smtp-client.ts:183`).

The focused regression test sets that environment flag to `"1"`, supplies `smtp.gmail.com:587` with STARTTLS and a username, passes a null password, and expects `SMTP_PASSWORD_MISSING` with no `fetch` call (`application/packages/server/src/smtp-gmail-host.test.ts:4`). Its coverage stops before connection establishment; it does not demonstrate successful Gmail delivery.

These are source conclusions and inspected test expectations. I executed no tests or migration and verified no deployed behavior, database cleanup, provider-token revocation, or live SMTP delivery.
