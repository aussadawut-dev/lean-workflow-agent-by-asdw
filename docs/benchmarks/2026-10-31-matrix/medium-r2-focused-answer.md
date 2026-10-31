The source removes five Gmail-specific routes while retaining ordinary SMTP.

1. **Removed HTTP endpoints**

   - `GET /api/v1/gmail/oauth/callback`
   - `GET /api/v1/settings/connectors/SMTP/gmail`
   - `PATCH /api/v1/settings/connectors/SMTP/gmail`
   - `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
   - `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

   The regression test constructs an app with a fake authenticated ADMIN and expects **404** for each; the callback includes `?state=x&code=y`. See `application/apps/api/src/routes/gmail-removed.test.ts:4`. The remaining connector controller registers SMTP configuration and test-email routes, without Gmail handlers (`application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`); the app supplies a generic JSON 404 fallback (`application/apps/api/src/app.ts:431`). This does not establish identical responses for every authentication or middleware condition.

2. **Exact stored-secret cleanup and preservation**

   The migration contains exactly:

   ```sql
   DELETE FROM "connector_secrets" WHERE "field" IN ('gmail-settings', 'gmail-grant') OR "field" LIKE 'gmail-state:%';
   ```

   Thus it deletes whole rows whose field equals either named value or starts with `gmail-state:`—including an empty suffix. There is **no workspace, connector-type, age, or connection-status restriction**. It does not decrypt values. Other field names, including `smtpPassword` and `emailApiKey`, do not match and are preserved; this statement does not modify connector configuration or other tables. See `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:1`.

   The migration test seeds six fields under connector type `AI`, executes that SQL, and expects only `emailApiKey` and `smtpPassword` to remain (`application/prisma/gmail-secret-cleanup.test.ts:12`). It does not explicitly exercise multiple workspaces/types or prefix edge cases; the broader scope follows from the predicate.

3. **Ordinary `smtp.gmail.com`, even with `GMAIL_API_ENABLED=1`**

   Transport selection uses explicit configuration: stored `mailTransport === "API"` selects API; otherwise SMTP is selected (`application/packages/server/src/modules/connectors/connector-settings.service.ts:194`). `sendSmtpMessage` dispatches HTTP only when `config.emailApi` exists. Otherwise it checks SMTP configuration/password, resolves the host, connects through TCP/TLS, negotiates STARTTLS where configured, and uses AUTH PLAIN/LOGIN. Neither the Gmail hostname nor that environment flag selects Gmail API (`application/packages/server/src/infrastructure/providers/smtp-client.ts:183`).

   The focused test sets the flag to `"1"`, uses `smtp.gmail.com:587` with STARTTLS and a username, supplies no password, and expects `SMTP_PASSWORD_MISSING` with no `fetch` calls (`application/packages/server/src/smtp-gmail-host.test.ts:4`). Its coverage stops before connection or successful delivery. Gmail is also absent from the API-provider allowlist; a test expects `GMAIL` rejection before HTTP (`application/packages/server/src/shared/email-api.ts:2`, `application/packages/server/src/email-api-client.test.ts:180`).

These are source and test-definition conclusions. I executed no tests, builds, migration, database/provider/network operations, or full gate. Migration application, deployed behavior, actual cleanup, and Gmail delivery remain unverified.
