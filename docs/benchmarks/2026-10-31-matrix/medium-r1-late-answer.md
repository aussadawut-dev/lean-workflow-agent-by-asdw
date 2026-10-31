The source removes Gmail OAuth/API routes while retaining ordinary SMTP delivery.

1. **Removed HTTP endpoints**

   The removal test enumerates these five combinations and expects **404** for each:

   - `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
   - `GET /api/v1/settings/connectors/SMTP/gmail`
   - `PATCH /api/v1/settings/connectors/SMTP/gmail`
   - `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
   - `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

   Evidence: `application/apps/api/src/routes/gmail-removed.test.ts:5`. These are test expectations under a fake authenticated ADMIN context. The app mounts connector routes under `/api/v1` and supplies a generic 404 fallback: `application/apps/api/src/app.ts:347`, `application/apps/api/src/app.ts:401`, `application/apps/api/src/app.ts:431`. Ordinary SMTP configuration and test-email handlers remain: `application/apps/api/src/modules/connectors/connector-settings.controller.ts:189`.

2. **Exact stored-secret cleanup and preservation**

   The migration’s complete statement is:

   ```sql
   DELETE FROM "connector_secrets"
   WHERE "field" IN ('gmail-settings', 'gmail-grant')
      OR "field" LIKE 'gmail-state:%';
   ```

   Evidence: `application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql:2`.

   It deletes entire matching rows, across **all workspaces and connector types**—there are no additional filters. The first two names match exactly; the third matches the literal `gmail-state:` prefix plus any suffix, including an empty suffix. Nonmatching fields remain untouched by this statement, including `smtpPassword` and `emailApiKey`; it contains no connector-configuration update.

   The database test seeds `gmail-settings`, `gmail-grant`, two state fields, `smtpPassword`, and `emailApiKey`, executes that SQL, and expects only the latter two fields to remain. Its fixture covers one workspace and `connectorType: "AI"`: `application/prisma/gmail-secret-cleanup.test.ts:13`. The current secret allowlist also retains both ordinary mail credentials: `application/packages/server/src/modules/connectors/connector-secrets.service.ts:8`.

3. **Ordinary `smtp.gmail.com`, including `GMAIL_API_ENABLED=1`**

   Without explicit `config.emailApi`, `sendSmtpMessage` takes the normal SMTP path: validates configuration, requires a password when a username is present, resolves the host, opens TCP/TLS, negotiates STARTTLS as configured, and authenticates through SMTP PLAIN or LOGIN. There is no Gmail-host or `GMAIL_API_ENABLED` branch in this function: `application/packages/server/src/infrastructure/providers/smtp-client.ts:183`.

   Stored transport defaults to SMTP unless `mailTransport === "API"`; SMTP settings retrieve the preserved `smtpPassword`: `application/packages/server/src/modules/connectors/connector-settings.service.ts:194`, `application/packages/server/src/modules/connectors/smtp-settings.usecases.ts:11`.

   The focused test explicitly sets `GMAIL_API_ENABLED=1`, uses `smtp.gmail.com:587` with STARTTLS and a username, passes no password, and expects `SMTP_PASSWORD_MISSING` with no `fetch` calls: `application/packages/server/src/smtp-gmail-host.test.ts:4`. Explicit generic email-API configuration still selects HTTP delivery.

These are source conclusions and inspected test assertions. I executed no tests or migration and verified no deployment, credential revocation, or successful Gmail delivery. The Gmail-host test stops before network activity; shared middleware can also reject requests before the 404 fallback.
