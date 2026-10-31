The inspected source removes Gmail OAuth/API handling while retaining ordinary SMTP.

**Removed HTTP endpoints.** The regression test lists five method/path combinations and expects `404` for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

See `application/apps/api/src/routes/gmail-removed.test.ts#L11`. The fixture supplies fake authentication and an ADMIN context (`application/apps/api/src/routes/gmail-removed.test.ts#L4`). Implementation evidence agrees: the app’s registrar list contains no Gmail registrar, mounts the connector routes, and provides a shared `404` fallback (`application/apps/api/src/app.ts#L337`, `application/apps/api/src/app.ts#L431`). This does not establish that every unauthenticated request returns `404`; shared middleware can respond first.

**Exact stored-secret cleanup.** The migration executes:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus it deletes rows whose field is exactly `gmail-settings` or `gmail-grant`, or starts with `gmail-state:`—including the empty suffix. There is **no workspace or connector-type restriction**. Nonmatching fields are preserved by this statement, including `smtpPassword` and `emailApiKey`; it neither clears the whole table nor changes connector configuration. `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql#L1`

The cleanup test seeds those two exact Gmail fields, two state fields, and the two ordinary mail secrets, all under connector type `AI`. It executes the migration SQL and expects only `emailApiKey` and `smtpPassword` to remain. That is test coverage for those examples in one workspace, not exhaustive coverage of every field/type/workspace combination. `application/prisma/gmail-secret-cleanup.test.ts#L13`

**Ordinary `smtp.gmail.com`, including `GMAIL_API_ENABLED=1`.** Transport defaults to SMTP unless stored `mailTransport` explicitly equals `"API"` (`application/packages/server/src/modules/connectors/connector-settings.service.ts#L194`). SMTP settings return the ordinary host configuration and `smtpPassword`; only the explicit API branch supplies `config.emailApi` (`application/packages/server/src/modules/connectors/smtp-settings.usecases.ts#L15`).

`sendSmtpMessage` chooses HTTP email delivery only when `config.emailApi` exists. Otherwise it checks SMTP configuration/password, resolves the host, opens a socket, negotiates TLS as configured, and uses SMTP authentication and envelope commands. It contains no Gmail-host or `GMAIL_API_ENABLED` switch. `application/packages/server/src/infrastructure/providers/smtp-client.ts#L183`, `application/packages/server/src/infrastructure/providers/smtp-client.ts#L217`

The focused test sets `GMAIL_API_ENABLED="1"` with `smtp.gmail.com:587`, STARTTLS and a username, then supplies no password. It expects `SMTP_PASSWORD_MISSING` and no `fetch` call. This covers early rejection, not successful Gmail SMTP delivery. `application/packages/server/src/smtp-gmail-host.test.ts#L4` Ordinary SMTP configuration and test-email handlers remain registered (`application/apps/api/src/modules/connectors/connector-settings.controller.ts#L189`).

These are source conclusions and unexecuted test assertions. I ran no tests, migration, database or network operations; deployment status, actual cleanup, and successful mail delivery remain unverified.
