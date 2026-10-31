The inspected source removes the Gmail OAuth/API connector while retaining ordinary Gmail SMTP support.

**Removed HTTP endpoints**

The removal test enumerates these five method/path combinations and expects **404** for each:

- `GET /api/v1/gmail/oauth/callback` (tested with `?state=x&code=y`)
- `GET /api/v1/settings/connectors/SMTP/gmail`
- `PATCH /api/v1/settings/connectors/SMTP/gmail`
- `POST /api/v1/settings/connectors/SMTP/gmail/oauth/start`
- `DELETE /api/v1/settings/connectors/SMTP/gmail/account`

The test uses injected authentication resolving an ADMIN principal (`application/apps/api/src/routes/gmail-removed.test.ts#L4`). The implementation registers the connector controller, mounts it under `/api/v1`, and supplies a JSON `NOT_FOUND` fallback; the connector controller has no Gmail registrations (`application/apps/api/src/app.ts#L337`, `application/apps/api/src/modules/connectors/connector-settings.controller.ts#L189`). These are source expectations, not observed HTTP results.

**Stored-secret cleanup and preservation**

The migration contains exactly:

```sql
DELETE FROM "connector_secrets"
WHERE "field" IN ('gmail-settings', 'gmail-grant')
   OR "field" LIKE 'gmail-state:%';
```

Thus it deletes whole secret rows with either exact field name, or a field beginning `gmail-state:`—including that prefix with an empty suffix. There is **no workspace, connector-type, age, or ciphertext restriction**. Other field values are preserved; this statement does not modify connector configuration or other tables (`application/prisma/migrations/20261030100000_remove_gmail_connector_secrets/migration.sql#L1`).

The migration test seeds six fields under connector type `AI`, executes the SQL, and expects only `emailApiKey` and `smtpPassword` to remain. Its deleted examples are `gmail-settings`, `gmail-grant`, `gmail-state:abc`, and `gmail-state:def` (`application/prisma/gmail-secret-cleanup.test.ts#L13`). That fixture covers one workspace/type; broader deletion scope follows from the SQL predicate, not multi-workspace test coverage.

**Ordinary `smtp.gmail.com`, including `GMAIL_API_ENABLED=1`**

`sendSmtpMessage` selects HTTP delivery only when `config.emailApi` exists. Otherwise it validates SMTP configuration, rejects a configured username without a password as `SMTP_PASSWORD_MISSING`, resolves the host, opens an SMTP socket, negotiates TLS as configured, and authenticates using PLAIN or LOGIN. It has no Gmail-host or legacy-flag branch (`application/packages/server/src/infrastructure/providers/smtp-client.ts#L183`).

The dedicated test sets `GMAIL_API_ENABLED=1`, configures `smtp.gmail.com:587` with STARTTLS and a username, passes no password, and expects `SMTP_PASSWORD_MISSING` with zero mocked `fetch` calls (`application/packages/server/src/smtp-gmail-host.test.ts#L4`). This covers early rejection, not successful Gmail delivery.

Gmail is also absent from the API-provider enum; an HTTP test includes `emailApiProvider: "GMAIL"` among requests expected to return 400 (`application/packages/contracts/src/connector-settings.ts#L269`, `application/apps/api/src/routes/connector-settings.test.ts#L312`).

No tests, requests, migrations, or provider calls were executed. Migration application, deployed endpoint behavior, existing data cleanup, and successful Gmail SMTP delivery remain unverified.
