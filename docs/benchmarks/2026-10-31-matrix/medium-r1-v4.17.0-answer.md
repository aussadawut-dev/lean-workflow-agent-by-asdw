Source inspection supports removal of the Gmail OAuth/API connector while retaining ordinary SMTP, including `smtp.gmail.com`. These are source conclusions; no tests or application behavior were executed.

**Removed HTTP endpoints**

The removal test enumerates five method/path combinations and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

Evidence: `application/apps/api/src/routes/gmail-removed.test.ts:10`. The application supplies a JSON `NOT_FOUND`/404 fallback at `application/apps/api/src/app.ts:431`. Ordinary SMTP configuration and test-email routes remain registered at `application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`.

**Exact stored-secret cleanup and preservation**

The migration contains exactly:

```sql
DELETE FROM "connector_secrets" WHERE "field" IN ('gmail-settings', 'gmail-grant') OR "field" LIKE 'gmail-state:%';
```

Thus, if applied, it deletes entire rows whose field equals either named value or starts with `gmail-state:`; `%` also permits an empty suffix. There is **no workspace, connector-type, or value filter**. All nonmatching rows are outside this statement’s deletion predicate, including `smtpPassword` and `emailApiKey`. The statement touches only `connector_secrets`. Evidence: `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:1`.

The migration test creates all six example fields under connector type `AI`, executes that SQL, and expects only `emailApiKey` and `smtpPassword` to remain. Its fixture covers one workspace and two nonempty state suffixes; broader matching follows from the SQL, not additional tested cases. Evidence: `application/prisma/gmail-secret-cleanup.test.ts:13`.

**`smtp.gmail.com`, including `GMAIL_API_ENABLED=1`**

The transport implementation selects HTTP email delivery through explicit `config.emailApi`. Otherwise, it follows SMTP configuration/password checks, DNS resolution, socket/TLS negotiation, and SMTP authentication. It contains no Gmail-host or `GMAIL_API_ENABLED` branch. A configured username without a password throws `SMTP_PASSWORD_MISSING` before DNS/socket work. Evidence: `application/packages/server/src/infrastructure/providers/smtp-client.ts:183`.

The dedicated test sets `GMAIL_API_ENABLED=1`, uses `smtp.gmail.com:587` with STARTTLS and a username, passes no password, and expects that error plus zero `fetch` calls. Evidence: `application/packages/server/src/smtp-gmail-host.test.ts:4`. This supports ordinary SMTP handling without flag-triggered Gmail API substitution; it does **not** demonstrate successful Gmail authentication or delivery.

Uncertainty remains about deployed routing, applied migrations, actual stored rows, credentials, and provider acceptance. None were inspected or verified.
